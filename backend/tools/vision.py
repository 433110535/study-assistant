"""
题目图片识别：压缩、编码并调用 DashScope 视觉模型
"""
from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from backend.config import DASHSCOPE_API_KEY, VISION_MODEL

MAX_LONG_EDGE = 1600
MAX_BYTES = 2 * 1024 * 1024


def _compress_image_bytes(raw: bytes) -> tuple[bytes, str]:
    """长边限制与体积控制，返回 (bytes, mime_subtype)"""
    try:
        from PIL import Image
    except ImportError:
        return raw, "jpeg"

    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGB")
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / long_edge
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    quality = 85
    while quality >= 50:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX_BYTES:
            return data, "jpeg"
        quality -= 10

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50, optimize=True)
    return buf.getvalue(), "jpeg"


def read_image(image_path: str, focus: str = "全部") -> str:
    """
    识别题目图片中的文字与公式，只识别不解答。
    """
    path = Path(image_path)
    if not path.is_file():
        return f"图片不存在或不可读: {image_path}"

    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY.startswith("your_"):
        return (
            "未配置 DASHSCOPE_API_KEY，无法识图。"
            "请在 .env 中设置通义千问 API Key。"
        )

    try:
        raw = path.read_bytes()
        compressed, subtype = _compress_image_bytes(raw)
        b64 = base64.b64encode(compressed).decode()
        data_uri = f"data:image/{subtype};base64,{b64}"
    except OSError as e:
        return f"读取图片失败: {e}"
    except Exception as e:
        return f"图片预处理失败: {e}"

    prompt = (
        f"识别图片中的题目内容（重点：{focus}）。"
        "公式用 LaTeX 表示，保留题号与选项，只输出识别结果，不要解答。"
    )

    try:
        import dashscope
        from dashscope import MultiModalConversation

        dashscope.api_key = DASHSCOPE_API_KEY
        model = os.getenv("VISION_MODEL", VISION_MODEL)
        from backend.llm_helper import invoke_named

        def _call():
            return MultiModalConversation.call(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"image": data_uri},
                            {"text": prompt},
                        ],
                    }
                ],
            )

        resp = invoke_named("vision", _call, label="识图")
    except Exception as e:
        return f"视觉模型调用失败: {e}"

    if getattr(resp, "status_code", None) not in (None, 200):
        code = getattr(resp, "status_code", "unknown")
        msg = getattr(resp, "message", str(resp))
        return f"视觉模型返回错误 (code={code}): {msg}"

    try:
        content = resp.output.choices[0].message.content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    return part["text"].strip()
                if isinstance(part, str):
                    return part.strip()
        if isinstance(content, str):
            return content.strip()
    except (AttributeError, IndexError, KeyError, TypeError):
        pass

    return "未能从模型响应中解析识别文本，请换一张更清晰的图片重试。"
