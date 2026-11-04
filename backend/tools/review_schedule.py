"""
SM-2 复习间隔与晨间卡片文案。纯函数，不访问数据库或网络。

间隔按复习前的难度系数计算，系数在间隔确定之后再更新。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
EVENING_HOUR = 20


def schedule_after_review(
    quality: int,
    repetitions: int,
    ease: float,
    interval_days: int,
) -> Dict[str, Any]:
    """根据一次回忆质量更新 SM-2 状态。quality 取 0–5，低于 3 视为没记住。"""
    quality = max(0, min(5, int(quality)))
    repetitions = int(repetitions)
    ease = float(ease)
    interval_days = int(interval_days)

    if quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        if repetitions <= 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = max(1, int(round(interval_days * ease)))
        repetitions += 1

    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease < 1.3:
        ease = 1.3

    return {
        "quality": quality,
        "repetitions": repetitions,
        "ease": ease,
        "interval_days": interval_days,
    }


def format_morning_card(due_items: List[Dict[str, Any]]) -> str:
    """把到期错题收成一张可发送的晨间卡片。没有到期项时返回空字符串。"""
    if not due_items:
        return ""
    lines = [f"晨间复习 {len(due_items)} 题"]
    for index, item in enumerate(due_items, start=1):
        concept = (item.get("concept") or "未命名考点").strip()
        subject = (item.get("subject") or "未分科").strip()
        question = (item.get("question_text") or "").strip()
        lines.append(f"{index}. {concept} · {subject}")
        if question:
            lines.append(f"   {question}")
    lines.append("回复「推到晚上」可改到当天 20:00（北京时间）。")
    return "\n".join(lines)


def parse_reschedule(when_text: str, now: datetime) -> datetime:
    """把「推到晚上」或 ISO 时间解析成 UTC。无法识别时抛出 ValueError。"""
    text = (when_text or "").strip()
    if not text:
        raise ValueError("缺少改期时间")

    current = _as_utc(now)
    if "晚上" in text:
        local_now = current.astimezone(SHANGHAI)
        evening = local_now.replace(hour=EVENING_HOUR, minute=0, second=0, microsecond=0)
        if evening <= local_now:
            evening = evening + timedelta(days=1)
        return evening.astimezone(timezone.utc).replace(microsecond=0)

    if text in {"明天", "推迟一天", "推到明天"}:
        return (current + timedelta(days=1)).replace(microsecond=0)

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("无法识别的改期时间，可以说「推到晚上」或给出 ISO 时间") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _as_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)
