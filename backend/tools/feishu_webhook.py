"""飞书自定义机器人。只有配置了 REVIEW_WEBHOOK_URL 才会发请求。"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable, Optional


def build_feishu_payload(text: str) -> dict:
    return {"msg_type": "text", "content": {"text": text}}


def post_feishu_text(url: str, text: str, timeout_s: int = 10) -> None:
    payload = json.dumps(build_feishu_payload(text), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    from backend.llm_helper import invoke_named

    def _post() -> str:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return response.read().decode("utf-8", errors="replace")

    raw = invoke_named("feishu", _post, label="飞书")
    if not raw:
        return
    data = json.loads(raw)
    code = data.get("code", data.get("StatusCode", 0))
    if code not in (0, None):
        raise RuntimeError(data.get("msg") or data.get("StatusMessage") or raw)


def sender_from_env() -> Optional[Callable[[str], None]]:
    url = os.getenv("REVIEW_WEBHOOK_URL", "").strip()
    if not url:
        return None

    def send(body: str) -> None:
        post_feishu_text(url, body)

    return send
