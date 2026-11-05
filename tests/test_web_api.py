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
)
from backend.platform.chat_store import append_message, start_session


class TestF1Auth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

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


class TestF2Sessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.client = TestClient(create_app(self.db, auth_mode="local"))

    def tearDown(self):
        self.tmp.cleanup()

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


class TestF3VisionOcr(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"

    def tearDown(self):
        self.tmp.cleanup()

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


class TestF4CodeTutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.client = TestClient(create_app(self.db, auth_mode="local"))

    def tearDown(self):
        self.tmp.cleanup()

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
