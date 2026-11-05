"""本机 SQLite 的整库复制。用 sqlite3.backup，避免复制到写了一半的文件。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


def copy_database(source: Path, dest: Path) -> Path:
    """把 source 的当前内容复制到 dest。dest 已存在时会被这次内容覆盖。"""
    src = Path(source)
    target = Path(dest)
    if not src.is_file():
        raise FileNotFoundError(f"数据库不存在: {src}")
    target.parent.mkdir(parents=True, exist_ok=True)
    origin = sqlite3.connect(src)
    replica = sqlite3.connect(target)
    try:
        try:
            origin.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass
        origin.backup(replica)
    finally:
        replica.close()
        origin.close()
    return target


def backup_database(source: Path, dest: Optional[Path] = None) -> Path:
    """热备份源数据库到指定路径或默认备份目录。"""
    src = Path(source)
    if dest is None:
        dest = src.parent / "backups" / f"{src.stem}_backup{src.suffix}"
    return copy_database(src, dest)


def restore_database(backup: Path, target: Path) -> Path:
    """从备份文件恢复到目标数据库。"""
    return copy_database(backup, target)


def count_database_records(db_path: Path) -> Dict[str, int]:
    """统计数据库中各核心业务表的记录数。"""
    counts = {}
    with sqlite3.connect(str(db_path)) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (tname,) in tables:
            try:
                c = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
                counts[tname] = c
            except Exception:
                pass
    return counts
