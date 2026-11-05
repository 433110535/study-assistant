"""
单元测试：知识库 /v1/documents* 与 /v1/mastery API
对齐说明/PLAN.md M7 验收标准
"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.api.local_client import (
    get_documents_api,
    ingest_document_api,
    delete_document_api,
    search_documents_api,
    ask_documents_api,
    list_mastery_api,
)


class MockKB:
    """Mock FAISS 向量库，用于 API 测试隔离"""
    def __init__(self):
        self.docs = {}
        self.doc_info = {}

    def add_text(self, text, doc_id, title, subject="未分类", chunk_size=500, chunk_overlap=50):
        self.docs[doc_id] = text
        self.doc_info[doc_id] = {
            "title": title,
            "subject": subject,
            "chunk_count": 3,
        }
        return True

    def delete_document(self, doc_id):
        if doc_id in self.docs:
            del self.docs[doc_id]
        if doc_id in self.doc_info:
            del self.doc_info[doc_id]
        return True

    def search(self, query, top_k=5, subject=None):
        return [
            {
                "content": f"关于 {query} 的重要内容",
                "similarity": 0.95,
                "metadata": {"title": "测试教材", "subject": subject or "通用"},
            }
        ]

    def get_stats(self):
        return {"total_documents": len(self.docs), "total_chunks": len(self.docs) * 3}


class TestDomainApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_api_app.db"
        self.mock_kb = MockKB()
        self.app = create_app(
            db_path=self.db,
            api_key="secret",
            kb_factory=lambda: self.mock_kb,
            rag_ask_fn=lambda q, res: f"基于参考资料对【{q}】的解答",
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def _headers(self):
        return {"X-API-Key": "secret"}

    def test_document_ingest_search_and_delete_via_api(self):
        # 1. 摄入文档
        ingest_res = self.client.post(
            "/v1/documents",
            headers=self._headers(),
            json={
                "title": "高等数学",
                "content_text": "微积分基本定理连接了微分与积分",
                "subject": "数学",
                "doc_id": "math_doc",
            },
        ).json()
        self.assertEqual(ingest_res["doc_id"], "math_doc")
        self.assertTrue(bool(ingest_res["trace_id"]))

        # 2. 查询文档列表
        doc_list = self.client.get(
            "/v1/documents",
            headers=self._headers(),
        ).json()
        self.assertEqual(doc_list["total_documents"], 1)
        self.assertEqual(doc_list["documents"][0]["title"], "高等数学")

        # 3. 向量搜索
        search_res = self.client.post(
            "/v1/documents/search",
            headers=self._headers(),
            json={"query": "微积分", "top_k": 2},
        ).json()
        self.assertEqual(search_res["count"], 1)
        self.assertIn("微积分", search_res["results"][0]["content"])

        # 4. RAG 问答
        ask_res = self.client.post(
            "/v1/documents/ask",
            headers=self._headers(),
            json={"question": "微积分基本定理是什么？"},
        ).json()
        self.assertIn("微积分基本定理", ask_res["answer"])
        self.assertIn("测试教材", ask_res["sources"])

        # 5. 删除文档
        del_res = self.client.delete(
            "/v1/documents/math_doc",
            headers=self._headers(),
        ).json()
        self.assertTrue(del_res["deleted"])

        # 6. 验证已删除
        doc_list_after = self.client.get(
            "/v1/documents",
            headers=self._headers(),
        ).json()
        self.assertEqual(doc_list_after["total_documents"], 0)

    def test_mastery_route(self):
        # 先手动记录一条掌握度
        from backend.platform.domain_store import upsert_mastery
        upsert_mastery("反函数求导", is_correct=True, db_path=self.db)

        res = self.client.get("/v1/mastery", headers=self._headers()).json()
        self.assertEqual(len(res["mastery"]), 1)
        self.assertEqual(res["mastery"][0]["concept"], "反函数求导")


if __name__ == "__main__":
    unittest.main()
