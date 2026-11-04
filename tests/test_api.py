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

    def test_empty_eval_board(self):
        latest = self.client.get("/v1/eval/latest", headers=self._headers())
        self.assertEqual(latest.status_code, 200)
        self.assertIsNone(latest.json()["latest"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
