"""主动复习：SM-2 间隔、到期队列、本地晨间卡片。"""
import io
import contextlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestSm2(unittest.TestCase):
    def test_first_success_waits_one_day(self):
        from backend.tools.review_schedule import schedule_after_review

        state = schedule_after_review(quality=5, repetitions=0, ease=2.5, interval_days=0)
        self.assertEqual(state["interval_days"], 1)
        self.assertEqual(state["repetitions"], 1)
        self.assertAlmostEqual(state["ease"], 2.6, places=2)

    def test_second_success_waits_six_days(self):
        from backend.tools.review_schedule import schedule_after_review

        state = schedule_after_review(quality=4, repetitions=1, ease=2.6, interval_days=1)
        self.assertEqual(state["interval_days"], 6)
        self.assertEqual(state["repetitions"], 2)
        self.assertAlmostEqual(state["ease"], 2.6, places=2)

    def test_later_success_multiplies_previous_interval(self):
        from backend.tools.review_schedule import schedule_after_review

        state = schedule_after_review(quality=5, repetitions=2, ease=2.5, interval_days=6)
        self.assertEqual(state["interval_days"], 15)
        self.assertEqual(state["repetitions"], 3)
        self.assertAlmostEqual(state["ease"], 2.6, places=2)

    def test_failed_recall_resets_to_one_day_and_floors_ease(self):
        from backend.tools.review_schedule import schedule_after_review

        failed = schedule_after_review(quality=2, repetitions=3, ease=2.5, interval_days=15)
        self.assertEqual(failed["interval_days"], 1)
        self.assertEqual(failed["repetitions"], 0)
        self.assertAlmostEqual(failed["ease"], 2.18, places=2)

        floored = schedule_after_review(quality=0, repetitions=1, ease=1.3, interval_days=6)
        self.assertEqual(floored["ease"], 1.3)
        self.assertEqual(floored["interval_days"], 1)
        self.assertEqual(floored["repetitions"], 0)


NOW = datetime(2026, 11, 4, 1, 0, tzinfo=timezone.utc)


class TestMorningCard(unittest.TestCase):
    def test_card_lists_due_questions_without_answers(self):
        from backend.tools.review_schedule import format_morning_card

        card = format_morning_card(
            [
                {
                    "concept": "链式法则",
                    "subject": "数学",
                    "question_text": "求 d/dx sin(x^2)",
                    "correct_answer": "2x cos(x^2)",
                }
            ]
        )
        self.assertEqual(
            card,
            "\n".join(
                [
                    "晨间复习 1 题",
                    "1. 链式法则 · 数学",
                    "   求 d/dx sin(x^2)",
                    "回复「推到晚上」可改到当天 20:00（北京时间）。",
                ]
            ),
        )
        self.assertNotIn("2x cos", card)

    def test_evening_means_20_00_shanghai(self):
        from backend.tools.review_schedule import parse_reschedule

        when = parse_reschedule("推到晚上", NOW)
        self.assertEqual(when, datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc))


