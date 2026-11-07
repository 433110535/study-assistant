"""
U7 数据中台与运维底座 API 测试：/v1/traces、/v1/eval/runs、/v1/eval/compare、/v1/datasets
"""
import gc
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.platform.trace_store import init_trace_db
from backend.platform.eval_runner import ensure_eval_tables


class TestOpsPlatformAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ops.db"
        init_trace_db(self.db_path)
        ensure_eval_tables(self.db_path)
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_list_traces_empty(self):
        res = self.client.get("/v1/traces")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["traces"], [])
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["limit"], 20)
        self.assertEqual(data["offset"], 0)

    def test_list_traces_with_data_and_filter(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (id, trace_id, session_id, user_input, final_answer, iterations, status, created_at, model, token_in, token_out, cost_yuan)
                VALUES ('run-1', 'trace-1', 'sess-1', '测试输入1', '回答1', 1, 'ok', '2026-11-07T10:00:00', 'qwen-plus', 10, 20, 0.001),
                       ('run-2', 'trace-2', 'sess-1', '测试输入2', '回答2', 2, 'error', '2026-11-07T10:05:00', 'qwen-max', 15, 30, 0.002)
                """
            )
            conn.commit()

        # 全部查询
        res = self.client.get("/v1/traces?limit=10&offset=0")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["traces"]), 2)
        self.assertEqual(data["traces"][0]["id"], "run-2")  # 倒序

        # 状态过滤
        res_err = self.client.get("/v1/traces?status=error")
        self.assertEqual(res_err.status_code, 200)
        self.assertEqual(res_err.json()["total"], 1)
        self.assertEqual(res_err.json()["traces"][0]["id"], "run-2")

        # 模型过滤
        res_model = self.client.get("/v1/traces?model=qwen-plus")
        self.assertEqual(res_model.status_code, 200)
        self.assertEqual(res_model.json()["total"], 1)
        self.assertEqual(res_model.json()["traces"][0]["id"], "run-1")

    def test_get_trace_detail_and_404(self):
        # 404 测试
        res_404 = self.client.get("/v1/traces/non-existent-run")
        self.assertEqual(res_404.status_code, 404)

        # 写入运行和 tool_calls
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (id, trace_id, user_input, final_answer, iterations, status, created_at, model)
                VALUES ('run-abc', 'trace-xyz', '求解题目', '答案为42', 1, 'ok', '2026-11-07T11:00:00', 'qwen-plus')
                """
            )
            conn.execute(
                """
                INSERT INTO tool_calls (run_id, tool_name, args_json, result_preview, status, latency_ms, created_at)
                VALUES ('run-abc', 'grade_item', '{"question":"1+1"}', 'correct', 'ok', 45, '2026-11-07T11:00:01')
                """
            )
            conn.commit()

        # 按 run_id 查
        res_run = self.client.get("/v1/traces/run-abc")
        self.assertEqual(res_run.status_code, 200)
        data_run = res_run.json()
        self.assertEqual(data_run["run"]["id"], "run-abc")
        self.assertEqual(len(data_run["tool_calls"]), 1)
        self.assertEqual(data_run["tool_calls"][0]["tool_name"], "grade_item")

        # 按 trace_id 查
        res_trace = self.client.get("/v1/traces/trace-xyz")
        self.assertEqual(res_trace.status_code, 200)
        self.assertEqual(res_trace.json()["run"]["trace_id"], "trace-xyz")

    def test_eval_runs_and_compare(self):
        # 写入两次评测记录
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO eval_runs (id, dataset_name, dataset_version, mode, status, sample_count, passed, summary_json, started_at, finished_at)
                VALUES ('eval-v1', 'qa_baseline', 'v1', 'dry-run', 'ok', 2, 2, '{"passed": 2, "total": 2, "accuracy": 1.0, "faithfulness": 0.95}', '2026-11-07T09:00:00', '2026-11-07T09:01:00'),
                       ('eval-v2', 'qa_baseline', 'v2', 'dry-run', 'ok', 2, 1, '{"passed": 1, "total": 2, "accuracy": 0.5, "faithfulness": 0.80}', '2026-11-07T09:10:00', '2026-11-07T09:11:00')
                """
            )
            # eval-v1 全部通过
            conn.execute(
                """
                INSERT INTO eval_results (eval_run_id, sample_id, tools_used, passed, detail)
                VALUES ('eval-v1', 'sample-1', '["grade_item"]', 1, 'ok'),
                       ('eval-v1', 'sample-2', '["rag_search"]', 1, 'ok')
                """
            )
            # eval-v2: sample-1 保持通过，sample-2 发生退化 (regression)
            conn.execute(
                """
                INSERT INTO eval_results (eval_run_id, sample_id, tools_used, passed, detail)
                VALUES ('eval-v2', 'sample-1', '["grade_item"]', 1, 'ok'),
                       ('eval-v2', 'sample-2', '[]', 0, 'missing tool')
                """
            )
            conn.commit()

        # 列表查询
        res_list = self.client.get("/v1/eval/runs")
        self.assertEqual(res_list.status_code, 200)
        runs = res_list.json()["runs"]
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]["id"], "eval-v2")  # 倒序
        self.assertEqual(runs[0]["summary"]["accuracy"], 0.5)

        # 404 对比
        res_404 = self.client.get("/v1/eval/compare?base_run_id=eval-v1&target_run_id=missing")
        self.assertEqual(res_404.status_code, 404)

        # 正常版本对比
        res_cmp = self.client.get("/v1/eval/compare?base_run_id=eval-v1&target_run_id=eval-v2")
        self.assertEqual(res_cmp.status_code, 200)
        cmp_data = res_cmp.json()
        self.assertEqual(cmp_data["delta"]["accuracy_delta"], -0.5)
        self.assertEqual(cmp_data["delta"]["passed_delta"], -1)
        self.assertEqual(cmp_data["delta"]["regression_count"], 1)
        self.assertEqual(cmp_data["delta"]["fixed_count"], 0)
        self.assertIn("sample-2", cmp_data["regressions"])

    def test_session_message_append_api(self):
        # 创建会话
        create_res = self.client.post("/v1/sessions", json={"user_id": "student", "title": "单测会话"})
        self.assertEqual(create_res.status_code, 200)
        sess_id = create_res.json()["session_id"]

        # 422 缺少 role
        err_res = self.client.post(f"/v1/sessions/{sess_id}/messages", json={"content": "hello"})
        self.assertEqual(err_res.status_code, 422)

        # 正常追加
        append_res = self.client.post(
            f"/v1/sessions/{sess_id}/messages",
            json={"role": "user", "content": "你好，这是单测消息"},
        )
        self.assertEqual(append_res.status_code, 200)
        self.assertEqual(append_res.json()["status"], "ok")

        # 验证读取
        msg_res = self.client.get(f"/v1/sessions/{sess_id}/messages")
        self.assertEqual(msg_res.status_code, 200)
        msgs = msg_res.json()["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "你好，这是单测消息")

    def test_local_client_wrappers(self):
        from backend.api.local_client import (
            list_traces_api,
            get_trace_api,
            list_eval_runs_api,
            compare_eval_runs_api,
            ensure_session_api,
            append_message_api,
            load_messages_api,
        )

        sess_id = ensure_session_api(user_id="student", db_path=self.db_path)
        self.assertTrue(sess_id)
        append_message_api(sess_id, "assistant", "测试回答", db_path=self.db_path)
        msgs = load_messages_api(sess_id, db_path=self.db_path)
        self.assertTrue(any(m["content"] == "测试回答" for m in msgs))

        traces = list_traces_api(limit=5, db_path=self.db_path)
        self.assertIn("traces", traces)


if __name__ == "__main__":
    unittest.main()
