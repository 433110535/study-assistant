"""
ReAct Study Agent
标准 ReAct 循环: Thought -> Action -> Observation -> ... -> Final Answer
LLM 自行决定调用哪个工具，看到结果后判断是否足够，不够就继续调用
"""
import time
from typing import List, Optional, Generator

from langchain_core.messages import (
    HumanMessage, SystemMessage, AIMessage, ToolMessage
)
from backend.agents.base_agent import BaseAgent
from backend.agents.react_models import ReActEvent, ReActEventType, ReActStep, ReActResult
from backend.agents.react_tools import get_tool_schemas, execute_tool
from backend.llm_helper import text_content
from backend.config import LLM_MODEL
from backend.platform.llm_cost import usage_from_message
from backend.platform.trace_store import TraceRun

# FAISS 知识库
try:
    from backend.knowledge.knowledge_base_faiss import FAISSKnowledgeBase
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

REACT_SYSTEM_PROMPT = """你是一位专业的智能学习助手，名字叫"Jesse"。

你是一位经验丰富的学习导师，擅长用通俗易懂的语言解释复杂概念，帮助学生建立知识体系。

## 你可以使用的工具

1. **rag_search**: 从知识库中检索相关学习资料。当用户的问题可能涉及已上传的文档内容时使用。
2. **explain_concept**: 详细讲解一个概念，包含定义、类比和例子。当用户想要理解某个概念时使用。
3. **generate_study_plan**: 生成结构化的学习计划。当用户想要规划学习路线时使用。
4. **generate_questions**: 生成练习题，包含答案和解析。当用户想要练习巩固时使用。
5. **read_image**: 识别用户上传的题目/作业图片中的文字与公式。当消息中包含「题目图片路径」时，**必须先**调用此工具，再视情况 `rag_search`，最后分步讲解并可给 1 道同考点变式题（变式题答案可折叠提示，勿直接泄露最终答案）。
6. **save_mistake**: 用户明确要求记入错题本时调用。它只生成待确认记录，必须提醒用户到「错题本」页面确认后才会进入复习。
7. **run_code / run_tests**: 用户贴出 Python 代码、要求运行或判断对错时，先在沙箱里跑。有 assert 或测试用例时用 run_tests，否则用 run_code。不要把文件读写、网络或系统命令送进沙箱。
8. **explain_traceback**: 运行失败后调用，把报错说成人话。不要在这一步给出改正后的代码。
9. **hint_level**: 给提示之前必须调用。默认 level=1。用户说「再提示一点 / 看行号 / 给方向」时再升到 2 或 3。按工具返回的级别说话，不要附加修改后的完整代码，除非用户明确要答案并且已经给过至少一次提示。
10. **grade_item**: 用户给出了题目、自己的答案，并且提供了标准答案时，先调用它判对错。没有标准答案就不要声称已经判分；工具返回 ungraded 时，向用户要标准答案。
11. **diagnose_error**: 只在 grade_item 判错后调用，用它给出的错因类别，不要另起一个分类。
12. **make_variants**: 用户要同考点变式时调用。它只改题干里的数字，或预先列出的人名和常见物品，且不附答案。若返回 unsupported，不要编造同结构题。
13. **get_learning_state**: 用户问今天复习什么时先调用。只列出已确认且到时间的错题。
14. **plan_review**: 有到期题时生成晨间卡片，不附答案，也不要自己再编一份。
15. **send_message**: 用户明确说「发给我 / 推送复习」时才调用。它保存当天卡片；没配置飞书就不会外发。不要重复调用。
16. **reschedule**: 用户说「推到晚上」或给出新时间时调用。不要把它说成已经重新判分。

## 回答原则
- 先思考用户需要什么帮助，再决定是否需要调用工具
- 如果问题简单、不需要工具，直接回答即可
- 可以在一次回答中调用多个工具（比如先检索资料再讲解概念）
- 调用工具后，基于工具返回的结果，用通俗易懂的语言组织最终回答
- 回答结构清晰，多用例子和类比
- 用中文回答
"""


