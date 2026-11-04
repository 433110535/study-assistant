"""本机 API 与 SQLite 备份。不调用模型，也不监听端口。"""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

NOW = datetime(2026, 11, 4, 1, 0, tzinfo=timezone.utc)


class TestDatabaseBackup(unittest.TestCase):
    def test_restore_puts_back_the_copied_rows(self):
        from backend.platform.db_backup import copy_database
        from backend.platform.mistake_store import create_pending, list_mistakes

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        db = root / "app.db"
        backup = root / "backups" / "app.db"
        first = create_pending(
            "student",
            subject="数学",
            concept="链式法则",
            error_type="概念不清",
            question_text="求导数",
            student_answer="错",
            correct_answer="对",
            db_path=db,
        )
        copy_database(db, backup)
        create_pending(
            "student",
            subject="数学",
            concept="换元",
            error_type="计算失误",
            question_text="求积分",
            student_answer="错",
            correct_answer="对",
            db_path=db,
        )
        self.assertEqual(len(list_mistakes("student", db_path=db)), 2)
        copy_database(backup, db)
        rows = list_mistakes("student", db_path=db)
        self.assertEqual([item["id"] for item in rows], [first])

    def test_missing_source_is_an_error(self):
        from backend.platform.db_backup import copy_database

        with self.assertRaises(FileNotFoundError):
            copy_database(Path(tempfile.mkdtemp()) / "missing.db", Path(tempfile.mkdtemp()) / "out.db")