class TestReviewPush(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_due(self, concept="链式法则", question="求 d/dx sin(x^2)"):
        from backend.platform.mistake_store import confirm_mistake, create_pending
        from backend.platform.review_planner import reschedule

        mistake_id = create_pending(
            "student",
            subject="数学",
            concept=concept,
            error_type="概念不清",
            question_text=question,
            student_answer="cos(x^2)",
            correct_answer="2x cos(x^2)",
            db_path=self.db,
        )
        self.assertTrue(confirm_mistake(mistake_id, db_path=self.db))
        self.assertTrue(
            reschedule(mistake_id, "2026-11-01T00:00:00+00:00", now=NOW, db_path=self.db)
        )
        return mistake_id

    def test_only_due_confirmed_items_are_listed(self):
        from backend.platform.mistake_store import confirm_mistake, create_pending
        from backend.platform.review_planner import get_learning_state, reschedule

        due_id = self._seed_due()
        pending_id = create_pending(
            "student",
            subject="物理",
            concept="牛顿第二定律",
            error_type="审题错误",
            question_text="2kg 物体受 4N 力",
            db_path=self.db,
        )
        future_id = create_pending(
            "student",
            subject="数学",
            concept="导数定义",
            error_type="计算失误",
            question_text="求极限",
            db_path=self.db,
        )
        self.assertTrue(confirm_mistake(future_id, db_path=self.db))
        self.assertTrue(
            reschedule(future_id, "2026-12-01T00:00:00+00:00", now=NOW, db_path=self.db)
        )

        state = get_learning_state("student", now=NOW, db_path=self.db)
        self.assertEqual([item["id"] for item in state["due"]], [due_id])
        self.assertNotIn(pending_id, [item["id"] for item in state["due"]])

    def test_successful_recall_schedules_the_next_day(self):
        from backend.platform.mistake_store import list_mistakes
        from backend.platform.review_planner import get_learning_state, record_review

        mistake_id = self._seed_due()
        updated = record_review(mistake_id, quality=5, reviewed_at=NOW, db_path=self.db)
        self.assertEqual(updated["interval_days"], 1)
        self.assertEqual(updated["repetitions"], 1)
        self.assertEqual(updated["review_count"], 1)
        self.assertEqual(updated["next_review_at"], "2026-11-05T01:00:00+00:00")
        self.assertAlmostEqual(updated["ease"], 2.6, places=2)

        still_due = get_learning_state("student", now=NOW, db_path=self.db)
        self.assertEqual(still_due["due"], [])
        tomorrow = get_learning_state("student", now=NOW + timedelta(days=1), db_path=self.db)
        self.assertEqual([item["id"] for item in tomorrow["due"]], [mistake_id])

        stored = list_mistakes("student", status="confirmed", db_path=self.db)
        self.assertEqual(stored[0]["next_review_at"], "2026-11-05T01:00:00+00:00")

    def test_pending_item_cannot_be_reviewed(self):
        from backend.platform.mistake_store import create_pending
        from backend.platform.review_planner import record_review

        mistake_id = create_pending(
            "student",
            subject="数学",
            concept="链式法则",
            error_type="概念不清",
            question_text="求 d/dx sin(x^2)",
            db_path=self.db,
        )
        self.assertEqual(
            record_review(mistake_id, quality=5, reviewed_at=NOW, db_path=self.db),
            {},
        )

    def test_push_to_evening_leaves_the_morning_queue(self):
        from backend.platform.review_planner import get_learning_state, reschedule

        mistake_id = self._seed_due()
        self.assertTrue(reschedule(mistake_id, "推到晚上", now=NOW, db_path=self.db))
        morning = get_learning_state("student", now=NOW, db_path=self.db)
        self.assertEqual(morning["due"], [])
        evening = get_learning_state(
            "student",
            now=datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc),
            db_path=self.db,
        )
        self.assertEqual([item["id"] for item in evening["due"]], [mistake_id])

    def test_daily_push_stores_one_local_card(self):
        from backend.platform.review_planner import list_outbox, run_review_push

        self._seed_due()
        first = run_review_push("student", now=NOW, db_path=self.db)
        self._seed_due(concept="换元积分", question="求 ∫2x dx")
        second = run_review_push("student", now=NOW, db_path=self.db)

        self.assertTrue(first["sent"])
        self.assertEqual(first["channel"], "local")
        self.assertEqual(first["status"], "stored")
        self.assertEqual(first["body"], second["body"])
        self.assertIn("晨间复习 1 题", first["body"])
        self.assertIn("链式法则", first["body"])
        self.assertNotIn("换元积分", second["body"])
        cards = list_outbox("student", db_path=self.db)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["status"], "stored")

    def test_nothing_due_writes_no_card(self):
        from backend.platform.review_planner import list_outbox, run_review_push

        result = run_review_push("student", now=NOW, db_path=self.db)
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "none_due")
        self.assertEqual(list_outbox("student", db_path=self.db), [])

    def test_injected_sender_receives_the_card_once(self):
        from backend.platform.review_planner import list_outbox, run_review_push

        self._seed_due()
        sent = []

        def sender(body: str) -> None:
            sent.append(body)

        first = run_review_push("student", now=NOW, db_path=self.db, sender=sender)
        second = run_review_push("student", now=NOW, db_path=self.db, sender=sender)
        self.assertEqual(sent, [first["body"]])
        self.assertEqual(first["channel"], "feishu")
        self.assertEqual(first["status"], "sent")
        self.assertEqual(second["reason"], "already_delivered")
        self.assertEqual(list_outbox("student", db_path=self.db)[0]["status"], "sent")

    def test_failed_sender_can_be_retried(self):
        from backend.platform.review_planner import list_outbox, run_review_push

        self._seed_due()
        calls = {"n": 0}

        def sender(body: str) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("webhook down")

        failed = run_review_push("student", now=NOW, db_path=self.db, sender=sender)
        retried = run_review_push("student", now=NOW, db_path=self.db, sender=sender)
        self.assertEqual(failed["status"], "failed")
        self.assertIn("webhook down", failed["error"])
        self.assertEqual(retried["status"], "sent")
        self.assertEqual(len(list_outbox("student", db_path=self.db)), 1)

    def test_worker_cli_prints_the_card(self):
        from backend.workers.review_push import main

        self._seed_due()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(
                [
                    "--user",
                    "student",
                    "--db",
                    str(self.db),
                    "--now",
                    "2026-11-04T01:00:00+00:00",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("晨间复习 1 题", buf.getvalue())

    def test_tools_plan_send_and_reschedule(self):
        import backend.platform.mistake_store as mistakes
        import backend.platform.review_planner as planner
        from unittest import mock

        import backend.agents.react_tools as tools
        from backend.agents.tool_registry import get_tool_spec

        self._seed_due()
        spec = get_tool_spec("send_message")
        self.assertTrue(spec.requires_approval)
        self.assertTrue(spec.side_effects)
        self.assertIsNotNone(get_tool_spec("get_learning_state"))
        self.assertIsNotNone(get_tool_spec("plan_review"))
        self.assertIsNotNone(get_tool_spec("reschedule"))

        class Agent:
            user_id = "student"

        with mock.patch.object(mistakes, "TRACE_DB_PATH", self.db), mock.patch.object(
            planner, "TRACE_DB_PATH", self.db
        ):
            state_text = tools.execute_tool(Agent(), "get_learning_state", {})
            card = tools.execute_tool(Agent(), "plan_review", {})
            sent = tools.execute_tool(Agent(), "send_message", {})
            moved = tools.execute_tool(Agent(), "reschedule", {"when_text": "推到晚上"})

        self.assertIn("链式法则", state_text)
        self.assertIn("晨间复习 1 题", card)
        self.assertIn("已保存", sent)
        self.assertIn("20:00", moved)
        cards = planner.list_outbox("student", db_path=self.db)
        self.assertEqual(len(cards), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
