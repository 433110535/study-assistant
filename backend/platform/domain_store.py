"""
领域数据持久化：users / documents / mastery 写入统一的 SQLite 数据库。
对齐说明/PLAN.md 第 4.2 节最小表集与 M2、M7 验收标准。
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH
from backend.platform.trace_store import TraceRun


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_domain_db(db_path: Optional[Path] = None) -> None:
    """初始化 users、documents、mastery 三张表并插入默认学生用户。"""
    path = Path(db_path or TRACE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'student',
                title TEXT NOT NULL,
                path TEXT NOT NULL,
                subject TEXT DEFAULT '未分类',
                chunks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS mastery (
                user_id TEXT NOT NULL DEFAULT 'student',
                concept TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT NOT NULL,
                PRIMARY KEY (user_id, concept),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
            CREATE INDEX IF NOT EXISTS idx_mastery_user ON mastery(user_id);
            """
        )
        # 确保默认用户存在
        now = _utc_now()
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, username, created_at)
            VALUES (?, ?, ?)
            """,
            ("student", "student", now),
        )
        conn.commit()


# =======================================================
# 用户管理
# =======================================================

def upsert_user(user_id: str, username: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    init_domain_db(path)
    now = _utc_now()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET username=excluded.username
            """,
            (user_id, username, now),
        )
        conn.commit()
    return {"id": user_id, "username": username, "created_at": now}


def get_user(user_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    init_domain_db(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# =======================================================
# 知识库文档元数据管理
# =======================================================

def add_document_record(
    doc_id: str,
    title: str,
    path: str = "",
    subject: str = "未分类",
    chunks: int = 0,
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """向 documents 表写入一条文档记录。"""
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    now = _utc_now()
    with _connect(db) as conn:
        conn.execute(
            """
            INSERT INTO documents (id, user_id, title, path, subject, chunks, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                path=excluded.path,
                subject=excluded.subject,
                chunks=excluded.chunks
            """,
            (doc_id, user_id, title, path, subject, chunks, now),
        )
        conn.commit()
    return {
        "id": doc_id,
        "user_id": user_id,
        "title": title,
        "path": path,
        "subject": subject,
        "chunks": chunks,
        "created_at": now,
    }


def get_document_record(doc_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    with _connect(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def list_document_records(
    user_id: Optional[str] = None,
    subject: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    sql = "SELECT * FROM documents WHERE 1=1"
    params: list = []
    if user_id:
        sql += " AND user_id = ?"
        params.append(user_id)
    if subject:
        sql += " AND subject = ?"
        params.append(subject)
    sql += " ORDER BY created_at DESC"
    with _connect(db) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]


def delete_document_record(
    doc_id: str,
    user_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> bool:
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    sql = "DELETE FROM documents WHERE id = ?"
    params: list = [doc_id]
    if user_id:
        sql += " AND user_id = ?"
        params.append(user_id)
    with _connect(db) as conn:
        cur = conn.execute(sql, tuple(params))
        conn.commit()
        return cur.rowcount > 0


def sync_legacy_documents(db_path: Optional[Path] = None, kb_save_dir: Optional[str] = None) -> int:
    """若 documents 表为空，从 data/faiss_index/doc_info.pkl 或 doc_info.json 同步历史文档元数据。"""
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    with _connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if count > 0:
            return 0

    save_dir = kb_save_dir or str(db.parent / "faiss_index")
    pkl_path = Path(save_dir) / "doc_info.pkl"
    synced = 0
    if pkl_path.exists():
        try:
            import pickle
            with open(pkl_path, "rb") as f:
                doc_info = pickle.load(f)
            if isinstance(doc_info, dict):
                for doc_id, info in doc_info.items():
                    add_document_record(
                        doc_id=doc_id,
                        title=info.get("title", doc_id),
                        path="",
                        subject=info.get("subject", "未分类"),
                        chunks=info.get("chunk_count", 0),
                        user_id="student",
                        db_path=db,
                    )
                    synced += 1
        except Exception:
            pass
    return synced


# =======================================================
# 掌握度管理 (Mastery)
# =======================================================

def upsert_mastery(
    concept: str,
    is_correct: bool,
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """更新某个知识点的掌握度。"""
    concept = concept.strip()
    if not concept:
        raise ValueError("concept 不能为空")
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    now = _utc_now()
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT score, attempts FROM mastery WHERE user_id = ? AND concept = ?",
            (user_id, concept),
        ).fetchone()
        if row:
            old_score = float(row["score"])
            attempts = int(row["attempts"]) + 1
            if is_correct:
                new_score = min(1.0, round(old_score + 0.15, 4))
            else:
                new_score = max(0.0, round(old_score - 0.20, 4))
        else:
            attempts = 1
            new_score = 0.65 if is_correct else 0.30

        conn.execute(
            """
            INSERT INTO mastery (user_id, concept, score, attempts, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, concept) DO UPDATE SET
                score=excluded.score,
                attempts=excluded.attempts,
                last_seen=excluded.last_seen
            """,
            (user_id, concept, new_score, attempts, now),
        )
        conn.commit()

    return {
        "user_id": user_id,
        "concept": concept,
        "score": new_score,
        "attempts": attempts,
        "last_seen": now,
    }


def get_mastery(concept: str, user_id: str = "student", db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT * FROM mastery WHERE user_id = ? AND concept = ?",
            (user_id, concept),
        ).fetchone()
        return dict(row) if row else None


def list_mastery(user_id: str = "student", db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    db = Path(db_path or TRACE_DB_PATH)
    init_domain_db(db)
    with _connect(db) as conn:
        rows = conn.execute(
            "SELECT * FROM mastery WHERE user_id = ? ORDER BY score ASC, last_seen DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# =======================================================
# 写操作审计 (Audit Logging)
# =======================================================

def log_write_audit(
    action: str,
    details: Dict[str, Any],
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> str:
    """把写操作统一记入 runs 和 tool_calls，满足 M2 写操作可审计。"""
    db = Path(db_path or TRACE_DB_PATH)
    run = TraceRun(
        user_input=f"audit:{action}",
        session_id=f"audit_{user_id}",
        db_path=db,
        model="system",
    )
    run.start()
    run.log_tool_call(
        tool_name=action,
        args=details,
        result="success",
        status="ok",
        latency_ms=0,
    )
    run.finish(f"audit recorded for {action}", iterations=1)
    return run.trace_id
