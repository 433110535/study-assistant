"""复习调度：每天北京时间 8:00 在页面外跑一次，同一天不重复。"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SHANGHAI = ZoneInfo("Asia/Shanghai")


class TestReviewScheduler(unittest.TestCase):
    def test_before_eight_waits_until_today(self):
        from backend.workers.review_scheduler import next_wake, should_run

        now = datetime(2026, 11, 4, 7, 30, tzinfo=SHANGHAI)
        self.assertEqual(next_wake(now), datetime(2026, 11, 4, 8, 0, tzinfo=SHANGHAI))
        self.assertFalse(should_run(now, None))

    def test_after_eight_runs_once_per_shanghai_day(self):
        from backend.workers.review_scheduler import next_wake, should_run

        now = datetime(2026, 11, 4, 8, 0, tzinfo=SHANGHAI)
        self.assertTrue(should_run(now, None))
        self.assertFalse(should_run(now, now.date()))
        self.assertEqual(next_wake(now), datetime(2026, 11, 5, 8, 0, tzinfo=SHANGHAI))

    def test_tick_calls_push_only_when_due(self):
        from backend.workers.review_scheduler import tick

        seen = []

        def push(now):
            seen.append(now)
            return {"body": "", "status": "stored", "reason": "none_due"}

        early = datetime(2026, 11, 4, 7, 30, tzinfo=SHANGHAI)
        skipped = tick(early, None, push)
        self.assertFalse(skipped["ran"])
        self.assertEqual(seen, [])

        due = datetime(2026, 11, 4, 8, 5, tzinfo=SHANGHAI)
        first = tick(due, None, push)
        second = tick(due, first["last_local_date"], push)
        self.assertTrue(first["ran"])
        self.assertFalse(second["ran"])
        self.assertEqual(len(seen), 1)
        self.assertEqual(first["next_wake"], datetime(2026, 11, 5, 8, 0, tzinfo=SHANGHAI))

    def test_once_cli_does_not_loop_or_call_the_network(self):
        from backend.workers.review_scheduler import main

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "app.db"
        code = main(
            [
                "--user",
                "student",
                "--db",
                str(db),
                "--now",
                "2026-11-04T00:30:00+00:00",
                "--once",
            ]
        )
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
