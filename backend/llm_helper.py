"""
LLM 辅助模块
统一管理通义千问 LLM 实例的创建。

客户端 max_retries 设为 0。重试、退避和熔断只在这一层做，避免和 SDK 再重试一次。
间隔与工具执行器相同：min(8, 0.5 × 2^attempt) + [0, 0.25) 秒。
连续 3 次调用失败后熔断 30 秒。TypeError 不重试，也不计入熔断。
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Callable, Iterator, Optional

from langchain_openai import ChatOpenAI

from backend.config import (
    LLM_MODEL, LLM_TEMPERATURE, MAX_TOKENS, get_api_key
)

_BACKOFF_BASE_S = 0.5
_BACKOFF_CAP_S = 8.0
_BACKOFF_JITTER_S = 0.25
_MODEL_ATTEMPTS = 3
_CIRCUIT_FAILURE_LIMIT = 3
_CIRCUIT_COOLDOWN_S = 30.0


class LLMUnavailable(RuntimeError):
    """熔断打开时抛出。调用方按模型失败处理，不再请求。"""


def _backoff_seconds(attempt: int, jitter_s: float) -> float:
    growth = _BACKOFF_BASE_S * (2 ** attempt)
    return min(_BACKOFF_CAP_S, growth) + jitter_s


def _sample_jitter() -> float:
    return random.uniform(0.0, _BACKOFF_JITTER_S)


class _ModelCircuit:
    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self.clock = clock or time.monotonic
        self._failures = 0
        self._open_until: Optional[float] = None

    def blocked(self) -> bool:
        if self._open_until is None:
            return False
        if self.clock() >= self._open_until:
            self._open_until = None
            self._failures = 0
            return False
        return True

    def success(self) -> None:
        self._failures = 0
        self._open_until = None

    def failure(self) -> None:
        self._failures += 1
        if self._failures >= _CIRCUIT_FAILURE_LIMIT:
            self._open_until = self.clock() + _CIRCUIT_COOLDOWN_S

    def reset(self) -> None:
        self._failures = 0
        self._open_until = None


_circuit = _ModelCircuit()
_named_circuits: dict = {}


def circuit_for(name: str) -> _ModelCircuit:
    if name == "llm":
        return _circuit
    found = _named_circuits.get(name)
    if found is None:
        found = _ModelCircuit()
        found.clock = _circuit.clock
        _named_circuits[name] = found
    return found


def reset_model_circuit() -> None:
    _circuit.reset()
    for circuit in _named_circuits.values():
        circuit.reset()


def invoke_named(
    name: str,
    call: Callable[[], Any],
    *,
    label: str = "外部调用",
    sleeper: Optional[Callable[[float], None]] = None,
    jitter: Optional[Callable[[], float]] = None,
) -> Any:
    """按名称分开熔断。失败再试，一共 3 次。TypeError 不重试。"""
    circuit = circuit_for(name)
    if circuit.blocked():
        raise LLMUnavailable(f"{label}连续失败，已暂时熔断，请稍后再试。")
    sleep = sleeper if sleeper is not None else time.sleep
    sample = jitter if jitter is not None else _sample_jitter
    last: Optional[BaseException] = None
    for attempt in range(_MODEL_ATTEMPTS):
        try:
            result = call()
        except TypeError:
            raise
        except Exception as exc:
            last = exc
            if attempt + 1 >= _MODEL_ATTEMPTS:
                circuit.failure()
                raise
            sleep(_backoff_seconds(attempt, sample()))
        else:
            circuit.success()
            return result
    raise last or LLMUnavailable(f"{label}失败")


def invoke_model(
    call: Callable[[], Any],
    *,
    sleeper: Optional[Callable[[float], None]] = None,
    jitter: Optional[Callable[[], float]] = None,
) -> Any:
    """调用一次模型。失败再试，一共 3 次。熔断打开时不调用 call。"""
    return invoke_named("llm", call, label="模型", sleeper=sleeper, jitter=jitter)


def stream_model(
    open_stream: Callable[[], Iterator[Any]],
    *,
    sleeper: Optional[Callable[[float], None]] = None,
    jitter: Optional[Callable[[], float]] = None,
) -> Iterator[Any]:
    """流式调用。已经吐出内容后不再重试，避免把同一段话再发一遍。"""
    if _circuit.blocked():
        raise LLMUnavailable("模型连续失败，已暂时熔断，请稍后再试。")
    sleep = sleeper if sleeper is not None else time.sleep
    sample = jitter if jitter is not None else _sample_jitter
    last: Optional[BaseException] = None
    for attempt in range(_MODEL_ATTEMPTS):
        yielded = False
        try:
            for chunk in open_stream():
                yielded = True
                yield chunk
        except TypeError:
            raise
        except Exception as exc:
            last = exc
            if yielded or attempt + 1 >= _MODEL_ATTEMPTS:
                _circuit.failure()
                raise
            sleep(_backoff_seconds(attempt, sample()))
            continue
        else:
            _circuit.success()
            return
    raise last or LLMUnavailable("模型调用失败")


async def ainvoke_model(
    call: Callable[[], Any],
    *,
    sleeper: Optional[Callable[[float], Any]] = None,
    jitter: Optional[Callable[[], float]] = None,
) -> Any:
    """异步调用。sleeper 可以是协程函数。"""
    if _circuit.blocked():
        raise LLMUnavailable("模型连续失败，已暂时熔断，请稍后再试。")

    async def default_sleep(seconds: float) -> None:
        await asyncio.sleep(seconds)

    sleep = sleeper if sleeper is not None else default_sleep
    sample = jitter if jitter is not None else _sample_jitter
    last: Optional[BaseException] = None
    for attempt in range(_MODEL_ATTEMPTS):
        try:
            result = await call()
        except TypeError:
            raise
        except Exception as exc:
            last = exc
            if attempt + 1 >= _MODEL_ATTEMPTS:
                _circuit.failure()
                raise
            waited = sleep(_backoff_seconds(attempt, sample()))
            if asyncio.iscoroutine(waited):
                await waited
        else:
            _circuit.success()
            return result
    raise last or LLMUnavailable("模型调用失败")


class ResilientLLM:
    """包住 ChatOpenAI 或 bind_tools 之后的 Runnable。"""

    def __init__(self, inner: Any):
        self._inner = inner

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return invoke_model(lambda: self._inner.invoke(*args, **kwargs))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await ainvoke_model(lambda: self._inner.ainvoke(*args, **kwargs))

    def stream(self, *args: Any, **kwargs: Any) -> Iterator[Any]:
        return stream_model(lambda: self._inner.stream(*args, **kwargs))

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ResilientLLM":
        return ResilientLLM(self._inner.bind_tools(tools, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


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


def get_llm(temperature: float = None, max_tokens: int = None) -> ResilientLLM:
    """获取通义千问实例。超时 60 秒；重试和熔断由外层负责，客户端不再重试。"""
    api_key = get_api_key()
    temp = temperature if temperature is not None else LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else MAX_TOKENS

    client = ChatOpenAI(
        model=LLM_MODEL,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=temp,
        max_tokens=tokens,
        request_timeout=60,
        max_retries=0,
        stream_usage=True,
    )
    return ResilientLLM(client)


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