class ReActStudyAgent(BaseAgent):
    """
    ReAct 智能学习助手
    使用 function calling 实现工具调用循环
    """

    def __init__(self, max_iterations: int = 5, session_id: str = "default", **kwargs):
        super().__init__(**kwargs)
        self.max_iterations = max_iterations
        self.session_id = session_id

        # 绑定工具到 LLM
        self.tool_schemas = get_tool_schemas()
        self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)

        # FAISS 知识库（兼容 StudyAssistantAgent 的接口）
        self._kb = None
        self._rag_enabled = False
        if FAISS_AVAILABLE:
            try:
                self._kb = FAISSKnowledgeBase()
                self._rag_enabled = True
                if self.verbose:
                    print("[ReAct] FAISS 知识库加载成功")
            except Exception as e:
                if self.verbose:
                    print(f"[ReAct] FAISS 知识库加载失败: {e}")

    def get_system_prompt(self) -> str:
        """实现抽象方法"""
        return REACT_SYSTEM_PROMPT

    def react_stream(self, user_input: str) -> Generator[ReActEvent, None, None]:
        """
        ReAct 循环核心方法，逐步 yield 事件
        最终回答使用流式输出

        Args:
            user_input: 用户输入

        Yields:
            ReActEvent: 每个步骤的事件
        """
        messages = self._build_messages(user_input)
        iteration = 0
        trace = TraceRun(
            user_input=user_input,
            session_id=self.session_id,
            model=LLM_MODEL,
        )
        trace.start()
        self.last_trace_id = trace.trace_id
        final_status = "ok"

        for iteration in range(1, self.max_iterations + 1):
            yield ReActEvent(
                event_type=ReActEventType.THINKING,
                content="Jesse正在思考...",
                iteration=iteration
            )

            try:
                response = self.llm_with_tools.invoke(messages)
                prompt_tokens, completion_tokens = usage_from_message(response)
                trace.add_usage(prompt_tokens, completion_tokens)
            except Exception as e:
                final_status = "error"
                yield ReActEvent(
                    event_type=ReActEventType.ERROR,
                    content=f"LLM 调用失败: {str(e)}",
                    iteration=iteration
                )
                trace.finish("", iteration, status=final_status)
                break

            messages.append(response)

            if not response.tool_calls:
                yield ReActEvent(
                    event_type=ReActEventType.THINKING,
                    content="Jesse正在组织回答...",
                    iteration=iteration
                )
                streamed = ""
                try:
                    streamed = yield from self._stream_answer(messages[:-1], iteration, trace)
                except Exception as e:
                    streamed = streamed or text_content(response.content) or f"回答生成失败: {e}"

                final_content = streamed or text_content(response.content)
                yield ReActEvent(
                    event_type=ReActEventType.FINAL_ANSWER,
                    content=final_content,
                    iteration=iteration
                )
                self.add_to_history("user", user_input)
                self.add_to_history("assistant", final_content)
                trace.finish(final_content or "", iteration, status=final_status)
                return

            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_call_id = tc.get("id", "")

                yield ReActEvent(
                    event_type=ReActEventType.TOOL_CALL,
                    content=f"调用工具: {tool_name}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    iteration=iteration
                )

                t0 = time.perf_counter()
                result = execute_tool(self, tool_name, tool_args)
                tool_ms = int((time.perf_counter() - t0) * 1000)
                tool_status = "error" if result.startswith(
                    ("未知工具", "工具参数错误", "工具执行失败", "工具 ", "未配置", "图片不存在")
                ) else "ok"
                try:
                    trace.log_tool_call(
                        tool_name, tool_args, result, tool_status, tool_ms
                    )
                except Exception:
                    pass

                preview = result[:500] + "..." if len(result) > 500 else result
                yield ReActEvent(
                    event_type=ReActEventType.TOOL_RESULT,
                    content=f"获取结果: {preview[:100]}",
                    tool_name=tool_name,
                    tool_result=result,
                    iteration=iteration
                )

                messages.append(
                    ToolMessage(content=result, tool_call_id=tool_call_id)
                )

        yield ReActEvent(
            event_type=ReActEventType.THINKING,
            content="Jesse正在组织最终回答...",
            iteration=iteration
        )

        streamed = ""
        try:
            streamed = yield from self._stream_answer(messages, iteration, trace)
        except Exception as e:
            streamed = streamed or f"抱歉，生成回答时出错: {str(e)}"

        final_content = streamed or "（无内容）"
        yield ReActEvent(
            event_type=ReActEventType.FINAL_ANSWER,
            content=final_content,
            iteration=iteration
        )
        self.add_to_history("user", user_input)
        self.add_to_history("assistant", final_content)
        trace.finish(final_content or "", iteration, status=final_status)

    def react(self, user_input: str) -> ReActResult:
        """
        同步执行 ReAct 循环，返回完整结果

        Args:
            user_input: 用户输入

        Returns:
            ReActResult: 完整的运行结果
        """
        steps = []
        final_answer = ""
        tools_used = []
        total_iterations = 0

        for event in self.react_stream(user_input):
            total_iterations = max(total_iterations, event.iteration)

            if event.event_type == ReActEventType.TOOL_CALL:
                if event.tool_name not in tools_used:
                    tools_used.append(event.tool_name)

            steps.append(ReActStep(
                iteration=event.iteration,
                event_type=event.event_type,
                content=event.content,
                tool_name=event.tool_name,
                tool_args=event.tool_args,
                tool_result_preview=event.tool_result[:300] if event.tool_result else ""
            ))

            if event.event_type == ReActEventType.FINAL_ANSWER:
                final_answer = event.content

        return ReActResult(
            user_input=user_input,
            final_answer=final_answer,
            steps=steps,
            total_iterations=total_iterations,
            tools_used=tools_used,
            trace_id=getattr(self, "last_trace_id", ""),
        )

    def _stream_answer(self, messages, iteration: int, trace: TraceRun):
        """流式写出最终回答，并把最后一块上的 token 用量记进同一次运行。"""
        streamed = ""
        seen_in = 0
        seen_out = 0
        for chunk in self.llm.stream(messages):
            piece = text_content(chunk.content)
            if piece:
                streamed += piece
                yield ReActEvent(
                    event_type=ReActEventType.ANSWER_CHUNK,
                    content=piece,
                    iteration=iteration,
                )
            prompt_tokens, completion_tokens = usage_from_message(chunk)
            if prompt_tokens or completion_tokens:
                seen_in, seen_out = prompt_tokens, completion_tokens
        trace.add_usage(seen_in, seen_out)
        return streamed

    # ========== 向后兼容方法 ==========

    def chat_with_tools_stream(self, user_input: str) -> Generator[str, None, None]:
        """向后兼容：只 yield 最终回答的文本"""
        for event in self.react_stream(user_input):
            if event.event_type == ReActEventType.FINAL_ANSWER:
                yield event.content

    def chat_with_tools(self, user_input: str) -> str:
        """向后兼容：同步返回最终回答"""
        result = ""
        for event in self.react_stream(user_input):
            if event.event_type == ReActEventType.FINAL_ANSWER:
                result = event.content
        return result

    def chat(self, user_input: str) -> str:
        """普通对话（不带工具）"""
        messages = self.format_messages(user_input)
        self.add_to_history("user", user_input)
        response = self.llm.invoke(messages)
        answer = text_content(response.content)
        self.add_to_history("assistant", answer)
        return answer

    def chat_stream(self, user_input: str) -> Generator[str, None, None]:
        """普通流式对话（不带工具）"""
        messages = self.format_messages(user_input)
        self.add_to_history("user", user_input)
        full_response = ""
        for chunk in self.llm.stream(messages):
            if hasattr(chunk, "content"):
                piece = text_content(chunk.content)
                if not piece:
                    continue
                full_response += piece
                yield piece
        self.add_to_history("assistant", full_response)

    def _build_messages(self, user_input: str) -> List:
        """构建消息列表（用于 ReAct 循环）"""
        messages = [SystemMessage(content=self.get_system_prompt())]
        for msg in self.chat_history[-10:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=user_input))
        return messages

    def set_knowledge_base(self, kb):
        """外部设置知识库"""
        self._kb = kb
        self._rag_enabled = kb is not None
