"""
看板数据聚合存储层。
为 GET /v1/dashboard/summary 提供高效的一次性 SQL 聚合查询。
严格保证：
1. 跨用户数据隔离（runs 关联 sessions 过滤）。
2. SQLite 空表防 NULL（COALESCE 处理）。
3. 标量子查询消灭多表 JOIN 笛卡尔积。
4. 容错降级，缺失数据安全返回默认零值。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH
from backend.platform.chat_store import init_chat_db
from backend.platform.domain_store import init_domain_db
from backend.platform.mistake_store import init_mistake_db
from backend.platform.trace_store import init_trace_db
from backend.platform.eval_runner import ensure_eval_tables


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ensure_tables(path: Path) -> None:
    """保证基础表存在，防止空库查询抛 no such table 错误。"""
    try:
        init_domain_db(path)
        init_chat_db(path)
        init_mistake_db(path)
        init_trace_db(path)
        ensure_eval_tables(path)
    except Exception:
        pass


def get_dashboard_summary(
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = Path(db_path or TRACE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_tables(path)
    now_iso = _utc_now()

    summary: Dict[str, Any] = {
        "user_id": user_id,
        "generated_at": now_iso,
        "overview": {
            "session_count": 0,
            "message_count": 0,
            "document_count": 0,
        },
        "mistakes": {
            "total": 0,
            "pending": 0,
            "confirmed": 0,
            "dismissed": 0,
            "due_today": 0,
        },
        "mastery": {
            "total_concepts": 0,
            "average_score": 0.0,
            "distribution": {
                "low": 0,
                "medium": 0,
                "high": 0,
            },
        },
        "recent_runs": [],
        "latest_evaluation": None,
    }

    if not path.exists():
        return summary

    with _connect(path) as conn:
        # 1. Overview: 标量子查询消灭笛卡尔积
        try:
            cur = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM sessions WHERE user_id = :user_id) AS session_count,
                    (SELECT COUNT(*) FROM messages m INNER JOIN sessions s ON m.session_id = s.id WHERE s.user_id = :user_id) AS message_count,
                    (SELECT COUNT(*) FROM documents WHERE user_id = :user_id) AS document_count
                """,
                {"user_id": user_id},
            )
            row = cur.fetchone()
            if row:
                summary["overview"]["session_count"] = int(row["session_count"] or 0)
                summary["overview"]["message_count"] = int(row["message_count"] or 0)
                summary["overview"]["document_count"] = int(row["document_count"] or 0)
        except sqlite3.OperationalError:
            pass

        # 2. Mistakes: 单次扫描聚合，COALESCE 拦截空表 NULL
        try:
            cur = conn.execute(
                """
                SELECT 
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) AS pending,
                    COALESCE(SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END), 0) AS confirmed,
                    COALESCE(SUM(CASE WHEN status = 'dismissed' THEN 1 ELSE 0 END), 0) AS dismissed,
                    COALESCE(SUM(CASE WHEN status = 'confirmed' AND next_review_at IS NOT NULL AND next_review_at <= :utc_now THEN 1 ELSE 0 END), 0) AS due_today
                FROM mistakes
                WHERE user_id = :user_id
                """,
                {"user_id": user_id, "utc_now": now_iso},
            )
            row = cur.fetchone()
            if row:
                summary["mistakes"]["total"] = int(row["total"] or 0)
                summary["mistakes"]["pending"] = int(row["pending"] or 0)
                summary["mistakes"]["confirmed"] = int(row["confirmed"] or 0)
                summary["mistakes"]["dismissed"] = int(row["dismissed"] or 0)
                summary["mistakes"]["due_today"] = int(row["due_today"] or 0)
        except sqlite3.OperationalError:
            pass

        # 3. Mastery: 均值与分桶分布单次扫描
        try:
            cur = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_concepts,
                    COALESCE(AVG(score), 0.0) AS average_score,
                    COALESCE(SUM(CASE WHEN score < 0.4 THEN 1 ELSE 0 END), 0) AS low_count,
                    COALESCE(SUM(CASE WHEN score >= 0.4 AND score < 0.75 THEN 1 ELSE 0 END), 0) AS medium_count,
                    COALESCE(SUM(CASE WHEN score >= 0.75 THEN 1 ELSE 0 END), 0) AS high_count
                FROM mastery
                WHERE user_id = :user_id
                """,
                {"user_id": user_id},
            )
            row = cur.fetchone()
            if row:
                summary["mastery"]["total_concepts"] = int(row["total_concepts"] or 0)
                summary["mastery"]["average_score"] = round(float(row["average_score"] or 0.0), 2)
                summary["mastery"]["distribution"]["low"] = int(row["low_count"] or 0)
                summary["mastery"]["distribution"]["medium"] = int(row["medium_count"] or 0)
                summary["mastery"]["distribution"]["high"] = int(row["high_count"] or 0)
        except sqlite3.OperationalError:
            pass

        # 4. Recent Runs: 严格通过 INNER JOIN sessions 隔离用户数据
        try:
            cur = conn.execute(
                """
                SELECT r.id, r.session_id, r.user_input, r.status, r.latency_ms, r.model, r.cost_yuan, r.created_at
                FROM runs r
                INNER JOIN sessions s ON r.session_id = s.id
                WHERE s.user_id = :user_id
                ORDER BY r.created_at DESC, r.rowid DESC
                LIMIT 5
                """,
                {"user_id": user_id},
            )
            runs = []
            for r in cur.fetchall():
                prompt_preview = (r["user_input"] or "")[:50]
                runs.append({
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "prompt_preview": prompt_preview,
                    "status": r["status"] or "unknown",
                    "latency_ms": int(r["latency_ms"] or 0),
                    "model": r["model"] or "",
                    "cost_yuan": round(float(r["cost_yuan"] or 0.0), 4),
                    "created_at": r["created_at"],
                })
            summary["recent_runs"] = runs
        except sqlite3.OperationalError:
            pass

        # 5. Latest Evaluation: 评测摘要与通过率计算
        try:
            cur = conn.execute(
                """
                SELECT id, dataset_name, dataset_version, mode, status, sample_count, passed, summary_json, started_at, finished_at
                FROM eval_runs
                ORDER BY COALESCE(finished_at, started_at) DESC, rowid DESC
                LIMIT 1
                """
            )
            erow = cur.fetchone()
            if erow:
                sample_count = int(erow["sample_count"] or 0)
                passed = int(erow["passed"] or 0)
                pass_rate = round(passed / sample_count, 4) if sample_count > 0 else 0.0

                summary_obj = {}
                if erow["summary_json"]:
                    try:
                        summary_obj = json.loads(erow["summary_json"])
                    except (json.JSONDecodeError, TypeError):
                        summary_obj = {}

                summary["latest_evaluation"] = {
                    "id": erow["id"],
                    "dataset_name": erow["dataset_name"] or "",
                    "dataset_version": erow["dataset_version"] or "",
                    "mode": erow["mode"] or "",
                    "status": erow["status"] or "",
                    "sample_count": sample_count,
                    "passed": passed,
                    "pass_rate": pass_rate,
                    "summary": summary_obj,
                    "started_at": erow["started_at"] or "",
                    "finished_at": erow["finished_at"] or "",
                }
        except sqlite3.OperationalError:
            pass

    return summary
