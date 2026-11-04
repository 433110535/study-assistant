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


def _execute_read_image(agent, image_path: str, focus: str = "全部") -> str:
    from backend.tools.vision import read_image

    return read_image(image_path, focus=focus)


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


_register_all_tools()


def execute_tool(agent, tool_name: str, tool_args: Dict[str, Any]) -> str:
    """
    执行指定工具（带超时，结果写入 trace 由 Agent 层负责）
    """
    spec = get_tool_spec(tool_name)
    if not spec:
        return f"未知工具: {tool_name}"

    started = time.perf_counter()

    def _run() -> str:
        return spec.fn(agent, **tool_args)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run)
            result = future.result(timeout=spec.timeout_s)
        return result
    except FuturesTimeoutError:
        return f"工具 {tool_name} 执行超时（>{spec.timeout_s}s），请稍后重试。"
    except TypeError as e:
        return f"工具参数错误: {str(e)}"
    except Exception as e:
        return f"工具执行失败: {str(e)}"
    finally:
        _ = time.perf_counter() - started  # 耗时由 react_agent 记录
