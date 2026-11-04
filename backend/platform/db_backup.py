"""本机 SQLite 的整库复制。用 sqlite3.backup，避免复制到写了一半的文件。"""
from __future__ import annotations

import sqlite3
from pathlib import Path


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
        origin.backup(replica)
    finally:
        replica.close()
        origin.close()
    return target
