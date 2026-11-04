"""
视觉识题工具测试（不调用真实 VL API）
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestVision(unittest.TestCase):
    def test_read_image_missing_file(self):
        from backend.tools.vision import read_image

        result = read_image("/nonexistent/path/image.png")
        self.assertIn("不存在", result)

    def test_read_image_no_api_key(self):
        from backend.tools import vision

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNG\r\n\x1a\n")
            path = tmp.name
        try:
            with mock.patch.object(vision, "DASHSCOPE_API_KEY", ""):
                result = vision.read_image(path)
            self.assertIn("DASHSCOPE_API_KEY", result)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_compress_large_image(self):
        from backend.tools.vision import _compress_image_bytes

        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow 未安装")

        import io

        buf = io.BytesIO()
        img = Image.new("RGB", (2400, 1800), color=(200, 100, 50))
        img.save(buf, format="PNG")
        raw = buf.getvalue()
        compressed, subtype = _compress_image_bytes(raw)
        self.assertEqual(subtype, "jpeg")
        self.assertLess(len(compressed), len(raw))


class TestToolRegistry(unittest.TestCase):
    def test_read_image_registered(self):
        from backend.agents.tool_registry import get_tool_spec

        spec = get_tool_spec("read_image")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.timeout_s, 90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
