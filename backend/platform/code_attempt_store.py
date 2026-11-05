"""
代码助教的修改记录。

同一次练习（thread）里每次运行追加一条，方便改完再跑。
不保存沙箱的标准错误全文，避免把源码片段再存一份。
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_thread_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_code_attempt_db(db_path: Optional[Path] = None) -> None:
    path = Path(db_path or TRACE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS code_attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                code TEXT NOT NULL,
                tests TEXT,
                status TEXT NOT NULL,
                exception_type TEXT,
                exception_message TEXT,
                line INTEGER,
                stdout_preview TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_code_attempts_thread
                ON code_attempts(user_id, thread_id, seq);
            """
        )
        conn.commit()


def latest_thread(user_id: str, db_path: Optional[Path] = None) -> Optional[str]:
    path = Path(db_path or TRACE_DB_PATH)
    init_code_attempt_db(path)
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT thread_id FROM code_attempts
            WHERE user_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT 1
            """,
            (user_id or "student",),
        ).fetchone()
    return None if row is None else str(row["thread_id"])


def list_attempts(
    user_id: str,
    thread_id: str,
    db_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_code_attempt_db(path)
    with _connect(path) as conn:
        if limit is not None:
            if limit <= 0:
                return []
            rows = conn.execute(
                """
                SELECT * FROM code_attempts
                WHERE user_id = ? AND thread_id = ?
                ORDER BY seq ASC
                LIMIT ?
                """,
                (user_id or "student", thread_id, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM code_attempts
                WHERE user_id = ? AND thread_id = ?
                ORDER BY seq ASC
                """,
                (user_id or "student", thread_id),
            ).fetchall()
    return [dict(row) for row in rows]


def append_attempt(
    user_id: str,
    thread_id: str,
    code: str,
    tests: str,
    result: Dict[str, Any],
    db_path: Optional[Path] = None,
) -> str:
    path = Path(db_path or TRACE_DB_PATH)
    init_code_attempt_db(path)
    attempt_id = str(uuid.uuid4())
    owner = user_id or "student"
    with _connect(path) as conn:
        current = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM code_attempts WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        seq = int(current[0]) + 1
        stdout = (result.get("stdout") or "")[:500]
        conn.execute(
            """
            INSERT INTO code_attempts (
                id, user_id, thread_id, seq, code, tests, status,
                exception_type, exception_message, line, stdout_preview, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                owner,
                thread_id,
                seq,
                code or "",
                tests or "",
                str(result.get("status") or "error"),
                result.get("exception_type") or "",
                (result.get("exception_message") or "")[:300],
                result.get("line"),
                stdout,
                _utc_now(),
            ),
        )
        conn.commit()
    return attempt_id
