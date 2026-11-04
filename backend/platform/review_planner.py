"""
主动复习：SM-2 间隔、到期列表、本地卡片。

独立脚本运行，不挂在 Streamlit 进程里。
卡片只写入本地表，不发飞书或邮件。
"""
from __future__ import annotations

import argparse
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH
from backend.platform.mistake_store import init_mistake_db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def sm2_update(
    ease: float,
    interval_days: int,
    repetitions: int,
    quality: int,
) -> Dict[str, Any]:
    """SM-2。quality 0–5，低于 3 视为没记住，间隔回到 1 天。"""
    try:
        score = int(quality)
    except (TypeError, ValueError):
        score = 0
    score = min(5, max(0, score))
    factor = float(ease or 2.5)
    interval = max(1, int(interval_days or 1))
    reps = max(0, int(repetitions or 0))
    if score < 3:
        reps = 0
        interval = 1
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = max(1, int(round(interval * factor)))
    factor = factor + (0.1 - (5 - score) * (0.08 + (5 - score) * 0.02))
    factor = max(1.3, factor)
    return {
        "ease": round(factor, 4),
        "interval_days": interval,
        "repetitions": reps,
        "quality": score,
    }


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_review_db(db_path: Optional[Path] = None) -> None:
    path = Path(db_path or TRACE_DB_PATH)
    init_mistake_db(path)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS review_cards (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                card_date TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, card_date)
            );
            """
        )
        conn.commit()


def list_due(
    user_id: str,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_review_db(path)
    moment = (now or _utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    stamp = moment.isoformat()
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM mistakes
            WHERE user_id = ? AND status = 'confirmed'
              AND (next_review_at IS NULL OR next_review_at <= ?)
            ORDER BY next_review_at
            """,
            (user_id or "student", stamp),
        ).fetchall()
    return [dict(row) for row in rows]


def learning_state(
    user_id: str,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    init_review_db(path)
    owner = user_id or "student"
    due = list_due(owner, now=now, db_path=path)
    with _connect(path) as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM mistakes WHERE user_id = ? AND status = 'pending'",
            (owner,),
        ).fetchone()[0]
        confirmed = conn.execute(
            "SELECT COUNT(*) FROM mistakes WHERE user_id = ? AND status = 'confirmed'",
            (owner,),
        ).fetchone()[0]
    return {
        "user_id": owner,
        "pending": int(pending),
        "confirmed": int(confirmed),
        "due": due,
    }


def format_state(state: Dict[str, Any]) -> str:
    due = state.get("due") or []
    lines = [
        f"待确认: {state.get('pending', 0)}",
        f"复习队列: {state.get('confirmed', 0)}",
        f"今日到期: {len(due)}",
    ]
    for item in due:
        lines.append(f"- {item.get('concept') or '未命名考点'}（{item.get('subject') or '未填写'}）")
    if not due:
        lines.append("没有到期错题。不要声称已经发出提醒。")
    return "\n".join(lines)


def format_card(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "今日没有到期错题。"
    lines = [f"今日复习 {len(items)} 题"]
    for index, item in enumerate(items, start=1):
        concept = item.get("concept") or "未命名考点"
        subject = item.get("subject") or "未填写"
        question = (item.get("question_text") or "").strip()
        lines.append(f"{index}. {concept} · {subject}")
        if question:
            lines.append(question)
    lines.append("这是本地卡片，还没有发送到飞书或邮箱。")
    return "\n".join(lines)


def apply_review(
    mistake_id: str,
    quality: int,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    init_review_db(path)
    moment = (now or _utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
        if row is None or row["status"] != "confirmed":
            return {"ok": False, "reason": "只能复习已确认的错题"}
        updated = sm2_update(
            row["ease"] if "ease" in row.keys() else 2.5,
            row["interval_days"] if "interval_days" in row.keys() else 1,
            row["repetitions"] if "repetitions" in row.keys() else 0,
            quality,
        )
        next_at = (moment + timedelta(days=updated["interval_days"])).isoformat()
        conn.execute(
            """
            UPDATE mistakes
            SET ease = ?, interval_days = ?, repetitions = ?,
                next_review_at = ?, review_count = COALESCE(review_count, 0) + 1
            WHERE id = ?
            """,
            (
                updated["ease"],
                updated["interval_days"],
                updated["repetitions"],
                next_at,
                mistake_id,
            ),
        )
        conn.commit()
    updated["ok"] = True
    updated["next_review_at"] = next_at
    updated["mistake_id"] = mistake_id
    return updated


def reschedule(
    mistake_id: str,
    when: str,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    init_review_db(path)
    moment = (now or _utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    target = _resolve_when(when, moment)
    if target is None:
        return {"ok": False, "reason": "只能改到明天、晚上，或若干天后"}
    with _connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE mistakes SET next_review_at = ?
            WHERE id = ? AND status = 'confirmed'
            """,
            (target.isoformat(), mistake_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return {"ok": False, "reason": "只能改期已确认的错题"}
    return {"ok": True, "mistake_id": mistake_id, "next_review_at": target.isoformat()}


def _resolve_when(when: str, now: datetime) -> Optional[datetime]:
    text = (when or "").strip()
    if text in {"明天", "明日"}:
        return now + timedelta(days=1)
    if text == "晚上":
        evening = now.replace(hour=12, minute=0, second=0)  # 北京时间 20:00
        if evening <= now:
            evening = evening + timedelta(days=1)
        return evening
    if text.endswith("天后") and text[:-2].isdigit():
        days = int(text[:-2])
        if 1 <= days <= 30:
            return now + timedelta(days=days)
    return None


def run_once(
    user_id: Optional[str] = None,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """为有到期错题的用户写一张当日卡片。同一天不重复写。"""
    path = Path(db_path or TRACE_DB_PATH)
    init_review_db(path)
    moment = (now or _utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    card_date = moment.date().isoformat()
    with _connect(path) as conn:
        if user_id:
            owners = [user_id]
        else:
            owners = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT user_id FROM mistakes WHERE status = 'confirmed'"
                ).fetchall()
            ]
    planned = []
    for owner in owners:
        due = list_due(owner, now=moment, db_path=path)
        if due:
            planned.append((owner, due))
    written = []
    with _connect(path) as conn:
        for owner, due in planned:
            exists = conn.execute(
                "SELECT id FROM review_cards WHERE user_id = ? AND card_date = ?",
                (owner, card_date),
            ).fetchone()
            if exists:
                continue
            body = format_card(due)
            card_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO review_cards (id, user_id, card_date, body, status, created_at)
                VALUES (?, ?, ?, ?, 'draft', ?)
                """,
                (card_id, owner, card_date, body, moment.isoformat()),
            )
            written.append({"id": card_id, "user_id": owner, "card_date": card_date, "body": body})
        conn.commit()
    return written


def latest_card(
    user_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_review_db(path)
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT * FROM review_cards
            WHERE user_id = ?
            ORDER BY card_date DESC
            LIMIT 1
            """,
            (user_id or "student",),
        ).fetchone()
    return None if row is None else dict(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成今日复习卡片，不发送外部消息")
    parser.add_argument("--user", default="", help="只处理这个用户，默认全部")
    args = parser.parse_args()
    cards = run_once(user_id=args.user or None)
    if not cards:
        print("没有新的复习卡片")
        return
    for card in cards:
        print(f"[{card['user_id']}] {card['card_date']}")
        print(card["body"])
        print("---")


if __name__ == "__main__":
    main()
