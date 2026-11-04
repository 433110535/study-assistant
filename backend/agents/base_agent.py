"""
基础 Agent 类（通义千问）
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.callbacks import BaseCallbackHandler
from backend.llm_helper import get_llm, text_content
from backend.config import (
    LLM_MODEL, LLM_TEMPERATURE, MAX_TOKENS
)


class ThinkingCallback(BaseCallbackHandler):
    """思维链回调处理器 - 用于可视化 AI 的思考过程"""

    def __init__(self):
        self.thoughts: List[str] = []

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """LLM 开始时的回调"""
        self.thoughts.append("正在思考...")

    def on_llm_end(self, response: Any, **kwargs) -> None:
        """LLM 结束时的回调"""
        self.thoughts.append("思考完成")


class BaseAgent(ABC):
    """所有 Agent 的基类"""

    def __init__(
        self,
        model: str = LLM_MODEL,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
        verbose: bool = True
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose  # 是否打印调试信息

        # 初始化 LLM
        self.llm = get_llm(temperature=temperature, max_tokens=max_tokens)

        # 对话历史
        self.chat_history: List[Dict[str, str]] = []

        # 思维链记录
        self.thinking_callback = ThinkingCallback()

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词 - 子类必须实现"""
        pass

    def add_to_history(self, role: str, content: str):
        """添加到对话历史"""
        self.chat_history.append({"role": role, "content": content})

    def clear_history(self):
        """清空对话历史"""
        self.chat_history = []

    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.chat_history

    def format_messages(self, user_input: str) -> List:
        """格式化消息为 LangChain 格式"""
        messages = [SystemMessage(content=self.get_system_prompt())]

        # 添加历史消息
        for msg in self.chat_history[-10:]:  # 只保留最近10轮
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # 添加当前用户输入
        messages.append(HumanMessage(content=user_input))

        return messages

    async def achat(self, user_input: str) -> str:
        """异步聊天方法"""
        messages = self.format_messages(user_input)

        response = await self.llm.ainvoke(
            messages,
            config={"callbacks": [self.thinking_callback] if self.verbose else []}
        )

        # 更新历史
        self.add_to_history("user", user_input)
        answer = text_content(response.content)
        self.add_to_history("assistant", answer)

        return answer

    def chat(self, user_input: str) -> str:
        """同步聊天方法"""
        messages = self.format_messages(user_input)

        if self.verbose:
            print("生成中...")

        response = self.llm.invoke(
            messages,
            config={"callbacks": [self.thinking_callback] if self.verbose else []}
        )

        # 更新历史
        self.add_to_history("user", user_input)
        answer = text_content(response.content)
        self.add_to_history("assistant", answer)

        return answer

    def chat_stream(self, user_input: str):
        """
        流式聊天方法 - 迭代器

        Yields:
            str: 每次返回一个文本块
        """
        messages = self.format_messages(user_input)

        # 更新用户历史
        self.add_to_history("user", user_input)

        if self.verbose:
            print("流式生成中...")

        # 流式输出
        full_response = ""
        for chunk in self.llm.stream(messages):
            if hasattr(chunk, "content"):
                content = text_content(chunk.content)
                if not content:
                    continue
                full_response += content
                yield content

        # 更新助手历史
        self.add_to_history("assistant", full_response)

    def get_thinking_process(self) -> List[str]:
        """获取思维链过程"""
        return self.thinking_callback.thoughts
