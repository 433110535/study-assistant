"""
复习的常驻调度。不要放进 Streamlit 进程。

每天北京时间 8:00 调用一次 review_push。同一天重复启动不会再跑。
没有飞书 webhook 和 SMTP 时，review_push 只写本地发件箱。

    python -m backend.workers.review_scheduler --user student
    python -m backend.workers.review_scheduler --once
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from backend.platform.review_planner import run_review_push
from backend.tools.feishu_webhook import sender_from_env
from backend.tools.smtp_mail import sender_from_env as mailer_from_env

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_HOUR = 8
Push = Callable[[datetime], dict]


def next_wake(now: datetime, hour: int = DEFAULT_HOUR) -> datetime:
    """下一次应当醒来的北京时间。已过今天的钟点则是明天。"""
    local = _as_shanghai(now)
    slot = _slot(local, hour)
    if local < slot:
        return slot
    return slot + timedelta(days=1)


def should_run(now: datetime, last_local_date, hour: int = DEFAULT_HOUR) -> bool:
    """今天的钟点已到，且这一天还没跑过。"""
    local = _as_shanghai(now)
    if last_local_date == local.date():
        return False
    return local >= _slot(local, hour)


def tick(now: datetime, last_local_date, push: Push, hour: int = DEFAULT_HOUR) -> dict:
    """到点就调用 push 一次。返回是否跑过、记到哪一天、下次醒来时间。"""
    wake = next_wake(now, hour)
    if not should_run(now, last_local_date, hour):
        return {"ran": False, "last_local_date": last_local_date, "next_wake": wake, "result": None}
    result = push(now)
    local_date = _as_shanghai(now).date()
    return {
        "ran": True,
        "last_local_date": local_date,
        "next_wake": next_wake(now, hour),
        "result": result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="每天北京时间 8:00 生成复习卡片")
    parser.add_argument("--user", default="student")
    parser.add_argument("--db", default="")
    parser.add_argument("--now", default="", help="只用于 --once 的 ISO 时间")
    parser.add_argument("--hour", type=int, default=DEFAULT_HOUR)
    parser.add_argument("--once", action="store_true", help="只判断一次，不常驻")
    args = parser.parse_args(argv)

    db_path = Path(args.db) if args.db else None
    sender = sender_from_env()
    mailer = mailer_from_env()

    def push(moment: datetime) -> dict:
        return run_review_push(
            args.user,
            now=moment,
            db_path=db_path,
            sender=sender,
            mailer=mailer,
        )

    if args.once:
        moment = _parse_now(args.now)
        outcome = tick(moment, None, push, hour=args.hour)
        _print_outcome(outcome)
        return _exit_code(outcome)

    last = None
    while True:
        moment = datetime.now(timezone.utc)
        outcome = tick(moment, last, push, hour=args.hour)
        if outcome["ran"]:
            last = outcome["last_local_date"]
            _print_outcome(outcome)
        delay = (outcome["next_wake"].astimezone(timezone.utc) - moment).total_seconds()
        time.sleep(max(delay, 1))


def _print_outcome(outcome: dict) -> None:
    result: Optional[dict] = outcome.get("result")
    if not result:
        return
    if result.get("body"):
        print(result["body"])
    else:
        print(result.get("reason") or "none_due")


def _exit_code(outcome: dict) -> int:
    result = outcome.get("result") or {}
    if result.get("status") == "failed":
        print(result.get("error") or "", file=sys.stderr)
        return 1
    return 0


def _parse_now(text: str) -> datetime:
    if not text:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _as_shanghai(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(SHANGHAI)


def _slot(local: datetime, hour: int) -> datetime:
    return local.replace(hour=hour, minute=0, second=0, microsecond=0)


if __name__ == "__main__":
    raise SystemExit(main())
