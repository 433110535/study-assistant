"""
Web 会话持久化：web_sessions 写入与 trace 相同的 SQLite 文件。
对齐说明/PLAN.md 第 12.4 节 F1 登录态规格。
"""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import TRACE_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_auth_db(db_path: Optional[Path] = None) -> None:
    path = Path(db_path or TRACE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS web_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_web_sessions_user ON web_sessions(user_id);
            """
        )
        conn.commit()


def create_web_session(
    user_id: str,
    token: str,
    ttl_seconds: int = 86400 * 7,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    init_auth_db(path)
    token_hash = _hash_token(token)
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    created_at = now_dt.isoformat()
    expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO web_sessions (token_hash, user_id, created_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(token_hash) DO UPDATE SET
                user_id=excluded.user_id,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at,
                revoked_at=NULL
            """,
            (token_hash, user_id, created_at, expires_at),
        )
        conn.commit()
    return {"token_hash": token_hash, "user_id": user_id, "created_at": created_at, "expires_at": expires_at}


def get_web_session(
    token: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    path = Path(db_path or TRACE_DB_PATH)
    init_auth_db(path)
    token_hash = _hash_token(token)
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT token_hash, user_id, created_at, expires_at, revoked_at
            FROM web_sessions
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (token_hash,),
        ).fetchone()
    if row is None:
        return None
    now_str = _utc_now()
    if row["expires_at"] <= now_str:
        return None
    return dict(row)


def revoke_web_session(
    token: str,
    db_path: Optional[Path] = None,
) -> bool:
    if not token:
        return False
    path = Path(db_path or TRACE_DB_PATH)
    init_auth_db(path)
    token_hash = _hash_token(token)
    now_str = _utc_now()
    with _connect(path) as conn:
        cursor = conn.execute(
            """
            UPDATE web_sessions
            SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (now_str, token_hash),
        )
        conn.commit()
        return cursor.rowcount > 0
