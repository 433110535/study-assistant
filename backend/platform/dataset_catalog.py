"""
评测集版本目录。同一个 name + version 只接受一份文件内容。

哈希是文件原始字节的 SHA-256。再次登记同一文件是空操作；
字节变了就拒绝，必须换版本号。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import TRACE_DB_PATH


def register_file(path: Path, db_path: Optional[Path] = None) -> Dict[str, Any]:
    source = Path(path)
    raw = source.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    record = {
        "dataset_name": str(data.get("name") or ""),
        "version": str(data.get("version") or ""),
        "sample_count": len(data.get("samples") or []),
        "content_hash": hashlib.sha256(raw).hexdigest(),
        "changelog": str(data.get("changelog") or ""),
        "source_path": str(source),
    }
    if not record["dataset_name"] or not record["version"]:
        raise ValueError(f"评测集缺少 name 或 version: {source}")
    _store(record, Path(db_path or TRACE_DB_PATH))
    return record


def list_versions(
    name: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = Path(db_path or TRACE_DB_PATH)
    _init(path)
    sql = "SELECT * FROM dataset_versions"
    params: tuple = ()
    if name:
        sql += " WHERE dataset_name = ?"
        params = (name,)
    sql += " ORDER BY created_at ASC"
    with _connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _store(record: Dict[str, Any], db_path: Path) -> None:
    _init(db_path)
    with _connect(db_path) as conn:
        existing = conn.execute(
            """
            SELECT content_hash FROM dataset_versions
            WHERE dataset_name = ? AND version = ?
            """,
            (record["dataset_name"], record["version"]),
        ).fetchone()
        if existing is not None:
            if existing["content_hash"] != record["content_hash"]:
                raise ValueError(
                    f"数据集 {record['dataset_name']}@{record['version']} 已冻结，"
                    "内容哈希不一致"
                )
            return
        conn.execute(
            """
            INSERT INTO dataset_versions (
                id, dataset_name, version, sample_count, content_hash,
                changelog, source_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                record["dataset_name"],
                record["version"],
                record["sample_count"],
                record["content_hash"],
                record["changelog"],
                record["source_path"],
                datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            ),
        )
        conn.commit()


def _init(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_versions (
                id TEXT PRIMARY KEY,
                dataset_name TEXT NOT NULL,
                version TEXT NOT NULL,
                sample_count INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                changelog TEXT,
                source_path TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(dataset_name, version)
            )
            """
        )
        conn.commit()


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def validate_and_clean_dataset(data: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    """自检并清洗评测集。拦截空问题、缺失必填字段、重复样本ID。返回 (cleaned_dict, issues_list)。"""
    issues = []
    name = str(data.get("name") or "").strip()
    version = str(data.get("version") or "").strip()
    if not name:
        issues.append("缺少 name 字段")
    if not version:
        issues.append("缺少 version 字段")

    raw_samples = data.get("samples") or []
    if not isinstance(raw_samples, list):
        issues.append("samples 必须是列表")
        return data, issues

    cleaned_samples = []
    seen_ids = set()
    for idx, sample in enumerate(raw_samples):
        if not isinstance(sample, dict):
            issues.append(f"第 {idx} 个样本非字典格式")
            continue
        sid = str(sample.get("id") or "").strip()
        query = str(sample.get("query") or sample.get("input") or sample.get("question") or "").strip()
        if not query:
            issues.append(f"样本 {sid or idx} 缺少问题内容")
            continue
        if sid in seen_ids:
            issues.append(f"发现重复样本 ID: {sid}")
            continue
        if sid:
            seen_ids.add(sid)
        cleaned_samples.append(sample)

    cleaned = dict(data)
    cleaned["samples"] = cleaned_samples
    return cleaned, issues
