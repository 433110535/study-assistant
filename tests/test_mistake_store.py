"""错题本待确认写入测试"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestMistakeStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_pending_until_confirmed(self):
        from backend.platform import mistake_store as store

        mistake_id = store.create_pending(
            "student",
            subject="数学",
            concept="链式法则",
            error_type="概念不清",
            question_text="求 d/dx sin(x^2)",
            student_answer="cos(x^2)",
            correct_answer="2x cos(x^2)",
            db_path=self.db,
        )
        pending = store.list_mistakes("student", status="pending", db_path=self.db)
        self.assertEqual(len(pending), 1)
        self.assertTrue(store.confirm_mistake(mistake_id, db_path=self.db))
        self.assertEqual(store.list_mistakes("student", status="pending", db_path=self.db), [])
        confirmed = store.list_mistakes("student", status="confirmed", db_path=self.db)
        self.assertEqual(confirmed[0]["review_count"], 0)
        self.assertTrue(confirmed[0]["next_review_at"])

    def test_tool_writes_pending_and_requires_approval(self):
        import backend.agents.react_tools as tools
        from backend.agents.tool_registry import get_tool_spec

        spec = get_tool_spec("save_mistake")
        self.assertTrue(spec.requires_approval)
        self.assertTrue(spec.side_effects)

        class Agent:
            user_id = "student"

        import backend.platform.mistake_store as store

        with mock.patch.object(store, "TRACE_DB_PATH", self.db):
            result = tools.execute_tool(
                    Agent(),
                    "save_mistake",
                    {
                        "subject": "物理",
                        "concept": "牛顿第二定律",
                        "error_type": "审题错误",
                        "question_text": "质量为 2kg 的物体受 4N 力，加速度是多少？",
                    },
                )
        self.assertIn("待确认", result)
        import backend.platform.mistake_store as store

        rows = store.list_mistakes("student", status="pending", db_path=self.db)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
