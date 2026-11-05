"""
Web UI 必需接口测试（对齐 PLAN.md 第 12 节 F1–F4 与 CORS）。
"""
import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.platform.auth_store import (
    create_web_session,
    get_web_session,
    revoke_web_session,
    cleanup_expired_sessions,
)
from backend.platform.chat_store import append_message, start_session


class TestF1Auth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_local_mode_default(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)
        res = client.get("/v1/auth/me")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["user_id"], "student")
        self.assertEqual(body["mode"], "local")

    def test_local_mode_with_api_key(self):
        app = create_app(self.db, api_key="test_secret", auth_mode="local")
        client = TestClient(app)
        denied = client.get("/v1/auth/me")
        self.assertEqual(denied.status_code, 401)

        allowed = client.get("/v1/auth/me", headers={"X-API-Key": "test_secret"})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["user_id"], "student")
        self.assertEqual(allowed.json()["mode"], "local")

    @patch.dict(os.environ, {"APP_USERNAME": "student", "APP_PASSWORD": "correct_pwd"})
    def test_password_mode_flow(self):
        app = create_app(self.db, auth_mode="password")
        client = TestClient(app)

        # 未登录访问受保护接口
        unauth = client.get("/v1/auth/me")
        self.assertEqual(unauth.status_code, 401)

        tools_unauth = client.get("/v1/tools")
        self.assertEqual(tools_unauth.status_code, 401)

        # 错误密码登录
        bad_login = client.post("/v1/auth/login", json={"username": "student", "password": "wrong_pwd"})
        self.assertEqual(bad_login.status_code, 401)
        self.assertEqual(bad_login.json()["detail"], "用户名或密码错误")

        # 正确登录
        login_res = client.post("/v1/auth/login", json={"username": "student", "password": "correct_pwd"})
        self.assertEqual(login_res.status_code, 200)
        data = login_res.json()
        self.assertEqual(data["user_id"], "student")
        self.assertIn("expires_at", data)
        self.assertIn("study_session", login_res.cookies)

        cookie_token = login_res.cookies["study_session"]

        # 携带 Cookie 访问受保护接口
        client.cookies.set("study_session", cookie_token)
        me_res = client.get("/v1/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["mode"], "password")

        tools_res = client.get("/v1/tools")
        self.assertEqual(tools_res.status_code, 200)

        # 登出
        logout_res = client.post("/v1/auth/logout")
        self.assertEqual(logout_res.status_code, 204)

        # 登出后失效 (再次带上已撤销的旧 token)
        client.cookies.set("study_session", cookie_token)
        after_logout = client.get("/v1/auth/me")
        self.assertEqual(after_logout.status_code, 401)

    def test_session_expiration(self):
        app = create_app(self.db, auth_mode="password")
        client = TestClient(app)
        token = "expired_token_123"
        # 创建已过期的 session (ttl = -10 秒)
        create_web_session("student", token, ttl_seconds=-10, db_path=self.db)
        self.assertIsNone(get_web_session(token, db_path=self.db))

        client.cookies.set("study_session", token)
        res = client.get("/v1/auth/me")
        self.assertEqual(res.status_code, 401)

    @patch.dict(os.environ, {"APP_USERNAME": "student", "APP_PASSWORD": "secret_pwd"})
    def test_login_rate_limiting(self):
        app = create_app(self.db, auth_mode="password")
        client = TestClient(app)

        # 连续失败 5 次
        for _ in range(5):
            res = client.post("/v1/auth/login", json={"username": "student", "password": "bad"})
            self.assertEqual(res.status_code, 401)

        # 第 6 次触发 429
        rate_res = client.post("/v1/auth/login", json={"username": "student", "password": "bad"})
        self.assertEqual(rate_res.status_code, 429)

    @patch.dict(os.environ, {"APP_USERNAME": "student", "APP_PASSWORD": ""})
    def test_empty_password_rejected_even_if_env_empty(self):
        app = create_app(self.db, auth_mode="password")
        client = TestClient(app)
        res = client.post("/v1/auth/login", json={"username": "student", "password": ""})
        self.assertEqual(res.status_code, 401)

    def test_cleanup_expired_sessions(self):
        create_web_session("student", "token_exp", ttl_seconds=-10, db_path=self.db)
        create_web_session("student", "token_valid", ttl_seconds=3600, db_path=self.db)
        create_web_session("student", "token_rev", ttl_seconds=3600, db_path=self.db)
        revoke_web_session("token_rev", db_path=self.db)

        deleted = cleanup_expired_sessions(db_path=self.db)
        self.assertEqual(deleted, 2)
        self.assertIsNotNone(get_web_session("token_valid", db_path=self.db))
        self.assertIsNone(get_web_session("token_exp", db_path=self.db))

    @patch.dict(os.environ, {"APP_USERNAME": "student", "APP_PASSWORD": "secret_pwd"})
    def test_local_client_login_logout(self):
        from backend.api.local_client import login_api, logout_api, auth_me_api

        info = login_api("student", "secret_pwd", db_path=self.db)
        self.assertEqual(info["user_id"], "student")
        self.assertTrue("token" in info)

        me = auth_me_api(token=info["token"], db_path=self.db)
        self.assertEqual(me["user_id"], "student")

        ok = logout_api(token=info["token"], db_path=self.db)
        self.assertTrue(ok)



class TestF2Sessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.client = TestClient(create_app(self.db, auth_mode="local"))

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_empty_sessions_and_create(self):
        empty = self.client.get("/v1/sessions", params={"user_id": "student"})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), {"sessions": [], "total": 0})

        created = self.client.post("/v1/sessions", json={"user_id": "student", "title": "数学学习"})
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["session_id"]
        self.assertTrue(session_id)

        listed = self.client.get("/v1/sessions", params={"user_id": "student"})
        self.assertEqual(listed.status_code, 200)
        body = listed.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["sessions"][0]["id"], session_id)
        self.assertEqual(body["sessions"][0]["title"], "数学学习")
        self.assertEqual(body["sessions"][0]["message_count"], 0)

    def test_session_messages_and_404(self):
        missing = self.client.get("/v1/sessions/non_existent_id/messages")
        self.assertEqual(missing.status_code, 404)

        sid = start_session("student", title="物理讨论", db_path=self.db)
        append_message(sid, "user", "什么是动量定理？", db_path=self.db)
        append_message(sid, "assistant", "动量定理是指合外力的冲量等于动量的增量。", db_path=self.db)

        res = self.client.get(f"/v1/sessions/{sid}/messages")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["session_id"], sid)
        self.assertEqual(len(body["messages"]), 2)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn("动量定理", body["messages"][0]["content"])
        self.assertTrue("created_at" in body["messages"][0])

    def test_user_isolation_and_pagination(self):
        s1 = start_session("student_a", title="A1", db_path=self.db)
        s2 = start_session("student_a", title="A2", db_path=self.db)
        s3 = start_session("student_b", title="B1", db_path=self.db)

        res_a = self.client.get("/v1/sessions", params={"user_id": "student_a", "limit": 1, "offset": 0})
        self.assertEqual(res_a.status_code, 200)
        body_a = res_a.json()
        self.assertEqual(body_a["total"], 2)
        self.assertEqual(len(body_a["sessions"]), 1)
        self.assertEqual(body_a["sessions"][0]["id"], s2)

        res_b = self.client.get("/v1/sessions", params={"user_id": "student_b"})
        self.assertEqual(res_b.status_code, 200)
        body_b = res_b.json()
        self.assertEqual(body_b["total"], 1)
        self.assertEqual(body_b["sessions"][0]["id"], s3)

    def test_session_user_isolation_strict(self):
        # 严格校验 Cookie 登录态下的跨用户隔离
        app = create_app(self.db, auth_mode="password")
        client_a = TestClient(app)
        create_web_session("student_a", "tok_a", db_path=self.db)
        client_a.cookies.set("study_session", "tok_a")

        s_b = start_session("student_b", title="B专属对话", db_path=self.db)
        append_message(s_b, "user", "B的私密笔记", db_path=self.db)

        # student_a 尝试获取 student_b 的会话列表 -> 不得泄露，仅返回 student_a 自身
        res_list = client_a.get("/v1/sessions", params={"user_id": "student_b"})
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(res_list.json()["total"], 0)

        # student_a 尝试直接读取 student_b 的会话消息 -> 404
        res_msg = client_a.get(f"/v1/sessions/{s_b}/messages")
        self.assertEqual(res_msg.status_code, 404)

        # student_a 创建会话时伪造 user_id=student_b -> 强制归属为 student_a
        create_res = client_a.post("/v1/sessions", json={"user_id": "student_b", "title": "A新建"})
        self.assertEqual(create_res.status_code, 200)
        new_sid = create_res.json()["session_id"]
        from backend.platform.chat_store import get_session
        sess_info = get_session(new_sid, db_path=self.db)
        self.assertEqual(sess_info["user_id"], "student_a")


