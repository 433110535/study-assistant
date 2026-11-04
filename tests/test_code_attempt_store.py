"""代码助教修改记录：同一次练习按顺序追加，另一次练习互不混入。"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCodeAttemptStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_attempts_stay_in_order_inside_one_thread(self):
        from backend.platform.code_attempt_store import append_attempt, list_attempts, new_thread_id

        thread_id = new_thread_id()
        append_attempt("student", thread_id, "print(1)", "", {"status": "passed", "stdout": "1"}, self.db)
        append_attempt(
            "student",
            thread_id,
            "print(2)",
            "assert False",
            {"status": "failed", "exception_type": "AssertionError", "line": 1},
            self.db,
        )
        rows = list_attempts("student", thread_id, self.db)
        self.assertEqual([row["seq"] for row in rows], [1, 2])
        self.assertEqual(rows[1]["code"], "print(2)")
        self.assertEqual(rows[1]["exception_type"], "AssertionError")

    def test_latest_thread_is_the_one_just_run(self):
        from backend.platform.code_attempt_store import append_attempt, latest_thread, new_thread_id

        first = new_thread_id()
        second = new_thread_id()
        append_attempt("student", first, "a = 1", "", {"status": "passed"}, self.db)
        append_attempt("student", second, "a = 2", "", {"status": "passed"}, self.db)
        self.assertEqual(latest_thread("student", self.db), second)

    def test_other_thread_is_not_listed(self):
        from backend.platform.code_attempt_store import append_attempt, list_attempts, new_thread_id

        keep = new_thread_id()
        other = new_thread_id()
        append_attempt("student", keep, "keep", "", {"status": "passed"}, self.db)
        append_attempt("student", other, "other", "", {"status": "failed"}, self.db)
        rows = list_attempts("student", keep, self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
