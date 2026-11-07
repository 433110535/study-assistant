"""问答页识图预览：先识别，再决定要不要回填修正框。
[Deprecated/Legacy UI] 优先通过 backend.api.local_client 标准 API 访问 OCR 接口。
"""
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
    """把图片字节交给 OCR 接口。支持注入 reader 测试替身。"""
    if not raw:
        return "图片是空的，无法识别。"
    safe = suffix.lower() if suffix.lower() in _ALLOWED_SUFFIXES else ".jpg"
    if reader is not None:
        handle, name = tempfile.mkstemp(suffix=safe)
        os.close(handle)
        path = Path(name)
        try:
            path.write_bytes(raw)
            return reader(str(path))
        finally:
            path.unlink(missing_ok=True)

    # 只走统一 API 契约，不再在页面进程内直连 vision
    try:
        from backend.api.local_client import ocr_image_api

        res = ocr_image_api(raw, filename=f"image{safe}")
        return str(res.get("text") or "")
    except Exception as e:
        return f"识图失败: {e}"


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