class TestF3VisionOcr(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_successful_ocr(self):
        def fake_ocr(path: str, focus: str = "全部") -> str:
            self.assertTrue(Path(path).is_file())
            return "题目：求导数 f'(x) 当 f(x) = x^2"

        app = create_app(self.db, auth_mode="local", ocr_fn=fake_ocr)
        client = TestClient(app)

        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("test.png", png_bytes, "image/png")},
            data={"focus": "题干"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("求导数", data["text"])
        self.assertTrue(data["elapsed_ms"] >= 0)
        self.assertTrue(data["model"])

    def test_bad_format_rejected(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)

        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("test.txt", b"plain text", "text/plain")},
        )
        self.assertEqual(res.status_code, 400)

    def test_empty_file_rejected(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)

        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("test.jpg", b"", "image/jpeg")},
        )
        self.assertEqual(res.status_code, 400)

    def test_oversized_file_rejected(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)

        oversized = b"\x00" * (5 * 1024 * 1024 + 10)
        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("big.jpg", oversized, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 413)

    def test_unconfigured_api_key_maps_to_503(self):
        def fake_no_key(path: str, focus: str = "全部") -> str:
            return "未配置 DASHSCOPE_API_KEY，无法识图。请在 .env 中设置通义千问 API Key。"

        app = create_app(self.db, auth_mode="local", ocr_fn=fake_no_key)
        client = TestClient(app)

        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 20, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("DASHSCOPE_API_KEY", res.json()["detail"])

    def test_model_failure_maps_to_502(self):
        def fake_model_err(path: str, focus: str = "全部") -> str:
            return "视觉模型调用失败: connection reset"

        app = create_app(self.db, auth_mode="local", ocr_fn=fake_model_err)
        client = TestClient(app)

        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 20, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 502)

    def test_octet_stream_with_invalid_extension_rejected(self):
        app = create_app(self.db, auth_mode="local", ocr_fn=lambda p, focus="": "ok")
        client = TestClient(app)

        # 恶意可执行文件或未知二进制即使伪装成 application/octet-stream 亦必须被拦截
        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("exploit.exe", b"MZ12345", "application/octet-stream")},
        )
        self.assertEqual(res.status_code, 400)

    def test_ocr_reader_exception_handled(self):
        def crash_ocr(path: str, focus: str = "全部") -> str:
            raise RuntimeError("unexpected dashscope crash")

        app = create_app(self.db, auth_mode="local", ocr_fn=crash_ocr)
        client = TestClient(app)
        res = client.post(
            "/v1/vision/ocr",
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 20, "image/jpeg")},
        )
        self.assertEqual(res.status_code, 502)



