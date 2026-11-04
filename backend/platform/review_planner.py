"""
主动复习：读已确认错题，按 SM-2 改下次时间，并把当天卡片写入发件箱。

同一用户、同一北京时间日期只保留一张卡片。外发由调用方传入 sender；
不传时只落本地，不访问网络。
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.config import TRACE_DB_PATH
from backend.platform.mistake_store import init_mistake_db
from backend.tools.review_schedule import (
    format_morning_card,
    parse_reschedule,
    schedule_after_review,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
Sender = Callable[[str], None]


def get_learning_state(
    user_id: str,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """返回已经确认、且下次复习时间不晚于 now 的错题。"""
    path = _prepare(db_path)
    as_of = _as_utc(now or datetime.now(timezone.utc))
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM mistakes
            WHERE user_id = ? AND status = 'confirmed'
            ORDER BY next_review_at ASC
            """,
            (user_id,),
        ).fetchall()
    due = []
    for row in rows:
        review_at = _parse_dt(row["next_review_at"])
        if review_at is not None and review_at <= as_of:
            due.append(dict(row))
    return {"user_id": user_id, "as_of": _iso(as_of), "due": due}


def record_review(
    mistake_id: str,
    quality: int,
    reviewed_at: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """对已确认错题记一次回忆质量。待确认或不存在时返回空字典。"""
    path = _prepare(db_path)
    when = _as_utc(reviewed_at or datetime.now(timezone.utc))
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
        if row is None or row["status"] != "confirmed":
            return {}
        scheduled = schedule_after_review(
            quality=quality,
            repetitions=int(row["repetitions"] or 0),
            ease=float(row["ease"] if row["ease"] is not None else 2.5),
            interval_days=int(row["interval_days"] or 0),
        )
        review_count = int(row["review_count"] or 0) + 1
        next_review_at = _iso(when + timedelta(days=scheduled["interval_days"]))
        conn.execute(
            """
            UPDATE mistakes
            SET ease = ?, interval_days = ?, repetitions = ?,
                review_count = ?, next_review_at = ?
            WHERE id = ? AND status = 'confirmed'
            """,
            (
                scheduled["ease"],
                scheduled["interval_days"],
                scheduled["repetitions"],
                review_count,
                next_review_at,
                mistake_id,
            ),
        )
        conn.commit()
    return {
        "id": mistake_id,
        "ease": scheduled["ease"],
        "interval_days": scheduled["interval_days"],
        "repetitions": scheduled["repetitions"],
        "review_count": review_count,
        "next_review_at": next_review_at,
    }


def reschedule(
    mistake_id: str,
    when_text: str,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """只改下次复习时间，不动 SM-2 的难度和次数。"""
    path = _prepare(db_path)
    current = _as_utc(now or datetime.now(timezone.utc))
    try:
        target = parse_reschedule(when_text, current)
    except ValueError:
        return False
    with _connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE mistakes
            SET next_review_at = ?
            WHERE id = ? AND status = 'confirmed'
            """,
            (_iso(target), mistake_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_outbox(user_id: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _prepare(db_path)
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM review_outbox
            WHERE user_id = ?
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def run_review_push(
    user_id: str,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
    sender: Optional[Sender] = None,
) -> Dict[str, Any]:
    """生成当天晨间卡片。已成功保存或发送过的日期不会再写第二张。"""
    as_of = _as_utc(now or datetime.now(timezone.utc))
    state = get_learning_state(user_id, now=as_of, db_path=db_path)
    if not state["due"]:
        return _result(sent=False, reason="none_due")

    body = format_morning_card(state["due"])
    dedupe_key = f"{user_id}:{as_of.astimezone(SHANGHAI).date().isoformat()}"
    path = _prepare(db_path)
    with _connect(path) as conn:
        existing = conn.execute(
            "SELECT * FROM review_outbox WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        if existing is not None and existing["status"] in {"stored", "sent"}:
            return _result(
                sent=True,
                reason="already_delivered",
                body=existing["body"],
                channel=existing["channel"],
                status=existing["status"],
                error=existing["error"] or "",
                count=len(state["due"]),
            )

        channel = "feishu" if sender is not None else "local"
        status = "stored"
        error = ""
        if sender is not None:
            try:
                sender(body)
                status = "sent"
            except Exception as exc:
                status = "failed"
                error = str(exc)

        created_at = _iso(as_of)
        if existing is None:
            conn.execute(
                """
                INSERT INTO review_outbox (
                    id, user_id, dedupe_key, body, status, channel, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    dedupe_key,
                    body,
                    status,
                    channel,
                    error,
                    created_at,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE review_outbox
                SET body = ?, status = ?, channel = ?, error = ?
                WHERE dedupe_key = ?
                """,
                (body, status, channel, error, dedupe_key),
            )
        conn.commit()

    reason = "failed" if status == "failed" else "delivered"
    return _result(
        sent=status in {"stored", "sent"},
        reason=reason,
        body=body,
        channel=channel,
        status=status,
        error=error,
        count=len(state["due"]),
    )


def _prepare(db_path: Optional[Path]) -> Path:
    path = Path(db_path or TRACE_DB_PATH)
    init_mistake_db(path)
    with _connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_outbox (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                dedupe_key TEXT NOT NULL UNIQUE,
                body TEXT NOT NULL,
                status TEXT NOT NULL,
                channel TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    return path


def _result(
    sent: bool,
    reason: str,
    body: str = "",
    channel: str = "",
    status: str = "",
    error: str = "",
    count: int = 0,
) -> Dict[str, Any]:
    return {
        "sent": sent,
        "reason": reason,
        "body": body,
        "channel": channel,
        "status": status,
        "error": error,
        "count": count,
    }


def _iso(moment: datetime) -> str:
    return _as_utc(moment).replace(microsecond=0).isoformat()


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
