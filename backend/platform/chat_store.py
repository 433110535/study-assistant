"""
问答会话持久化：sessions / messages 写入与 trace 相同的 SQLite 文件
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import TRACE_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_chat_db(db_path: Optional[Path] = None) -> None:
    path = Path(db_path or TRACE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at);
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


def start_session(user_id: str, title: str = "新对话", db_path: Optional[Path] = None) -> str:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    session_id = str(uuid.uuid4())
    now = _utc_now()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_id, title, now, now),
        )
        conn.commit()
    return session_id


def latest_session_id(user_id: str, db_path: Optional[Path] = None) -> Optional[str]:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC, rowid DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return row["id"] if row else None


def ensure_session(user_id: str, db_path: Optional[Path] = None) -> str:
    existing = latest_session_id(user_id, db_path=db_path)
    if existing:
        return existing
    return start_session(user_id, db_path=db_path)


def list_sessions(
    user_id: str,
    limit: int = 20,
    db_path: Optional[Path] = None,
) -> List[Dict[str, str]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, title, updated_at FROM sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC, rowid DESC
            LIMIT ?
            """,
            (user_id or "student", max(1, int(limit))),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"] or "新对话",
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def load_messages(session_id: str, db_path: Optional[Path] = None) -> List[Dict[str, str]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def get_session(session_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def list_sessions_summary(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    with _connect(path) as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?",
            (user_id or "student",),
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) AS message_count
            FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            WHERE s.user_id = ?
            GROUP BY s.id
            ORDER BY s.updated_at DESC, s.rowid DESC
            LIMIT ? OFFSET ?
            """,
            (user_id or "student", max(1, int(limit)), max(0, int(offset))),
        ).fetchall()
    sessions = [
        {
            "id": row["id"],
            "title": row["title"] or "新对话",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": int(row["message_count"]),
        }
        for row in rows
    ]
    return {"sessions": sessions, "total": total}


def load_session_messages_detailed(
    session_id: str,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def append_message(
    session_id: str,
    role: str,
    content: str,
    db_path: Optional[Path] = None,
) -> None:
    text = (content or "").strip()
    if not session_id or not text:
        return
    path = Path(db_path or TRACE_DB_PATH)
    init_chat_db(path)
    now = _utc_now()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, text, now),
        )
        if role == "user":
            row = conn.execute(
                "SELECT title FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            title = (row["title"] if row else "") or ""
            if title in ("", "新对话"):
                title = text.replace("\n", " ")[:40]
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
        conn.commit()

