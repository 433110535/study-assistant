"""
按阿里云百炼华北 2（北京）实时推理原价估算文本费用。

不含缓存命中、Batch 半价和限时优惠。qwen-plus 用非思考模式、输入不超过 128K 的单价。
价目来自百炼模型价格表：qwen-max 输入 2.4 元/百万 tokens、输出 9.6 元；
qwen-plus 输入 0.8 元/百万 tokens、输出 2 元。
未知模型不估费用。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional, Tuple

# 每百万 tokens 的人民币单价：(输入, 输出)
_YUAN_PER_MILLION = {
    "qwen-max": (Decimal("2.4"), Decimal("9.6")),
    "qwen-plus": (Decimal("0.8"), Decimal("2")),
}


def estimate_cost_yuan(model: str, token_in: int, token_out: int) -> Optional[float]:
    token_in = max(0, int(token_in))
    token_out = max(0, int(token_out))
    if token_in == 0 and token_out == 0:
        return 0.0
    rates = _YUAN_PER_MILLION.get(model or "")
    if rates is None:
        return None
    yuan = (Decimal(token_in) * rates[0] + Decimal(token_out) * rates[1]) / Decimal(1_000_000)
    return float(yuan.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def usage_from_message(message: Any) -> Tuple[int, int]:
    """从 LangChain 消息上读取本次调用的输入、输出 token。没有用量时返回 0。"""
    metadata = getattr(message, "usage_metadata", None) or {}
    if metadata:
        return (
            int(metadata.get("input_tokens") or 0),
            int(metadata.get("output_tokens") or 0),
        )
    response_metadata = getattr(message, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or response_metadata.get("usage") or {}
    return (
        int(token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0),
        int(token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0),
    )
