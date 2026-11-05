"""
单元测试：domain_store (users, documents, mastery, write_audit)
对齐说明/PLAN.md M2 验收标准
"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.platform.domain_store import (
    init_domain_db,
    upsert_user,
    get_user,
    add_document_record,
    get_document_record,
    list_document_records,
    delete_document_record,
    upsert_mastery,
    get_mastery,
    list_mastery,
    log_write_audit,
)


class TestDomainStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_app.db"
        init_domain_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_user_is_created(self):
        user = get_user("student", db_path=self.db)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "student")

    def test_upsert_user(self):
        upsert_user("u1", "alice", db_path=self.db)
        user = get_user("u1", db_path=self.db)
        self.assertEqual(user["username"], "alice")

    def test_document_lifecycle(self):
        rec = add_document_record(
            doc_id="doc_py",
            title="Python基础",
            subject="编程",
            chunks=10,
            user_id="student",
            db_path=self.db,
        )
        self.assertEqual(rec["title"], "Python基础")
        found = get_document_record("doc_py", db_path=self.db)
        self.assertEqual(found["chunks"], 10)

        docs = list_document_records(user_id="student", db_path=self.db)
        self.assertEqual(len(docs), 1)

        deleted = delete_document_record("doc_py", db_path=self.db)
        self.assertTrue(deleted)
        self.assertIsNone(get_document_record("doc_py", db_path=self.db))

    def test_mastery_scoring(self):
        # 第一次答对
        res1 = upsert_mastery("链式法则", is_correct=True, user_id="student", db_path=self.db)
        self.assertGreaterEqual(res1["score"], 0.6)
        self.assertEqual(res1["attempts"], 1)

        # 再次答对，提分
        res2 = upsert_mastery("链式法则", is_correct=True, user_id="student", db_path=self.db)
        self.assertGreater(res2["score"], res1["score"])
        self.assertEqual(res2["attempts"], 2)

        # 答错，扣分但不得低于0
        res3 = upsert_mastery("链式法则", is_correct=False, user_id="student", db_path=self.db)
        self.assertLess(res3["score"], res2["score"])

        m_list = list_mastery("student", db_path=self.db)
        self.assertEqual(len(m_list), 1)
        self.assertEqual(m_list[0]["concept"], "链式法则")

    def test_write_audit_logs_to_trace(self):
        from backend.platform.trace_store import get_trace

        trace_id = log_write_audit(
            action="kb_delete_document",
            details={"doc_id": "test_doc"},
            user_id="student",
            db_path=self.db,
        )
        self.assertTrue(bool(trace_id))
        trace = get_trace(trace_id, db_path=self.db)
        self.assertIsNotNone(trace)
        self.assertEqual(trace["tool_calls"][0]["tool_name"], "kb_delete_document")


if __name__ == "__main__":
    unittest.main()