class TestLocalApi(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app

        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.client = TestClient(create_app(self.db, api_key="secret"))

    def tearDown(self):
        self.tmp.cleanup()

    def _headers(self):
        return {"X-API-Key": "secret"}

    def test_health_is_open_and_tools_need_the_key(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        denied = self.client.get("/v1/tools")
        self.assertEqual(denied.status_code, 401)
        allowed = self.client.get("/v1/tools", headers=self._headers())
        names = {item["name"] for item in allowed.json()["tools"]}
        self.assertIn("read_image", names)
        self.assertIn("grade_item", names)
        self.assertTrue(all("fn" not in item for item in allowed.json()["tools"]))

    def test_trace_round_trip(self):
        from backend.platform.trace_store import TraceRun

        run = TraceRun("什么是链式法则", db_path=self.db, model="qwen-plus")
        run.start()
        run.log_tool_call("rag_search", {"query": "链式法则"}, "片段", "ok", 12)
        run.finish("见教材", 1)
        missing = self.client.get("/v1/traces/missing", headers=self._headers())
        self.assertEqual(missing.status_code, 404)
        found = self.client.get(f"/v1/traces/{run.trace_id}", headers=self._headers())
        self.assertEqual(found.status_code, 200)
        body = found.json()
        self.assertEqual(body["run"]["user_input"], "什么是链式法则")
        self.assertEqual(body["tool_calls"][0]["tool_name"], "rag_search")

    def test_confirm_mistake_and_plan_review_without_sending(self):
        from backend.platform.mistake_store import create_pending
        from backend.platform.review_planner import list_outbox, reschedule

        mistake_id = create_pending(
            "student",
            subject="数学",
            concept="链式法则",
            error_type="概念不清",
            question_text="求 d/dx sin(x^2)",
            student_answer="cos(x^2)",
            correct_answer="2x cos(x^2)",
            db_path=self.db,
        )
        listed = self.client.get(
            "/v1/mistakes",
            params={"user_id": "student", "status": "pending"},
            headers=self._headers(),
        )
        self.assertEqual(listed.json()["mistakes"][0]["id"], mistake_id)
        confirmed = self.client.post(
            f"/v1/mistakes/{mistake_id}/confirm",
            headers=self._headers(),
        )
        self.assertEqual(confirmed.status_code, 200)
        again = self.client.post(
            f"/v1/mistakes/{mistake_id}/confirm",
            headers=self._headers(),
        )
        self.assertEqual(again.status_code, 404)
        other = create_pending(
            "student",
            subject="数学",
            concept="换元",
            error_type="计算失误",
            question_text="求积分",
            student_answer="错",
            correct_answer="对",
            db_path=self.db,
        )
        from backend.api.local_client import dismiss_user_mistake, list_user_mistakes

        self.assertEqual(list_user_mistakes("student", status="pending", db_path=self.db)[0]["id"], other)
        self.assertEqual(dismiss_user_mistake(other, db_path=self.db)["status"], "dismissed")
        self.assertEqual(list_user_mistakes("student", status="pending", db_path=self.db), [])
        missing = self.client.post(
            f"/v1/mistakes/{other}/dismiss",
            headers=self._headers(),
        )
        self.assertEqual(missing.status_code, 404)
        self.assertTrue(
            reschedule(mistake_id, "2026-11-01T00:00:00+00:00", now=NOW, db_path=self.db)
        )
        plan = self.client.get(
            "/v1/review/plan",
            params={"user_id": "student"},
            headers=self._headers(),
        )
        self.assertEqual(plan.status_code, 200)
        self.assertIn("晨间复习 1 题", plan.json()["body"])
        self.assertNotIn("2x cos", plan.json()["body"])
        self.assertEqual(list_outbox("student", db_path=self.db), [])

    def test_page_client_reads_the_latest_board_through_the_route(self):
        import json

        from backend.api.local_client import failure_board
        from backend.platform.eval_runner import load_failure_board, save_eval_run

        dataset = {"name": "tiny", "version": "v0", "samples": [{"id": "a"}]}
        save_eval_run(
            dataset,
            "dry-run",
            [
                {
                    "sample_id": "a",
                    "passed": False,
                    "tools_used": [],
                    "detail": json.dumps({"missing": ["rag_search"]}),
                    "output": "",
                }
            ],
            db_path=self.db,
        )
        via_route = failure_board(self.db)
        direct = load_failure_board(self.db)
        self.assertEqual(via_route["latest"]["failure_attribution"], direct["latest"]["failure_attribution"])
        self.assertEqual(via_route["latest"]["failure_attribution"][0]["tool"], "rag_search")

    def test_due_review_and_local_card_go_through_the_route(self):
        from datetime import datetime

        from backend.api.local_client import (
            due_reviews,
            list_review_cards,
            move_review,
            remember_review,
            save_review_card,
        )
        from backend.platform.mistake_store import confirm_mistake, create_pending
        from backend.platform.review_planner import reschedule

        stamp = "2026-11-04T01:00:00+00:00"
        moment = datetime.fromisoformat(stamp)
        mistake_id = create_pending(
            "student",
            subject="数学",
            concept="链式法则",
            error_type="概念不清",
            question_text="求 d/dx sin(x^2)",
            student_answer="cos(x^2)",
            correct_answer="2x cos(x^2)",
            db_path=self.db,
        )
        self.assertTrue(confirm_mistake(mistake_id, db_path=self.db))
        self.assertTrue(
            reschedule(
                mistake_id,
                "2026-11-01T00:00:00+00:00",
                now=moment,
                db_path=self.db,
            )
        )
        due = due_reviews("student", now=stamp, db_path=self.db)["due"]
        self.assertEqual([item["id"] for item in due], [mistake_id])
        saved = save_review_card("student", now=stamp, db_path=self.db)
        self.assertEqual(saved["channel"], "local")
        self.assertEqual(saved["status"], "stored")
        self.assertNotIn("2x cos", saved["body"])
        cards = list_review_cards("student", db_path=self.db)
        self.assertEqual(len(cards), 1)
        self.assertEqual(move_review(mistake_id, "推到晚上", now=stamp, db_path=self.db)["when_text"], "推到晚上")
        self.assertEqual(due_reviews("student", now=stamp, db_path=self.db)["due"], [])
        remembered = remember_review(mistake_id, quality=5, now=stamp, db_path=self.db)
        self.assertEqual(remembered["interval_days"], 1)
        pending = create_pending(
            "student",
            subject="数学",
            concept="换元",
            error_type="计算失误",
            question_text="求积分",
            student_answer="错",
            correct_answer="对",
            db_path=self.db,
        )
        denied = self.client.post(
            f"/v1/mistakes/{pending}/review",
            json={"quality": 5, "now": stamp},
            headers=self._headers(),
        )
        self.assertEqual(denied.status_code, 404)
        bad_quality = self.client.post(
            f"/v1/mistakes/{mistake_id}/review",
            json={"quality": 9, "now": stamp},
            headers=self._headers(),
        )
        self.assertEqual(bad_quality.status_code, 400)

    def test_chat_stream_uses_the_injected_agent(self):
        import json

        from backend.agents.react_models import ReActEvent, ReActEventType
        from backend.api.app import create_app

        class FakeAgent:
            def react_stream(self, message: str):
                yield ReActEvent(
                    event_type=ReActEventType.ANSWER_CHUNK,
                    content=message[:1],
                    iteration=1,
                )
                yield ReActEvent(
                    event_type=ReActEventType.FINAL_ANSWER,
                    content=message,
                    iteration=1,
                )

        from fastapi.testclient import TestClient

        app = create_app(self.db, api_key="secret", agent_factory=FakeAgent)
        empty = TestClient(app).post(
            "/v1/chat/stream",
            json={"message": "  "},
            headers=self._headers(),
        )
        self.assertEqual(empty.status_code, 400)
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/stream",
                json={"message": "你好"},
                headers=self._headers(),
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0][len("data: "):])
        last = json.loads(lines[1][len("data: "):])
        self.assertEqual(first["event_type"], "answer_chunk")
        self.assertEqual(first["content"], "你")
        self.assertEqual(last["event_type"], "final_answer")
        self.assertEqual(last["content"], "你好")

    def test_page_chat_stream_reuses_the_same_agent(self):
        from backend.agents.react_models import ReActEvent, ReActEventType
        from backend.api.local_client import iter_chat_events, parse_sse

        parsed = parse_sse("data: {\"event_type\": \"thinking\", \"content\": \"想\"}\n\n")
        self.assertEqual(parsed, [{"event_type": "thinking", "content": "想"}])

        class Agent:
            def __init__(self):
                self.seen = ""

            def react_stream(self, message: str):
                self.seen = message
                yield ReActEvent(
                    event_type=ReActEventType.FINAL_ANSWER,
                    content="好",
                    iteration=1,
                )

        agent = Agent()
        events = list(iter_chat_events("今天复习什么", agent_factory=lambda: agent))
        self.assertEqual(agent.seen, "今天复习什么")
        self.assertEqual(events[0]["event_type"], "final_answer")
        self.assertEqual(events[0]["content"], "好")

    def test_explain_route_uses_the_injected_function(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app

        def fake(concept: str, subject: str = "", level: str = "初学者") -> str:
            return f"{concept}|{subject}|{level}"

        app = create_app(self.db, api_key="secret", explain_fn=fake)
        with TestClient(app) as client:
            empty = client.post("/v1/explain", json={"concept": "  "}, headers=self._headers())
            self.assertEqual(empty.status_code, 400)
            ok = client.post(
                "/v1/explain",
                json={"concept": "递归", "subject": "编程", "level": "中级"},
                headers=self._headers(),
            )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["text"], "递归|编程|中级")

    def test_compare_route_uses_the_injected_function(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app

        def fake(concept1: str, concept2: str) -> str:
            return f"{concept1} vs {concept2}"

        app = create_app(self.db, api_key="secret", compare_fn=fake)
        with TestClient(app) as client:
            empty = client.post(
                "/v1/compare",
                json={"concept1": "列表", "concept2": " "},
                headers=self._headers(),
            )
            self.assertEqual(empty.status_code, 400)
            ok = client.post(
                "/v1/compare",
                json={"concept1": "列表", "concept2": "元组"},
                headers=self._headers(),
            )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["text"], "列表 vs 元组")

    def test_questions_route_uses_the_injected_function(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app

        def fake(topic: str, difficulty: str = "中等", count: int = 3, question_type: str = "mixed") -> str:
            return f"{topic}|{difficulty}|{count}|{question_type}"

        app = create_app(self.db, api_key="secret", questions_fn=fake)
        with TestClient(app) as client:
            empty = client.post("/v1/questions", json={"topic": " "}, headers=self._headers())
            self.assertEqual(empty.status_code, 400)
            bad_count = client.post(
                "/v1/questions",
                json={"topic": "列表", "count": 11},
                headers=self._headers(),
            )
            self.assertEqual(bad_count.status_code, 400)
            ok = client.post(
                "/v1/questions",
                json={"topic": "列表", "difficulty": "基础", "count": 2, "question_type": "填空题"},
                headers=self._headers(),
            )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["text"], "列表|基础|2|填空题")

    def test_plan_route_uses_the_injected_function(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app

        def fake(subject, goal, duration_days, current_level="初学者", hours_per_day=2.0):
            return f"{subject}|{goal}|{duration_days}|{current_level}|{hours_per_day}"

        app = create_app(self.db, api_key="secret", plan_fn=fake)
        with TestClient(app) as client:
            empty = client.post(
                "/v1/plans",
                json={"subject": "数学", "goal": " "},
                headers=self._headers(),
            )
            self.assertEqual(empty.status_code, 400)
            bad_days = client.post(
                "/v1/plans",
                json={"subject": "数学", "goal": "会做题", "duration_days": 3},
                headers=self._headers(),
            )
            self.assertEqual(bad_days.status_code, 400)
            ok = client.post(
                "/v1/plans",
                json={
                    "subject": "数学",
                    "goal": "会做题",
                    "duration_days": 14,
                    "current_level": "初学者",
                    "hours_per_day": 1.5,
                },
                headers=self._headers(),
            )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["text"], "数学|会做题|14|初学者|1.5")

    def test_schedule_route_matches_the_local_function(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app
        from backend.tools.plan_generator import create_daily_schedule

        topics = ["变量", "循环"]
        app = create_app(self.db, api_key="secret")
        with TestClient(app) as client:
            empty = client.post(
                "/v1/schedules",
                json={"topics": ["  "]},
                headers=self._headers(),
            )
            self.assertEqual(empty.status_code, 400)
            ok = client.post(
                "/v1/schedules",
                json={
                    "topics": topics,
                    "available_hours": 2,
                    "include_break": True,
                    "break_duration": 15,
                },
                headers=self._headers(),
            )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["text"], create_daily_schedule(topics, 2, True, 15))

    def test_paper_grade_route_matches_the_local_function(self):
        from fastapi.testclient import TestClient

        from backend.api.app import create_app
        from backend.tools.grading import grade_paper

        paper = "1. 3+4等于多少？\n作答：7\n标准答案：7"
        app = create_app(self.db, api_key="secret")
        with TestClient(app) as client:
            empty = client.post("/v1/papers/grade", json={"text": "  "}, headers=self._headers())
            self.assertEqual(empty.status_code, 400)
            ok = client.post(
                "/v1/papers/grade",
                json={"text": paper},
                headers=self._headers(),
            )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json(), grade_paper(paper))

    def test_empty_eval_board(self):
        latest = self.client.get("/v1/eval/latest", headers=self._headers())
        self.assertEqual(latest.status_code, 200)
        self.assertIsNone(latest.json()["latest"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