class TestF4CodeTutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.client = TestClient(create_app(self.db, auth_mode="local"))

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_run_code_passed(self):
        res = self.client.post(
            "/v1/code/run",
            json={
                "code": "def add(a, b):\n    return a + b\n",
                "tests": "assert add(1, 2) == 3\nprint('TESTS_PASSED')",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "passed")
        self.assertEqual(data["exit_code"], 0)
        self.assertIn("TESTS_PASSED", data["stdout"])
        self.assertFalse(data["timed_out"])
        self.assertTrue(data["thread_id"])

    def test_run_code_assertion_failure(self):
        res = self.client.post(
            "/v1/code/run",
            json={
                "code": "def add(a, b):\n    return a - b\n",
                "tests": "assert add(1, 2) == 3",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["exit_code"], 1)
        self.assertIn("AssertionError", data["stderr"])

    def test_run_code_timeout(self):
        res = self.client.post(
            "/v1/code/run",
            json={
                "code": "while True:\n    pass\n",
                "timeout_s": 0.5,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "timeout")
        self.assertTrue(data["timed_out"])
        self.assertEqual(data["exit_code"], 1)

    def test_code_oversized_rejected(self):
        big_code = "x = 1\n" * 12000  # > 50KB
        res = self.client.post("/v1/code/run", json={"code": big_code})
        self.assertEqual(res.status_code, 400)
        self.assertIn("50KB", res.json()["detail"])

    def test_code_hint(self):
        obs = "状态: failed\n异常: ZeroDivisionError\n信息: division by zero\n行号: 3\n"
        res = self.client.post("/v1/code/hint", json={"level": 2, "observation": obs})
        self.assertEqual(res.status_code, 200)
        hint = res.json()["hint"]
        self.assertIn("ZeroDivisionError", hint)
        self.assertIn("第 2 级", hint)

    def test_code_attempts_history(self):
        thread_id = "test_thread_abc"
        self.client.post(
            "/v1/code/run",
            json={"code": "x = 1", "thread_id": thread_id, "user_id": "student"},
        )
        self.client.post(
            "/v1/code/run",
            json={"code": "x = 2", "thread_id": thread_id, "user_id": "student"},
        )

        res = self.client.get(
            "/v1/code/attempts",
            params={"thread_id": thread_id, "user_id": "student"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["thread_id"], thread_id)
        attempts = body["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["seq"], 1)
        self.assertEqual(attempts[0]["code"], "x = 1")
        self.assertEqual(attempts[1]["seq"], 2)
        self.assertEqual(attempts[1]["code"], "x = 2")

    def test_code_oversized_tests_rejected(self):
        big_tests = "assert True\n" * 5000  # > 50KB
        res = self.client.post("/v1/code/run", json={"code": "x = 1", "tests": big_tests})
        self.assertEqual(res.status_code, 400)
        self.assertIn("测试代码长度", res.json()["detail"])

    def test_code_attempts_user_isolation(self):
        app = create_app(self.db, auth_mode="password")
        client_a = TestClient(app)
        create_web_session("student_a", "tok_a", db_path=self.db)
        client_a.cookies.set("study_session", "tok_a")

        # student_b 有一次代码尝试
        from backend.platform.code_attempt_store import append_attempt
        append_attempt("student_b", "thread_b", "print('b code')", "", {"status": "passed"}, db_path=self.db)

        # student_a 尝试查询 student_b 的记录 -> 必须被隔离为空
        res = client_a.get("/v1/code/attempts", params={"user_id": "student_b", "thread_id": "thread_b"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["attempts"], [])

    def test_code_attempts_negative_limit(self):
        thread_id = "thread_lim"
        self.client.post("/v1/code/run", json={"code": "x = 1", "thread_id": thread_id})
        res = self.client.get("/v1/code/attempts", params={"thread_id": thread_id, "limit": 0})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["attempts"], [])



class TestCorsAndOptions(unittest.TestCase):
    def test_cors_preflight(self):
        app = create_app()
        client = TestClient(app)
        res = client.options(
            "/v1/tools",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")



class TestF5Dashboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.app = create_app(self.db, auth_mode="local")
        self.client = TestClient(self.app)

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_empty_dashboard_summary(self):
        res = self.client.get("/v1/dashboard/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user_id"], "student")
        self.assertEqual(data["overview"]["session_count"], 0)
        self.assertEqual(data["overview"]["message_count"], 0)
        self.assertEqual(data["overview"]["document_count"], 0)
        self.assertEqual(data["mistakes"]["total"], 0)
        self.assertEqual(data["mistakes"]["due_today"], 0)
        self.assertEqual(data["mastery"]["total_concepts"], 0)
        self.assertEqual(data["mastery"]["average_score"], 0.0)
        self.assertEqual(data["mastery"]["distribution"], {"low": 0, "medium": 0, "high": 0})
        self.assertEqual(data["recent_runs"], [])
        self.assertIsNone(data["latest_evaluation"])

    def test_dashboard_summary_with_data(self):
        import sqlite3
        from datetime import datetime, timezone, timedelta
        from backend.platform.chat_store import start_session, append_message
        from backend.platform.domain_store import add_document_record, upsert_mastery
        from backend.platform.mistake_store import create_pending, confirm_mistake

        from backend.platform.trace_store import init_trace_db
        from backend.platform.eval_runner import ensure_eval_tables
        init_trace_db(self.db)
        ensure_eval_tables(self.db)

        # 1. Sessions & Messages
        s1 = start_session("student", "会话1", db_path=self.db)
        append_message(s1, "user", "你好", db_path=self.db)
        append_message(s1, "assistant", "你好！", db_path=self.db)

        # 2. Documents
        add_document_record("doc1", "算法导论", path="/tmp/algo.pdf", chunks=10, user_id="student", db_path=self.db)

        # 3. Mistakes
        m1 = create_pending("student", "数学", "导数", "计算错", "求导", db_path=self.db)
        confirm_mistake(m1, db_path=self.db)  # becomes confirmed, next_review_at in future
        m2 = create_pending("student", "数学", "极限", "概念错", "求极限", db_path=self.db)  # pending

        # 模拟一条今日到期的错题
        with sqlite3.connect(str(self.db)) as c_m:
            past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            c_m.execute("UPDATE mistakes SET next_review_at = ? WHERE id = ?", (past_time, m1))
            c_m.commit()

        # 4. Mastery, Runs, Eval runs
        with sqlite3.connect(str(self.db)) as c:
            now_iso = datetime.now(timezone.utc).isoformat()
            c.execute("INSERT INTO mastery (user_id, concept, score, attempts, last_seen) VALUES ('student', '二分查找', 0.9, 5, ?)", (now_iso,))
            c.execute("INSERT INTO mastery (user_id, concept, score, attempts, last_seen) VALUES ('student', '动态规划', 0.5, 3, ?)", (now_iso,))
            c.execute("INSERT INTO mastery (user_id, concept, score, attempts, last_seen) VALUES ('student', '图论', 0.2, 1, ?)", (now_iso,))

            # 5. Runs (关联 session s1)
            c.execute(
                """
                INSERT INTO runs (id, session_id, user_input, final_answer, iterations, tools_used, latency_ms, status, created_at, model, cost_yuan)
                VALUES ('run_1', ?, '请帮我写个快速排序', '好的，这是快排', 1, '[]', 250, 'success', ?, 'qwen2.5', 0.002)
                """,
                (s1, now_iso),
            )

            # 6. Eval runs
            c.execute(
                """
                INSERT INTO eval_runs (id, dataset_name, dataset_version, mode, status, sample_count, passed, summary_json, started_at, finished_at)
                VALUES ('eval_1', 'qa_baseline', 'v5', 'dry-run', 'passed', 10, 9, '{"faithfulness": 0.95}', '2026-11-05T01:00:00Z', '2026-11-05T01:05:00Z')
                """
            )
            c.commit()

        res = self.client.get("/v1/dashboard/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["overview"]["session_count"], 1)
        self.assertEqual(data["overview"]["message_count"], 2)
        self.assertEqual(data["overview"]["document_count"], 1)

        self.assertEqual(data["mistakes"]["total"], 2)
        self.assertEqual(data["mistakes"]["pending"], 1)
        self.assertEqual(data["mistakes"]["confirmed"], 1)
        self.assertEqual(data["mistakes"]["due_today"], 1)

        self.assertEqual(data["mastery"]["total_concepts"], 3)
        self.assertAlmostEqual(data["mastery"]["average_score"], 0.53, places=2)
        self.assertEqual(data["mastery"]["distribution"]["low"], 1)
        self.assertEqual(data["mastery"]["distribution"]["medium"], 1)
        self.assertEqual(data["mastery"]["distribution"]["high"], 1)

        self.assertEqual(len(data["recent_runs"]), 1)
        self.assertEqual(data["recent_runs"][0]["prompt_preview"], "请帮我写个快速排序")
        self.assertEqual(data["recent_runs"][0]["model"], "qwen2.5")

        self.assertIsNotNone(data["latest_evaluation"])
        self.assertEqual(data["latest_evaluation"]["dataset_name"], "qa_baseline")
        self.assertEqual(data["latest_evaluation"]["pass_rate"], 0.9)
        self.assertEqual(data["latest_evaluation"]["summary"], {"faithfulness": 0.95})

    def test_dashboard_user_isolation(self):
        app = create_app(self.db, auth_mode="password")
        client_a = TestClient(app)
        create_web_session("student_a", "tok_a", db_path=self.db)
        client_a.cookies.set("study_session", "tok_a")

        # student_b 有数据
        from backend.platform.chat_store import start_session
        s_b = start_session("student_b", "B的私密会话", db_path=self.db)

        # student_a 越权请求 student_b 的看板 -> 403 Forbidden
        res_forbidden = client_a.get("/v1/dashboard/summary", params={"user_id": "student_b"})
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertIn("无权访问", res_forbidden.json()["detail"])

        # student_a 查看自己的看板 -> 干净隔离 (0)
        res_own = client_a.get("/v1/dashboard/summary")
        self.assertEqual(res_own.status_code, 200)
        self.assertEqual(res_own.json()["overview"]["session_count"], 0)


class TestF6DocumentsUpload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.app = create_app(self.db, auth_mode="local")
        self.client = TestClient(self.app)

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_upload_non_pdf_rejected(self):
        fake_file = io.BytesIO(b"print('hello')")
        res = self.client.post(
            "/v1/documents/upload",
            files={"file": ("exploit.py", fake_file, "text/x-python")},
            data={"subject": "编程"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("仅支持合法的 PDF", res.json()["detail"])

    def test_upload_fake_pdf_magic_bytes_rejected(self):
        fake_file = io.BytesIO(b"NOT_A_REAL_PDF_HEADER_CONTENT")
        res = self.client.post(
            "/v1/documents/upload",
            files={"file": ("fake.pdf", fake_file, "application/pdf")},
            data={"subject": "计算机"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("不是合法的 PDF 格式", res.json()["detail"])

    def test_upload_empty_pdf_rejected(self):
        empty_file = io.BytesIO(b"")
        res = self.client.post(
            "/v1/documents/upload",
            files={"file": ("empty.pdf", empty_file, "application/pdf")},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("上传文档为空", res.json()["detail"])

    def test_upload_oversized_pdf_rejected(self):
        # 超过 20MB: 创建以 %PDF- 开头的大流（用 mock 或流式生成）
        big_content = b"%PDF-" + b"0" * (20 * 1024 * 1024 + 10)
        big_file = io.BytesIO(big_content)
        res = self.client.post(
            "/v1/documents/upload",
            files={"file": ("oversized.pdf", big_file, "application/pdf")},
        )
        self.assertEqual(res.status_code, 413)
        self.assertIn("超过 20MB", res.json()["detail"])

    def test_upload_scanned_or_empty_text_rejected(self):
        # 伪造有效魔数但无可提取文本的 PDF
        dummy_pdf = io.BytesIO(b"%PDF-1.4 header without text")
        with patch("backend.knowledge.pdf_loader.extract_text_from_pdf", return_value={"text": "", "pages": 1, "metadata": {}}):
            res = self.client.post(
                "/v1/documents/upload",
                files={"file": ("blank.pdf", dummy_pdf, "application/pdf")},
            )
            self.assertEqual(res.status_code, 422)
            self.assertIn("无法从 PDF 中提取有效文本", res.json()["detail"])

    def test_upload_success_and_reflected_in_f5_dashboard(self):
        fixture_path = Path("tests/fixtures/sample.pdf")
        if not fixture_path.exists():
            self.skipTest("sample.pdf fixture not found")

        with open(fixture_path, "rb") as f:
            pdf_bytes = f.read()

        # Mock FAISS kb.add_pdf
        class MockKB:
            def __init__(self):
                self.doc_info = {}
            def add_pdf(self, path, doc_id=None, title=None, subject=None, chunk_size=500, chunk_overlap=50):
                self.doc_info[doc_id] = {"chunk_count": 5}
                return True

        mock_kb = MockKB()
        app = create_app(self.db, auth_mode="local", kb_factory=lambda: mock_kb)
        client = TestClient(app)

        res = client.post(
            "/v1/documents/upload",
            files={"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"subject": "英语", "title": "英语学习指南"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["title"], "英语学习指南")
        self.assertEqual(data["subject"], "英语")
        self.assertEqual(data["chunks"], 5)
        self.assertEqual(data["status"], "indexed")
        self.assertTrue(data["doc_id"].startswith("doc_"))

        # 联动验证 F5 看板：document_count 必须实时 +1
        dash_res = client.get("/v1/dashboard/summary")
        self.assertEqual(dash_res.status_code, 200)
        self.assertEqual(dash_res.json()["overview"]["document_count"], 1)



class TestF7QuizGrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_quiz_grade_blank_inputs_rejected(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)

        res1 = client.post("/v1/quiz/grade", json={"questions": "", "answers": "我的答案"})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("questions 不能为空", res1.json()["detail"])

        res2 = client.post("/v1/quiz/grade", json={"questions": "1+1=?", "answers": ""})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("answers 不能为空", res2.json()["detail"])

    def test_quiz_grade_oversized_rejected(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)

        big_text = "题目 " * 10000
        res = client.post("/v1/quiz/grade", json={"questions": big_text, "answers": "1"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("超出最大长度限制", res.json()["detail"])

    def test_quiz_grade_unconfigured_api_key_503(self):
        app = create_app(self.db, auth_mode="local")
        client = TestClient(app)

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "", "OPENAI_API_KEY": ""}):
            res = client.post("/v1/quiz/grade", json={"questions": "1+1=?", "answers": "2"})
            self.assertEqual(res.status_code, 503)
            self.assertIn("未配置", res.json()["detail"])

    def test_quiz_grade_success(self):
        def mock_grader(questions, answers):
            return f"| 1 | {answers} | 正确 | 2 | 基础算术 |\n\n总分: 1/1"

        app = create_app(self.db, auth_mode="local", quiz_grade_fn=mock_grader)
        client = TestClient(app)

        res = client.post("/v1/quiz/grade", json={"questions": "1+1=?", "answers": "2"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("feedback", data)
        self.assertIn("总分: 1/1", data["feedback"])

    def test_quiz_grade_model_exception_mapped_to_502(self):
        def failing_grader(questions, answers):
            raise RuntimeError("Remote LLM Connection Timeout")

        app = create_app(self.db, auth_mode="local", quiz_grade_fn=failing_grader)
        client = TestClient(app)

        res = client.post("/v1/quiz/grade", json={"questions": "1+1=?", "answers": "2"})
        self.assertEqual(res.status_code, 502)
        self.assertIn("批改模型调用失败", res.json()["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
