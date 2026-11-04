"""
工具注册表：schema、执行器与元数据（超时、副作用、成本提示）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., str]
    schema: dict
    side_effects: bool = False
    requires_approval: bool = False
    timeout_s: int = 30
    retries: int = 0
    cost_hint: str = ""


_REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def get_tool_spec(name: str) -> Optional[ToolSpec]:
    return _REGISTRY.get(name)


def get_all_specs() -> List[ToolSpec]:
    return list(_REGISTRY.values())


def get_tool_schemas() -> List[dict]:
    return [spec.schema for spec in _REGISTRY.values()]
