"""
错题本：写入默认待确认，用户在页面确认后才进入复习队列
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_mistake_db(db_path: Optional[Path] = None) -> None:
    path = Path(db_path or TRACE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS mistakes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                subject TEXT,
                concept TEXT,
                error_type TEXT,
                question_text TEXT,
                student_answer TEXT,
                correct_answer TEXT,
                status TEXT NOT NULL,
                next_review_at TEXT,
                review_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mistakes_user ON mistakes(user_id, status);
            """
        )
        conn.commit()


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_pending(
    user_id: str,
    subject: str,
    concept: str,
    error_type: str,
    question_text: str,
    student_answer: str = "",
    correct_answer: str = "",
    db_path: Optional[Path] = None,
) -> str:
    path = Path(db_path or TRACE_DB_PATH)
    init_mistake_db(path)
    mistake_id = str(uuid.uuid4())
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO mistakes (
                id, user_id, subject, concept, error_type, question_text,
                student_answer, correct_answer, status, review_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?)
            """,
            (
                mistake_id,
                user_id or "student",
                subject.strip(),
                concept.strip(),
                error_type.strip(),
                question_text.strip(),
                student_answer.strip(),
                correct_answer.strip(),
                _utc_now(),
            ),
        )
        conn.commit()
    return mistake_id


def list_mistakes(
    user_id: str,
    status: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_mistake_db(path)
    sql = "SELECT * FROM mistakes WHERE user_id = ?"
    params: list = [user_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    with _connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def confirm_mistake(mistake_id: str, db_path: Optional[Path] = None) -> bool:
    path = Path(db_path or TRACE_DB_PATH)
    init_mistake_db(path)
    review_at = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat()
    with _connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE mistakes
            SET status = 'confirmed', next_review_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (review_at, mistake_id),
        )
        conn.commit()
        return cur.rowcount > 0


def dismiss_mistake(mistake_id: str, db_path: Optional[Path] = None) -> bool:
    path = Path(db_path or TRACE_DB_PATH)
    init_mistake_db(path)
    with _connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE mistakes SET status = 'dismissed'
            WHERE id = ? AND status = 'pending'
            """,
            (mistake_id,),
        )
        conn.commit()
        return cur.rowcount > 0
