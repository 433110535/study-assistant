"""
LLM 辅助模块
统一管理通义千问 LLM 实例的创建
"""
from langchain_openai import ChatOpenAI

from backend.config import (
    LLM_MODEL, LLM_TEMPERATURE, MAX_TOKENS, get_api_key
)


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
