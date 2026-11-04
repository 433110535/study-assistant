"""
LLM 辅助模块
统一管理通义千问 LLM 实例的创建
"""
from langchain_openai import ChatOpenAI

from backend.config import (
    LLM_MODEL, LLM_TEMPERATURE, MAX_TOKENS, get_api_key
)


def text_content(content) -> str:
    """把模型返回收成字符串。LangChain 1.x 的 content 可能是字符串，也可能是内容块列表。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                text = getattr(block, "text", None)
                parts.append(str(text) if text else "")
        return "".join(parts)
    return str(content)


def get_llm(temperature: float = None, max_tokens: int = None):
    """
    获取通义千问 LLM 实例（带超时和重试）

    Args:
        temperature: 温度参数（如果为 None 则使用配置）
        max_tokens: 最大 token 数（如果为 None 则使用配置）

    Returns:
        LLM 实例
    """
    api_key = get_api_key()
    temp = temperature if temperature is not None else LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else MAX_TOKENS

    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=temp,
        max_tokens=tokens,
        request_timeout=60,
        max_retries=2,
        stream_usage=True,
    )


# 默认 LLM 实例（按需创建）
_default_llm = None


def get_default_llm():
    """获取默认的 LLM 实例（单例模式）"""
    global _default_llm
    if _default_llm is None:
        _default_llm = get_llm()
    return _default_llm


# 别名，兼容性
create_llm = get_llm
