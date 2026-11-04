"""把复习回复解析成改期。飞书事件只取文本，不在这里访问网络。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union


def extract_reply_text(payload: Union[str, Dict[str, Any], None]) -> str:
    """纯文本原样返回。飞书 im.message 事件从 content.text 取出。"""
    if payload is None:
        return ""
    if isinstance(payload, str):
        text = payload.strip()
        if not text.startswith("{"):
            return text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        return extract_reply_text(parsed)
    if not isinstance(payload, dict):
        return ""
    direct = payload.get("text")
    if isinstance(direct, str):
        return direct.strip()
    event = payload.get("event")
    if not isinstance(event, dict):
        return ""
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return content.strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
    return ""


def apply_review_reply(
    user_id: str,
    payload: Union[str, Dict[str, Any], None],
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """把回复应用到当前到期错题。认不出或没有到期题时不改数据库。"""
    from backend.platform.review_planner import get_learning_state, reschedule

    text = extract_reply_text(payload)
    moment = now or datetime.now(timezone.utc)
    try:
        from backend.tools.review_schedule import parse_reschedule

        parse_reschedule(text, moment)
    except ValueError:
        return {"applied": 0, "reason": "unrecognized", "text": text}
    due = get_learning_state(user_id, now=moment, db_path=db_path)["due"]
    if not due:
        return {"applied": 0, "reason": "none_due", "text": text}
    applied = 0
    for item in due:
        if reschedule(item["id"], text, now=moment, db_path=db_path):
            applied += 1
    reason = "rescheduled" if applied else "unchanged"
    return {"applied": applied, "reason": reason, "text": text}
