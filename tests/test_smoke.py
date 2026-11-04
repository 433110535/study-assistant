"""
项目冒烟测试（不调用通义千问 API）

运行方式：
    venv\\Scripts\\python.exe -m unittest discover -s tests -v

覆盖内容：
    1. 依赖导入 / 配置校验
    2. 文本切分
    3. FAISS 向量库增删查 + 落盘 / 加载
    4. PDF 解析
    5. 现有知识库索引加载
    6. Streamlit 前端 9 个页面渲染
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDependencies(unittest.TestCase):
    """依赖与配置"""

    def test_import_dependencies(self):
        import numpy  # noqa: F401
        import pandas  # noqa: F401
        import streamlit  # noqa: F401
        import faiss  # noqa: F401
        import dashscope  # noqa: F401
        import langchain_core  # noqa: F401
        import langchain_openai  # noqa: F401
        import jieba  # noqa: F401
        import pypdf  # noqa: F401

    def test_backend_modules_import(self):
        import importlib

        modules = [
            "backend.config",
            "backend.llm_helper",
            "backend.agents.base_agent",
            "backend.agents.react_models",
            "backend.agents.react_tools",
            "backend.agents.react_agent",
            "backend.knowledge.embedding",
            "backend.knowledge.pdf_loader",
            "backend.knowledge.vector_store_faiss",
            "backend.knowledge.knowledge_base_faiss",
            "backend.tools.knowledge",
            "backend.tools.plan_generator",
            "backend.tools.question_generator",
            "backend.tools.vision",
            "backend.agents.tool_registry",
            "backend.platform.trace_store",
        ]
        for name in modules:
            with self.subTest(module=name):
                self.assertIsNotNone(importlib.import_module(name))

    def test_config_valid(self):
        from backend import config

        self.assertTrue(config.validate_config())
        self.assertTrue(config.FAISS_INDEX_DIR.exists())
        self.assertTrue(config.DATA_DIR.exists())


class TestTextSplit(unittest.TestCase):
    """文本切分"""

    def test_split_short_text(self):
        from backend.knowledge.embedding import text_split_by_token

        chunks = text_split_by_token("Python是一种高级编程语言。", max_tokens=200, overlap=20)
        self.assertGreaterEqual(len(chunks), 1)

    def test_split_long_text(self):
        from backend.knowledge.embedding import text_split_by_token

        text = "Python是一种广泛使用的高级编程语言。\n\n" * 60
        chunks = text_split_by_token(text, max_tokens=200, overlap=20)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 300, "文本块超出 max_tokens*1.5")


class TestPdfLoader(unittest.TestCase):
    """PDF 解析"""

    def test_extract_pdf(self):
        from backend.knowledge.pdf_loader import clean_text, extract_text_from_pdf

        pdfs = sorted(PROJECT_ROOT.glob("*.pdf"))
        if not pdfs:
            self.skipTest("项目根目录没有 PDF 样本")
        smallest = min(pdfs, key=lambda p: p.stat().st_size)
        data = extract_text_from_pdf(str(smallest))
        self.assertGreater(data["pages"], 0)
        self.assertGreater(len(data["text"].strip()), 0)
        self.assertIn("title", data["metadata"])
        self.assertIsInstance(clean_text(data["text"]), str)


class TestVectorStore(unittest.TestCase):
    """FAISS 向量库（离线，使用随机向量）"""

    def setUp(self):
        import numpy as np

        from backend.knowledge.vector_store_faiss import FAISSVectorStore

        self.np = np
        self.tmpdir = tempfile.mkdtemp(prefix="faiss_test_")
        self.rng = np.random.default_rng(42)
        self.store = FAISSVectorStore(index_type="flat", dim=1024)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _vectors(self, n=5):
        return [self.rng.random(1024).astype("float32").tolist() for _ in range(n)]

    def test_add_and_search(self):
        chunks = [f"文本块{i}" for i in range(5)]
        self.store.add_vectors(self._vectors(5), "doc1", chunks, {"subject": "测试"})

        results = self.store.search(self._vectors(1)[0], top_k=3)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn("content", r)
            self.assertIn("similarity", r)
            self.assertEqual(r["metadata"]["subject"], "测试")

    def test_save_and_load(self):
        self.store.add_vectors(self._vectors(4), "doc1", [f"块{i}" for i in range(4)])
        self.store.save(self.tmpdir)

        from backend.knowledge.vector_store_faiss import FAISSVectorStore

        loaded = FAISSVectorStore(index_type="flat", dim=1024)
        loaded.load(self.tmpdir)
        stats = loaded.get_stats()
        self.assertEqual(stats["total_chunks"], 4)
        self.assertEqual(stats["total_documents"], 1)

    def test_delete_document(self):
        self.store.add_vectors(self._vectors(3), "doc1", ["a", "b", "c"])
        self.assertTrue(self.store.delete_document("doc1"))
        self.assertEqual(self.store.get_stats()["total_documents"], 0)


class TestKnowledgeBase(unittest.TestCase):
    """知识库索引加载"""

    def test_load_existing_index(self):
        from backend.knowledge.knowledge_base_faiss import FAISSKnowledgeBase

        kb = FAISSKnowledgeBase()
        stats = kb.get_stats()
        self.assertIn("total_chunks", stats)
        self.assertIn("total_documents", stats)
        self.assertIsInstance(kb.list_documents(), list)


class TestFrontend(unittest.TestCase):
    """Streamlit 前端页面渲染（不触发 LLM 调用）"""

    PAGES = [
        "dashboard", "qa", "react_viz", "knowledge", "compare",
        "planner", "daily", "quiz", "kb", "mistakes",
    ]

    def test_pages_render(self):
        from streamlit.testing.v1 import AppTest

        app = str(PROJECT_ROOT / "frontend" / "app.py")
        for page in self.PAGES:
            with self.subTest(page=page):
                at = AppTest.from_file(app, default_timeout=120)
                at.session_state["current_page"] = page
                at.run()
                errors = [str(e.value) for e in at.exception]
                self.assertEqual(errors, [], f"{page} 页面渲染异常: {errors}")
                self.assertGreater(len(at.sidebar.button), 0, "侧边栏未渲染")


if __name__ == "__main__":
    unittest.main(verbosity=2)
