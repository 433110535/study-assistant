"""SM-2 与本地复习卡片。不调用大模型，不发外部消息。"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestReviewPlanner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.now = datetime(2026, 11, 4, 1, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def _confirm(self, concept: str, when: datetime):
        from backend.platform.mistake_store import confirm_mistake, create_pending

        mistake_id = create_pending(
            "student",
            subject="数学",
            concept=concept,
            error_type="计算失误",
            question_text=f"{concept}?",
            db_path=self.db,
        )
        confirm_mistake(mistake_id, db_path=self.db)
        from backend.platform import review_planner as planner

        planner.reschedule(mistake_id, "明天", now=when - timedelta(days=1), db_path=self.db)
        return mistake_id

    def test_sm2_resets_when_forgotten(self):
        from backend.platform.review_planner import sm2_update

        remembered = sm2_update(2.5, 6, 2, 5)
        self.assertGreater(remembered["interval_days"], 6)
        forgotten = sm2_update(2.5, 6, 2, 1)
        self.assertEqual(forgotten["interval_days"], 1)
        self.assertEqual(forgotten["repetitions"], 0)
        self.assertGreaterEqual(sm2_update(1.3, 1, 0, 0)["ease"], 1.3)

    def test_due_and_one_card_per_day(self):
        from backend.platform.review_planner import latest_card, list_due, run_once

        self._confirm("加法", self.now)
        due = list_due("student", now=self.now, db_path=self.db)
        self.assertEqual(len(due), 1)
        first = run_once(user_id="student", now=self.now, db_path=self.db)
        second = run_once(user_id="student", now=self.now, db_path=self.db)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertIn("加法", latest_card("student", self.db)["body"])
        self.assertIn("没有发送", latest_card("student", self.db)["body"])

    def test_apply_review_moves_next_time(self):
        from backend.platform.review_planner import apply_review

        mistake_id = self._confirm("减法", self.now)
        result = apply_review(mistake_id, 5, now=self.now, db_path=self.db)
        self.assertTrue(result["ok"])
        self.assertGreater(result["interval_days"], 0)
        nxt = datetime.fromisoformat(result["next_review_at"])
        self.assertGreater(nxt, self.now)

    def test_reschedule_rejects_unknown_phrase(self):
        from backend.platform.review_planner import reschedule

        mistake_id = self._confirm("乘法", self.now)
        moved = reschedule(mistake_id, "3天后", now=self.now, db_path=self.db)
        self.assertTrue(moved["ok"])
        rejected = reschedule(mistake_id, "下下周", now=self.now, db_path=self.db)
        self.assertFalse(rejected["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
