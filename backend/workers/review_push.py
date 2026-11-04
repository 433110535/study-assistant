"""
到期复习的独立入口。用系统计划任务每天跑一次，不要放进 Streamlit 进程。

示例：
    python -m backend.workers.review_push --user student
配置 REVIEW_WEBHOOK_URL 后才会请求飞书；否则只写入本地发件箱。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from backend.platform.review_planner import run_review_push
from backend.tools.feishu_webhook import sender_from_env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成当天的复习卡片")
    parser.add_argument("--user", default="student", help="学习记录所属用户")
    parser.add_argument("--db", default="", help="SQLite 路径，默认 data/app.db")
    parser.add_argument("--now", default="", help="ISO 时间，缺省为当前 UTC")
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    db_path = Path(args.db) if args.db else None
    result = run_review_push(
        args.user,
        now=now,
        db_path=db_path,
        sender=sender_from_env(),
    )
    if result["body"]:
        print(result["body"])
    else:
        print(result["reason"] or "none_due")
    if result["status"] == "failed":
        print(result["error"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
