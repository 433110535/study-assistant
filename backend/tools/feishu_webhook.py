"""飞书自定义机器人。只有配置了 REVIEW_WEBHOOK_URL 才会发请求。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from typing import Callable, Optional


def build_feishu_payload(text: str, secret: str = "", timestamp: Optional[int] = None) -> dict:
    payload: dict = {"msg_type": "text", "content": {"text": text}}
    if secret:
        ts = int(time.time()) if timestamp is None else timestamp
        string_to_sign = f"{ts}\n{secret}"
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        payload["timestamp"] = str(ts)
        payload["sign"] = sign
    return payload


def post_feishu_text(url: str, text: str, timeout_s: int = 10, secret: str = "") -> None:
    payload = json.dumps(build_feishu_payload(text, secret=secret), ensure_ascii=False).encode("utf-8")
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
    secret = (os.getenv("REVIEW_WEBHOOK_SECRET") or os.getenv("FEISHU_SECRET") or "").strip()
    if not url:
        return None

    def send(body: str) -> None:
        post_feishu_text(url, body, secret=secret)

    return send
