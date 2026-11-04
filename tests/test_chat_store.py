"""问答会话持久化测试（使用临时数据库）"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestChatStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_and_new_session(self):
        from backend.platform.chat_store import (
            append_message,
            ensure_session,
            load_messages,
            start_session,
        )

        first = ensure_session("student", db_path=self.db)
        append_message(first, "user", "什么是梯度下降？", db_path=self.db)
        append_message(first, "assistant", "沿着损失下降的方向更新参数。", db_path=self.db)

        again = ensure_session("student", db_path=self.db)
        self.assertEqual(first, again)
        messages = load_messages(first, db_path=self.db)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")

        second = start_session("student", db_path=self.db)
        self.assertNotEqual(first, second)
        self.assertEqual(load_messages(second, db_path=self.db), [])
        # 最新会话成为默认恢复对象
        self.assertEqual(ensure_session("student", db_path=self.db), second)

    def test_list_sessions_is_per_user_and_newest_first(self):
        from backend.platform.chat_store import append_message, list_sessions, start_session

        older = start_session("student", db_path=self.db)
        append_message(older, "user", "先问梯度下降", db_path=self.db)
        newer = start_session("student", db_path=self.db)
        append_message(newer, "user", "再问反向传播", db_path=self.db)
        start_session("other", db_path=self.db)

        rows = list_sessions("student", db_path=self.db)
        self.assertEqual([row["id"] for row in rows], [newer, older])
        self.assertEqual(rows[1]["title"], "先问梯度下降")


if __name__ == "__main__":
    unittest.main(verbosity=2)
