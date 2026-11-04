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
from backend.platform.llm_cost import estimate_cost_yuan


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
        _ensure_run_columns(conn)
        conn.commit()


def _ensure_run_columns(conn: sqlite3.Connection) -> None:
    """旧库补上编号、模型和费用。新库的 CREATE TABLE 不带这些列，靠这里补齐。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    if "trace_id" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN trace_id TEXT")
    if "model" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN model TEXT")
    if "token_in" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN token_in INTEGER DEFAULT 0")
    if "token_out" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN token_out INTEGER DEFAULT 0")
    if "cost_yuan" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN cost_yuan REAL")


def get_trace(trace_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """按 trace_id 取一次运行和它的工具调用。没有记录时返回 None。"""
    path = Path(db_path or TRACE_DB_PATH)
    init_trace_db(path)
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
        if row is None:
            return None
        calls = conn.execute(
            """
            SELECT id, tool_name, args_json, result_preview, status, latency_ms, created_at
            FROM tool_calls
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (row["id"],),
        ).fetchall()
    return {"run": dict(row), "tool_calls": [dict(item) for item in calls]}


def get_run(run_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_trace_db(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return None if row is None else dict(row)


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class TraceRun:
    """单次 react_stream 的 trace 上下文"""

    def __init__(
        self,
        user_input: str,
        session_id: str = "default",
        model: str = "",
        db_path: Optional[Path] = None,
    ):
        self.run_id = str(uuid.uuid4())
        self.trace_id = uuid.uuid4().hex
        self.session_id = session_id
        self.user_input = user_input
        self.model = model or ""
        self.db_path = Path(db_path) if db_path else TRACE_DB_PATH
        self.tools_used: List[str] = []
        self.token_in = 0
        self.token_out = 0
        self._started = datetime.now(timezone.utc)

    def add_usage(self, token_in: int, token_out: int) -> None:
        self.token_in += max(0, int(token_in))
        self.token_out += max(0, int(token_out))

    def start(self) -> str:
        init_trace_db(self.db_path)
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, trace_id, session_id, user_input, model,
                    token_in, token_out, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 'running', ?)
                """,
                (
                    self.run_id,
                    self.trace_id,
                    self.session_id,
                    self.user_input,
                    self.model,
                    _utc_now(),
                ),
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
        with _connect(self.db_path) as conn:
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
        cost = estimate_cost_yuan(self.model, self.token_in, self.token_out)
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE runs SET
                    final_answer = ?,
                    iterations = ?,
                    tools_used = ?,
                    latency_ms = ?,
                    status = ?,
                    model = ?,
                    token_in = ?,
                    token_out = ?,
                    cost_yuan = ?
                WHERE id = ?
                """,
                (
                    final_answer[:8000] if final_answer else "",
                    iterations,
                    json.dumps(self.tools_used, ensure_ascii=False),
                    elapsed,
                    status,
                    self.model,
                    self.token_in,
                    self.token_out,
                    cost,
                    self.run_id,
                ),
            )
            conn.commit()


# 模块加载时确保表存在（失败时不阻断主流程）
try:
    init_trace_db()
except OSError:
    pass
