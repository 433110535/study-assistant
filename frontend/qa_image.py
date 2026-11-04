"""问答页识图预览：先识别，再决定要不要回填修正框。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Callable, MutableMapping, Optional

_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def preview_image_text(
    raw: bytes,
    suffix: str = ".jpg",
    reader: Optional[Callable[[str], str]] = None,
) -> str:
    """把图片字节交给 read_image。临时文件在返回前删除。"""
    if not raw:
        return "图片是空的，无法识别。"
    safe = suffix.lower() if suffix.lower() in _ALLOWED_SUFFIXES else ".jpg"
    if reader is None:
        from backend.tools.vision import read_image

        reader = read_image
    handle, name = tempfile.mkstemp(suffix=safe)
    os.close(handle)
    path = Path(name)
    try:
        path.write_bytes(raw)
        return reader(str(path))
    finally:
        path.unlink(missing_ok=True)


def remember_ocr_preview(
    state: MutableMapping[str, Any],
    source: Any,
    text: str,
) -> bool:
    """同一张图片只回填一次，避免改写用户已经改过的文字。"""
    if state.get("qa_ocr_source") == source:
        return False
    state["qa_ocr_source"] = source
    state["qa_ocr_override"] = text
    return True
