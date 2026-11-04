"""
ReAct Agent 数据模型
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ReActEventType(str, Enum):
    """ReAct 事件类型"""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER_CHUNK = "answer_chunk"      # 流式最终回答的一个片段
    FINAL_ANSWER = "final_answer"      # 完整最终回答（流结束）
    ERROR = "error"


class ReActEvent(BaseModel):
    """ReAct 循环产生的单个事件，由 react_stream() 逐个 yield"""
    event_type: ReActEventType
    content: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = {}
    tool_result: str = ""
    iteration: int = 0


class ReActStep(BaseModel):
    """单个 ReAct 步骤，用于可视化页面展示"""
    iteration: int
    event_type: ReActEventType
    content: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = {}
    tool_result_preview: str = ""


class ReActResult(BaseModel):
    """一次完整的 ReAct 运行结果，存储在 session_state 中"""
    user_input: str = ""
    final_answer: str = ""
    steps: List[ReActStep] = []
    total_iterations: int = 0
    tools_used: List[str] = []
    success: bool = True
    trace_id: str = ""
