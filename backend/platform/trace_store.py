"""
SQLite 运行 trace：记录每次 ReAct run 与 tool_call
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_trace_db(db_path: Optional[Path] = None) -> None:
    path = db_path or TRACE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                user_input TEXT NOT NULL,
                final_answer TEXT,
                iterations INTEGER DEFAULT 0,
                tools_used TEXT,
                latency_ms INTEGER,
                status TEXT DEFAULT 'running',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                args_json TEXT,
                result_preview TEXT,
                status TEXT,
                latency_ms INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
            """
        )
        conn.commit()


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


class TraceRun:
    """单次 react_stream 的 trace 上下文"""

    def __init__(self, user_input: str, session_id: str = "default"):
        self.run_id = str(uuid.uuid4())
        self.session_id = session_id
        self.user_input = user_input
        self.tools_used: List[str] = []
        self._started = datetime.now(timezone.utc)

    def start(self) -> str:
        init_trace_db()
        with _connect(TRACE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO runs (id, session_id, user_input, status, created_at)
                VALUES (?, ?, ?, 'running', ?)
                """,
                (self.run_id, self.session_id, self.user_input, _utc_now()),
            )
            conn.commit()
        return self.run_id

    def log_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: str,
        status: str,
        latency_ms: int,
    ) -> None:
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)
        preview = result[:500] + "..." if len(result) > 500 else result
        with _connect(TRACE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO tool_calls
                (run_id, tool_name, args_json, result_preview, status, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id,
                    tool_name,
                    json.dumps(args, ensure_ascii=False),
                    preview,
                    status,
                    latency_ms,
                    _utc_now(),
                ),
            )
            conn.commit()

    def finish(
        self,
        final_answer: str,
        iterations: int,
        status: str = "ok",
    ) -> None:
        elapsed = int(
            (datetime.now(timezone.utc) - self._started).total_seconds() * 1000
        )
        with _connect(TRACE_DB_PATH) as conn:
            conn.execute(
                """
                UPDATE runs SET
                    final_answer = ?,
                    iterations = ?,
                    tools_used = ?,
                    latency_ms = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    final_answer[:8000] if final_answer else "",
                    iterations,
                    json.dumps(self.tools_used, ensure_ascii=False),
                    elapsed,
                    status,
                    self.run_id,
                ),
            )
            conn.commit()


# 模块加载时确保表存在（失败时不阻断主流程）
try:
    init_trace_db()
except OSError:
    pass
