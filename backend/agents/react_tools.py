"""
ReAct Agent 工具定义
OpenAI function calling 格式的工具 schema + 执行器（经工具注册表统一管理）
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict

from backend.agents.tool_registry import ToolSpec, get_tool_schemas, get_tool_spec, register_tool


# ========== 工具执行器 ==========

def _execute_rag_search(agent, query: str, top_k: int = 3) -> str:
    """执行知识库检索"""
    if not agent._rag_enabled or not agent._kb:
        return "知识库未启用或为空，无法检索。"

    try:
        results = agent._kb.search(query, top_k=top_k)
        if not results:
            return "未在知识库中找到相关内容。"

        parts = []
        for i, r in enumerate(results):
            title = r.get("metadata", {}).get("title", "未知来源")
            content = r.get("content", "")
            similarity = r.get("similarity", 0)
            parts.append(
                f"【资料{i+1}】来源: {title}, 相似度: {similarity:.1%}\n{content}"
            )
        return "\n\n".join(parts)
    except Exception as e:
        return f"知识库检索失败: {str(e)}"


def _execute_explain_concept(
    agent, concept: str, subject: str = "", level: str = "初学者"
) -> str:
    from backend.tools.knowledge import explain_concept

    return explain_concept(concept, subject=subject, level=level, llm=agent.llm)


def _execute_generate_study_plan(
    agent,
    subject: str,
    goal: str,
    duration_days: int = 30,
    current_level: str = "初学者",
) -> str:
    from backend.tools.plan_generator import generate_study_plan

    return generate_study_plan(
        subject, goal, duration_days, current_level=current_level, llm=agent.llm
    )


def _execute_generate_questions(
    agent, topic: str, difficulty: str = "中等", count: int = 3
) -> str:
    from backend.tools.question_generator import generate_questions

    return generate_questions(topic, difficulty=difficulty, count=count, llm=agent.llm)


def _execute_save_mistake(
    agent,
    subject: str,
    concept: str,
    error_type: str,
    question_text: str,
    student_answer: str = "",
    correct_answer: str = "",
) -> str:
    from backend.platform.mistake_store import create_pending

    user_id = getattr(agent, "user_id", None) or "student"
    mistake_id = create_pending(
        user_id=user_id,
        subject=subject,
        concept=concept,
        error_type=error_type,
        question_text=question_text,
        student_answer=student_answer,
        correct_answer=correct_answer,
    )
    return (
        f"已生成待确认错题（id={mistake_id}）。"
        "它还不会进入复习，请用户在「错题本」页面确认或丢弃。"
    )


def _execute_read_image(agent, image_path: str, focus: str = "全部") -> str:
    from backend.tools.vision import read_image

    return read_image(image_path, focus=focus)


def _execute_run_code(agent, code: str, timeout_s: int = 2) -> str:
    from backend.tools.code_sandbox import format_run_result, run_student_code

    return format_run_result(run_student_code(code, timeout_s=timeout_s))


def _execute_run_tests(agent, code: str, tests: str, timeout_s: int = 2) -> str:
    from backend.tools.code_sandbox import format_run_result, run_student_code

    return format_run_result(run_student_code(code, tests=tests, timeout_s=timeout_s))


def _execute_explain_traceback(agent, observation: str) -> str:
    from backend.tools.code_sandbox import explain_traceback

    return explain_traceback(observation)


def _execute_hint_level(agent, level: int = 1, observation: str = "") -> str:
    from backend.tools.code_sandbox import hint_for_level

    return hint_for_level(level, observation)


def _execute_grade_item(
    agent,
    question_text: str,
    student_answer: str,
    correct_answer: str = "",
) -> str:
    from backend.tools.grading import format_grade, grade_item

    return format_grade(grade_item(question_text, student_answer, correct_answer))


def _execute_diagnose_error(
    agent,
    question_text: str,
    student_answer: str,
    correct_answer: str = "",
) -> str:
    from backend.tools.grading import diagnose_error, format_diagnosis

    return format_diagnosis(diagnose_error(question_text, student_answer, correct_answer))


def _execute_make_variants(agent, question_text: str, count: int = 3) -> str:
    from backend.tools.grading import format_variants, make_variants

    return format_variants(make_variants(question_text, count))


def _review_user_id(agent) -> str:
    return getattr(agent, "user_id", None) or "student"


def _execute_get_learning_state(agent) -> str:
    from backend.platform.review_planner import get_learning_state

    state = get_learning_state(_review_user_id(agent))
    due = state["due"]
    if not due:
        return "当前没有到期复习。"
    lines = [f"到期 {len(due)} 题"]
    for item in due:
        lines.append(
            f"- {item.get('concept') or '未命名考点'} · {item.get('subject') or '未分科'}"
            f"（id={item['id']}）"
        )
        question = (item.get("question_text") or "").strip()
        if question:
            lines.append(f"  {question}")
    return "\n".join(lines)


def _execute_plan_review(agent) -> str:
    from backend.platform.review_planner import get_learning_state
    from backend.tools.review_schedule import format_morning_card

    card = format_morning_card(get_learning_state(_review_user_id(agent))["due"])
    return card or "当前没有到期复习。"


def _execute_send_message(agent) -> str:
    from backend.platform.review_planner import run_review_push
    from backend.tools.feishu_webhook import sender_from_env

    result = run_review_push(_review_user_id(agent), sender=sender_from_env())
    if result["reason"] == "none_due":
        return "当前没有到期复习，未发送。"
    if result["status"] == "failed":
        return f"晨间卡片外发失败：{result['error']}。内容已留在本地发件箱。"
    if result["reason"] == "already_delivered":
        return "今天的晨间卡片已保存，没有重复发送。\n" + result["body"]
    if result["channel"] == "feishu":
        return "已保存并发送到飞书。\n" + result["body"]
    return "已保存到本地发件箱。未配置 REVIEW_WEBHOOK_URL，所以没有外发。\n" + result["body"]


def _execute_reschedule(agent, when_text: str, mistake_id: str = "") -> str:
    from datetime import datetime, timezone

    from backend.platform.review_planner import get_learning_state, reschedule

    user_id = _review_user_id(agent)
    now = datetime.now(timezone.utc)
    if mistake_id.strip():
        ids = [mistake_id.strip()]
    else:
        ids = [item["id"] for item in get_learning_state(user_id, now=now)["due"]]
    if not ids:
        return "没有可改期的到期错题。"
    moved = 0
    for item_id in ids:
        if reschedule(item_id, when_text, now=now):
            moved += 1
    if moved == 0:
        return "改期失败。可以说「推到晚上」，或给出 ISO 时间。"
    return f"已把 {moved} 道到期错题改期（{when_text}）。推到晚上即当天 20:00（北京时间）。"


# ========== 注册工具 ==========

def _register_all_tools() -> None:
    register_tool(
        ToolSpec(
            name="rag_search",
            fn=_execute_rag_search,
            schema={
                "type": "function",
                "function": {
                    "name": "rag_search",
                    "description": (
                        "从知识库中检索与查询相关的学习资料，返回相关的文档片段和来源信息。"
                        "当用户的问题可能需要参考知识库中的文档时使用此工具。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索查询文本"},
                            "top_k": {
                                "type": "integer",
                                "description": "返回结果数量，默认3",
                                "default": 3,
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            side_effects=False,
            cost_hint="embedding+检索",
            timeout_s=45,
        )
    )
    register_tool(
        ToolSpec(
            name="explain_concept",
            fn=_execute_explain_concept,
            schema={
                "type": "function",
                "function": {
                    "name": "explain_concept",
                    "description": (
                        "详细讲解一个学习概念，包含定义、核心要点、生活类比、举例说明。"
                        "当用户想要理解某个概念时使用。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "concept": {"type": "string", "description": "要讲解的概念名称"},
                            "subject": {
                                "type": "string",
                                "description": "所属学科，如编程、数学、英语等",
                                "default": "",
                            },
                            "level": {
                                "type": "string",
                                "description": "学习者水平：初学者/中级/高级",
                                "default": "初学者",
                            },
                        },
                        "required": ["concept"],
                    },
                },
            },
            cost_hint="llm:1",
        )
    )
    register_tool(
        ToolSpec(
            name="generate_study_plan",
            fn=_execute_generate_study_plan,
            schema={
                "type": "function",
                "function": {
                    "name": "generate_study_plan",
                    "description": (
                        "为指定学科生成结构化的学习计划，包含分阶段安排和检查点。"
                        "当用户想要制定学习规划时使用。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "要学习的学科或主题"},
                            "goal": {"type": "string", "description": "学习目标"},
                            "duration_days": {
                                "type": "integer",
                                "description": "计划学习天数",
                                "default": 30,
                            },
                            "current_level": {
                                "type": "string",
                                "description": "当前水平：初学者/中级/高级",
                                "default": "初学者",
                            },
                        },
                        "required": ["subject", "goal"],
                    },
                },
            },
            cost_hint="llm:1",
        )
    )
    register_tool(
        ToolSpec(
            name="generate_questions",
            fn=_execute_generate_questions,
            schema={
                "type": "function",
                "function": {
                    "name": "generate_questions",
                    "description": (
                        "生成指定主题的练习题，包含题目、答案和详细解析。"
                        "当用户想要做练习巩固知识时使用。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "练习题的主题"},
                            "difficulty": {
                                "type": "string",
                                "description": "难度：简单/中等/困难",
                                "default": "中等",
                            },
                            "count": {
                                "type": "integer",
                                "description": "题目数量",
                                "default": 3,
                            },
                        },
                        "required": ["topic"],
                    },
                },
            },
            cost_hint="llm:1",
        )
    )
    register_tool(
        ToolSpec(
            name="read_image",
            fn=_execute_read_image,
            schema={
                "type": "function",
                "function": {
                    "name": "read_image",
                    "description": (
                        "读取用户上传的作业或题目图片，识别文字与公式。"
                        "当用户消息中包含题目图片路径时，必须先调用此工具再讲解或检索。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_path": {
                                "type": "string",
                                "description": "本地图片路径（绝对或相对项目根）",
                            },
                            "focus": {
                                "type": "string",
                                "description": "重点识别区域，如题干、选项、手写答案",
                                "default": "全部",
                            },
                        },
                        "required": ["image_path"],
                    },
                },
            },
            side_effects=False,
            cost_hint="vl:1 次调用",
            timeout_s=90,
        )
    )
    register_tool(
        ToolSpec(
            name="save_mistake",
            fn=_execute_save_mistake,
            schema={
                "type": "function",
                "function": {
                    "name": "save_mistake",
                    "description": (
                        "把一道错题记为待确认记录。调用后必须告诉用户到「错题本」确认，"
                        "未确认前不会进入复习。适用于用户明确说「记下来 / 加入错题本」。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "学科"},
                            "concept": {"type": "string", "description": "考点或概念"},
                            "error_type": {
                                "type": "string",
                                "description": "错因：概念不清 / 计算失误 / 审题错误 / 其他",
                            },
                            "question_text": {"type": "string", "description": "题干"},
                            "student_answer": {
                                "type": "string",
                                "description": "学生的答案",
                                "default": "",
                            },
                            "correct_answer": {
                                "type": "string",
                                "description": "正确答案，未知可留空",
                                "default": "",
                            },
                        },
                        "required": ["subject", "concept", "error_type", "question_text"],
                    },
                },
            },
            side_effects=True,
            requires_approval=True,
            cost_hint="sqlite:1 写",
        )
    )
    register_tool(
        ToolSpec(
            name="run_code",
            fn=_execute_run_code,
            schema={
                "type": "function",
                "function": {
                    "name": "run_code",
                    "description": (
                        "在本机沙箱中运行学生的 Python 代码，返回标准输出或异常。"
                        "用户贴出代码、要求运行或排查报错时使用。不要用它执行文件、网络或系统命令。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "要运行的 Python 源码"},
                            "timeout_s": {
                                "type": "integer",
                                "description": "超时秒数，1 到 5",
                                "default": 2,
                            },
                        },
                        "required": ["code"],
                    },
                },
            },
            side_effects=False,
            timeout_s=15,
            cost_hint="sandbox:local",
        )
    )
    register_tool(
        ToolSpec(
            name="run_tests",
            fn=_execute_run_tests,
            schema={
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": (
                        "在沙箱中先运行学生代码，再运行测试断言。"
                        "用户给出了测试、assert，或要求判断对错时使用。失败后不要直接改写完整答案。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "学生的函数或脚本"},
                            "tests": {
                                "type": "string",
                                "description": "断言或其他检查代码，例如 assert add(1, 2) == 3",
                            },
                            "timeout_s": {
                                "type": "integer",
                                "description": "超时秒数，1 到 5",
                                "default": 2,
                            },
                        },
                        "required": ["code", "tests"],
                    },
                },
            },
            side_effects=False,
            timeout_s=15,
            cost_hint="sandbox:local",
        )
    )
    register_tool(
        ToolSpec(
            name="explain_traceback",
            fn=_execute_explain_traceback,
            schema={
                "type": "function",
                "function": {
                    "name": "explain_traceback",
                    "description": (
                        "把 run_code 或 run_tests 的失败结果翻译成学生能读的说明。"
                        "只解释错误，不生成改正后的代码。运行失败后、给提示之前调用。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "observation": {
                                "type": "string",
                                "description": "上一次运行工具返回的原文",
                            },
                        },
                        "required": ["observation"],
                    },
                },
            },
            cost_hint="local",
        )
    )
    register_tool(
        ToolSpec(
            name="hint_level",
            fn=_execute_hint_level,
            schema={
                "type": "function",
                "function": {
                    "name": "hint_level",
                    "description": (
                        "按教学级别生成允许说出的提示。默认 level=1。"
                        "用户要求再具体一点时升到 2 或 3。任何级别都不要附上修改后的完整代码，"
                        "除非用户明确说「给我答案」并且已经给过至少一次提示。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "integer",
                                "description": "1 只说类别，2 加行号和异常原文，3 再加一句检查方向",
                                "default": 1,
                            },
                            "observation": {
                                "type": "string",
                                "description": "上一次运行工具返回的原文",
                                "default": "",
                            },
                        },
                        "required": ["level"],
                    },
                },
            },
            cost_hint="local",
        )
    )
    register_tool(
        ToolSpec(
            name="grade_item",
            fn=_execute_grade_item,
            schema={
                "type": "function",
                "function": {
                    "name": "grade_item",
                    "description": (
                        "对照标准答案判断学生答案对错。没有标准答案时返回 ungraded，"
                        "这时不要说题目已经判对或判错。多个可接受答案用 || 分隔。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question_text": {"type": "string", "description": "题干"},
                            "student_answer": {"type": "string", "description": "学生的答案"},
                            "correct_answer": {
                                "type": "string",
                                "description": "标准答案。未知时留空，不要猜测",
                                "default": "",
                            },
                        },
                        "required": ["question_text", "student_answer"],
                    },
                },
            },
            side_effects=False,
            cost_hint="local",
        )
    )
    register_tool(
        ToolSpec(
            name="diagnose_error",
            fn=_execute_diagnose_error,
            schema={
                "type": "function",
                "function": {
                    "name": "diagnose_error",
                    "description": (
                        "在有标准答案且 grade_item 判错之后，归类错因："
                        "概念不清、计算失误、审题错误或其他。判对时不要编造错因。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question_text": {"type": "string", "description": "题干"},
                            "student_answer": {"type": "string", "description": "学生的答案"},
                            "correct_answer": {
                                "type": "string",
                                "description": "标准答案",
                                "default": "",
                            },
                        },
                        "required": ["question_text", "student_answer", "correct_answer"],
                    },
                },
            },
            side_effects=False,
            cost_hint="local",
        )
    )
    register_tool(
        ToolSpec(
            name="make_variants",
            fn=_execute_make_variants,
            schema={
                "type": "function",
                "function": {
                    "name": "make_variants",
                    "description": (
                        "把题干里的数字换成邻近数字，生成同结构变式，不附答案。"
                        "题干没有数字时会拒绝，这时不要自己编造同结构题。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question_text": {"type": "string", "description": "原题题干"},
                            "count": {
                                "type": "integer",
                                "description": "变式数量，1 到 5",
                                "default": 3,
                            },
                        },
                        "required": ["question_text"],
                    },
                },
            },
            side_effects=False,
            cost_hint="local",
        )
    )
    register_tool(
        ToolSpec(
            name="get_learning_state",
            fn=_execute_get_learning_state,
            schema={
                "type": "function",
                "function": {
                    "name": "get_learning_state",
                    "description": (
                        "读取当前用户已经确认、并且到了复习时间的错题。"
                        "用户问今天该复习什么、或要安排复习时先调用它。"
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            side_effects=False,
            cost_hint="sqlite:读",
        )
    )
    register_tool(
        ToolSpec(
            name="plan_review",
            fn=_execute_plan_review,
            schema={
                "type": "function",
                "function": {
                    "name": "plan_review",
                    "description": (
                        "根据到期错题生成一张晨间复习卡片，不附标准答案，也不发送。"
                        "调用 get_learning_state 看到有到期题后再用它。"
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            side_effects=False,
            cost_hint="local",
        )
    )
    register_tool(
        ToolSpec(
            name="send_message",
            fn=_execute_send_message,
            schema={
                "type": "function",
                "function": {
                    "name": "send_message",
                    "description": (
                        "把今天的晨间复习卡片保存到发件箱。同一天不会重复保存。"
                        "只有配置了 REVIEW_WEBHOOK_URL 才会发到飞书。"
                        "用户没明确要发送时不要调用。"
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            side_effects=True,
            requires_approval=True,
            cost_hint="sqlite:1 写；可选飞书 1 次",
        )
    )
    register_tool(
        ToolSpec(
            name="reschedule",
            fn=_execute_reschedule,
            schema={
                "type": "function",
                "function": {
                    "name": "reschedule",
                    "description": (
                        "改到期错题的下次复习时间，不改变掌握度。"
                        "用户说「推到晚上」时 when_text 传「推到晚上」，即改到当天北京时间 20:00。"
                        "不传 mistake_id 时改当前全部到期题。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "when_text": {
                                "type": "string",
                                "description": "推到晚上、明天，或 ISO 时间",
                            },
                            "mistake_id": {
                                "type": "string",
                                "description": "只改这一条；留空则改全部到期题",
                                "default": "",
                            },
                        },
                        "required": ["when_text"],
                    },
                },
            },
            side_effects=True,
            requires_approval=True,
            cost_hint="sqlite:1 写",
        )
    )


_register_all_tools()


def execute_tool(agent, tool_name: str, tool_args: Dict[str, Any]) -> str:
    """
    执行指定工具。超时或执行异常会再试 ToolSpec.retries 次。
    参数错误不重试。结果写入 trace 由 Agent 层负责。
    """
    spec = get_tool_spec(tool_name)
    if not spec:
        return f"未知工具: {tool_name}"

    attempts = max(0, int(spec.retries)) + 1
    last_error = f"工具执行失败: {tool_name}"
    started = time.perf_counter()
    try:
        for _ in range(attempts):
            def _run() -> str:
                return spec.fn(agent, **tool_args)

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(_run)
                    return future.result(timeout=spec.timeout_s)
            except FuturesTimeoutError:
                last_error = f"工具 {tool_name} 执行超时（>{spec.timeout_s}s），请稍后重试。"
            except TypeError as e:
                return f"工具参数错误: {str(e)}"
            except Exception as e:
                last_error = f"工具执行失败: {str(e)}"
        return last_error
    finally:
        _ = time.perf_counter() - started  # 耗时由 react_agent 记录
