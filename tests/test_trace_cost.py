"""运行记录带 trace_id，并按百炼华北2（北京）原价记费用。"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestLlmCost(unittest.TestCase):
    def test_qwen_max_million_tokens_match_beijing_list_price(self):
        from backend.platform.llm_cost import estimate_cost_yuan

        self.assertEqual(estimate_cost_yuan("qwen-max", 1_000_000, 0), 2.4)
        self.assertEqual(estimate_cost_yuan("qwen-max", 0, 1_000_000), 9.6)
        self.assertEqual(estimate_cost_yuan("qwen-max", 1000, 1000), 0.012)

    def test_qwen_plus_uses_non_thinking_rate(self):
        from backend.platform.llm_cost import estimate_cost_yuan

        self.assertEqual(estimate_cost_yuan("qwen-plus", 1_000_000, 1_000_000), 2.8)

    def test_unknown_model_with_tokens_has_no_invented_price(self):
        from backend.platform.llm_cost import estimate_cost_yuan

        self.assertIsNone(estimate_cost_yuan("qwen-turbo", 100, 50))

    def test_usage_reads_langchain_metadata(self):
        from backend.platform.llm_cost import usage_from_message

        class Message:
            usage_metadata = {"input_tokens": 20, "output_tokens": 5}
            response_metadata = {}

        self.assertEqual(usage_from_message(Message()), (20, 5))


class TestTraceRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_finish_stores_trace_id_tokens_and_cost(self):
        from backend.platform.trace_store import TraceRun, get_run

        trace = TraceRun("什么是梯度下降？", session_id="student", model="qwen-max", db_path=self.db)
        trace.start()
        trace.add_usage(1000, 500)
        trace.add_usage(200, 100)
        trace.finish("梯度下降沿负梯度更新参数。", iterations=2)

        stored = get_run(trace.run_id, db_path=self.db)
        self.assertEqual(len(stored["trace_id"]), 32)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in stored["trace_id"]))
        self.assertNotEqual(stored["trace_id"], "0" * 32)
        self.assertEqual(stored["token_in"], 1200)
        self.assertEqual(stored["token_out"], 600)
        self.assertEqual(stored["cost_yuan"], 0.00864)
        self.assertEqual(stored["model"], "qwen-max")

    def test_run_without_model_usage_costs_zero(self):
        from backend.platform.trace_store import TraceRun, get_run

        trace = TraceRun("[代码助教]\nprint(1)", db_path=self.db)
        trace.start()
        trace.finish("1", iterations=1, status="ok")
        stored = get_run(trace.run_id, db_path=self.db)
        self.assertEqual(stored["token_in"], 0)
        self.assertEqual(stored["token_out"], 0)
        self.assertEqual(stored["cost_yuan"], 0.0)
        self.assertEqual(len(stored["trace_id"]), 32)

    def test_old_runs_table_gains_cost_columns(self):
        from backend.platform.trace_store import TraceRun, get_run, init_trace_db

        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """
                CREATE TABLE runs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    user_input TEXT NOT NULL,
                    final_answer TEXT,
                    iterations INTEGER DEFAULT 0,
                    tools_used TEXT,
                    latency_ms INTEGER,
                    status TEXT DEFAULT 'running',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        init_trace_db(self.db)
        trace = TraceRun("旧库补列", model="qwen-plus", db_path=self.db)
        trace.start()
        trace.add_usage(1_000_000, 0)
        trace.finish("ok", iterations=1)
        stored = get_run(trace.run_id, db_path=self.db)
        self.assertEqual(stored["cost_yuan"], 0.8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
