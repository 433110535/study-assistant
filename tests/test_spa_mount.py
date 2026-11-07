"""
FastAPI 静态产物托管与 SPA 路由 Fallback 验收测试 (U6 阶段)。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app


class TestSpaMountAndFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.dist_dir = cls.project_root / "web_UI" / "dist"
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    def test_root_redirects_to_app(self):
        resp = self.client.get("/", follow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 307, 308))
        self.assertEqual(resp.headers.get("location"), "/app")

    def test_app_and_app_slash_return_index_html(self):
        if not (self.dist_dir / "index.html").is_file():
            self.skipTest("web_UI/dist/index.html not built yet")

        for path in ("/app", "/app/"):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("text/html", resp.headers.get("content-type", ""))
            self.assertIn('<div id="root">', resp.text)
            self.assertEqual(resp.headers.get("cache-control"), "no-cache")

    def test_spa_deep_routes_fallback_to_index_html(self):
        if not (self.dist_dir / "index.html").is_file():
            self.skipTest("web_UI/dist/index.html not built yet")

        deep_routes = [
            "/app/chat",
            "/app/chat/",
            "/app/practice",
            "/app/practice/",
            "/app/review",
            "/app/knowledge",
            "/app/code",
            "/app/code/",
        ]
        for route in deep_routes:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} failed")
            self.assertIn("text/html", resp.headers.get("content-type", ""))
            self.assertIn('<div id="root">', resp.text)
            self.assertEqual(resp.headers.get("cache-control"), "no-cache")

    def test_real_assets_serve_with_correct_content_type(self):
        assets_dir = self.dist_dir / "assets"
        if not assets_dir.is_dir():
            self.skipTest("assets directory not found")

        js_files = list(assets_dir.glob("*.js"))
        css_files = list(assets_dir.glob("*.css"))
        self.assertTrue(len(js_files) > 0, "No JS files found in dist/assets")
        self.assertTrue(len(css_files) > 0, "No CSS files found in dist/assets")

        sample_js = js_files[0].name
        resp_js = self.client.get(f"/app/assets/{sample_js}")
        self.assertEqual(resp_js.status_code, 200)
        self.assertTrue(
            any(t in resp_js.headers.get("content-type", "") for t in ("javascript", "application/x-javascript")),
            f"Unexpected content-type: {resp_js.headers.get('content-type')}",
        )

        sample_css = css_files[0].name
        resp_css = self.client.get(f"/app/assets/{sample_css}")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn("text/css", resp_css.headers.get("content-type", ""))

        if (self.dist_dir / "favicon.svg").is_file():
            resp_svg = self.client.get("/app/favicon.svg")
            self.assertEqual(resp_svg.status_code, 200)
            self.assertIn("image/svg+xml", resp_svg.headers.get("content-type", ""))

    def test_root_favicon_routes(self):
        if not (self.dist_dir / "favicon.svg").is_file():
            self.skipTest("web_UI/dist/favicon.svg not present")

        for fav_path in ("/favicon.ico", "/favicon.svg"):
            resp = self.client.get(fav_path)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(
                any(t in resp.headers.get("content-type", "") for t in ("image/svg+xml", "image/x-icon")),
                f"Unexpected favicon content-type: {resp.headers.get('content-type')}",
            )

    def test_missing_static_assets_and_directories_return_404_not_html(self):
        # 缺失的静态资源文件必须 404，不得回退 HTML
        resp = self.client.get("/app/assets/missing_asset_12345.js")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('<div id="root">', resp.text)

        resp2 = self.client.get("/app/static/missing_script.css")
        self.assertEqual(resp2.status_code, 404)
        self.assertNotIn('<div id="root">', resp2.text)

        # 静态资源目录自身禁止当作 SPA 路由回退 HTML
        resp_assets_dir = self.client.get("/app/assets")
        self.assertEqual(resp_assets_dir.status_code, 404)
        self.assertNotIn('<div id="root">', resp_assets_dir.text)

        resp_assets_slash = self.client.get("/app/assets/")
        self.assertEqual(resp_assets_slash.status_code, 404)
        self.assertNotIn('<div id="root">', resp_assets_slash.text)

    def test_path_traversal_returns_404(self):
        resp = self.client.get("/app/../../etc/passwd")
        self.assertEqual(resp.status_code, 404)

        resp2 = self.client.get("/app/../backend/api/app.py")
        self.assertEqual(resp2.status_code, 404)

    def test_dist_missing_returns_503_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_app = create_app(dist_dir=Path(tmp_dir))
            client = TestClient(test_app)
            resp = client.get("/app")
            self.assertEqual(resp.status_code, 503)
            self.assertIn("Frontend build artifacts not found", resp.json().get("detail", ""))

    def test_api_routes_unaffected_in_local_mode(self):
        resp_health = self.client.get("/health")
        self.assertEqual(resp_health.status_code, 200)
        self.assertEqual(resp_health.json(), {"status": "ok"})

        resp_me = self.client.get("/v1/auth/me")
        self.assertEqual(resp_me.status_code, 200)
        self.assertEqual(resp_me.json(), {"user_id": "student", "mode": "local"})


if __name__ == "__main__":
    unittest.main()
