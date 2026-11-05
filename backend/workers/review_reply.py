"""
把一条复习回复应用到到期错题。不要放进 Streamlit 进程。

单次：
    python -m backend.workers.review_reply --text 推到晚上 --user student

本机 HTTP 只监听 127.0.0.1，不校验飞书签名。真实飞书回调还没接。
配置 REVIEW_REPLY_TOKEN 后，请求必须带同样的 X-Review-Token。
    python -m backend.workers.review_reply --serve --port 8765
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from backend.tools.review_reply import apply_review_reply


import hashlib
import hmac


def verify_feishu_signature(timestamp: str, nonce: str, body: bytes, secret: str, signature: str) -> bool:
    if not secret or not signature:
        return False
    bytes_to_sign = f"{timestamp}{nonce}{secret}".encode("utf-8") + body
    calculated = hashlib.sha256(bytes_to_sign).hexdigest()
    return hmac.compare_digest(calculated, signature)


def process_reply_http(
    body: bytes,
    user_id: str,
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
    token: str = "",
    header_token: str = "",
    feishu_secret: str = "",
    lark_timestamp: str = "",
    lark_nonce: str = "",
    lark_signature: str = "",
) -> tuple:
    # 鉴权优先级：配置了 token 则检验 token；配置了 feishu_secret 则校验飞书签名
    if token and header_token != token:
        return 401, {"applied": 0, "reason": "unauthorized", "text": ""}
    if feishu_secret:
        if not verify_feishu_signature(lark_timestamp, lark_nonce, body, feishu_secret, lark_signature):
            return 401, {"applied": 0, "reason": "unauthorized", "text": ""}
    text = body.decode("utf-8", errors="replace")
    result = apply_review_reply(user_id, text, now=now, db_path=db_path)
    code = 200 if result["reason"] != "unrecognized" else 422
    return code, result


def make_server(
    user_id: str,
    db_path: Optional[Path] = None,
    now: Optional[datetime] = None,
    token: str = "",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b""
            code, result = process_reply_http(
                raw,
                user_id,
                now=now,
                db_path=db_path,
                token=token,
                header_token=self.headers.get("X-Review-Token", ""),
            )
            payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="解析复习回复并改期")
    parser.add_argument("--user", default="student")
    parser.add_argument("--db", default="")
    parser.add_argument("--now", default="")
    parser.add_argument("--text", default="", help="一条回复，例如「推到晚上」")
    parser.add_argument("--serve", action="store_true", help="在 127.0.0.1 接收 POST")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="", help="非空时要求 X-Review-Token")
    args = parser.parse_args(argv)
    if args.serve and args.text:
        print("不要同时使用 --serve 和 --text")
        return 2
    if not args.serve and not args.text:
        print("需要 --text 或 --serve")
        return 2

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    db_path = Path(args.db) if args.db else None
    if args.serve:
        server = make_server(
            args.user,
            db_path=db_path,
            now=now,
            token=args.token,
            port=args.port,
        )
        print(f"复习回复入口 http://127.0.0.1:{server.server_address[1]}/")
        server.serve_forever()
        return 0

    result = apply_review_reply(args.user, args.text, now=now, db_path=db_path)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["reason"] != "unrecognized" else 1


if __name__ == "__main__":
    raise SystemExit(main())
