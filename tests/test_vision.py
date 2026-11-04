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


class TestOcrPreview(unittest.TestCase):
    def test_preview_passes_bytes_to_the_reader_and_deletes_the_file(self):
        from frontend.qa_image import preview_image_text

        seen = {}

        def reader(path: str) -> str:
            file_path = Path(path)
            seen["exists"] = file_path.is_file()
            seen["bytes"] = file_path.read_bytes()
            seen["path"] = path
            return "1. 求 x 的值"

        text = preview_image_text(b"png-bytes", ".png", reader=reader)
        self.assertEqual(text, "1. 求 x 的值")
        self.assertTrue(seen["exists"])
        self.assertEqual(seen["bytes"], b"png-bytes")
        self.assertFalse(Path(seen["path"]).exists())

    def test_empty_image_does_not_call_the_reader(self):
        from frontend.qa_image import preview_image_text

        def reader(path: str) -> str:
            raise AssertionError("空图片不应识图")

        self.assertIn("空", preview_image_text(b"", ".png", reader=reader))

    def test_same_image_is_not_filled_again(self):
        from frontend.qa_image import remember_ocr_preview

        state = {}
        self.assertTrue(remember_ocr_preview(state, "file-1", "题干"))
        state["qa_ocr_override"] = "用户改过的题干"
        self.assertFalse(remember_ocr_preview(state, "file-1", "新的识别"))
        self.assertEqual(state["qa_ocr_override"], "用户改过的题干")
        self.assertTrue(remember_ocr_preview(state, "file-2", "另一题"))
        self.assertEqual(state["qa_ocr_override"], "另一题")

    def test_qa_page_fills_the_edit_box_without_calling_the_model(self):
        from streamlit.testing.v1 import AppTest

        import io

        from PIL import Image

        import frontend.qa_image as qa_image

        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), color=(255, 255, 255)).save(buffer, format="PNG")
        png = buffer.getvalue()
        original = qa_image.preview_image_text
        qa_image.preview_image_text = lambda raw, suffix=".jpg", reader=None: "回填的题干"
        app = str(PROJECT_ROOT / "frontend" / "app.py")
        try:
            at = AppTest.from_file(app, default_timeout=120)
            at.session_state["authenticated"] = True
            at.session_state["auth_user"] = "student"
            at.session_state["current_page"] = "qa"
            at.run()
            self.assertEqual([str(item.value) for item in at.exception], [])
            at.file_uploader[0].upload("question.png", png, "image/png").run()
            self.assertEqual([str(item.value) for item in at.exception], [])
            filled = [
                area.value
                for area in at.text_area
                if area.label == "识别结果修正（可选）"
            ]
            self.assertEqual(filled, ["回填的题干"])
        finally:
            qa_image.preview_image_text = original


class TestToolRegistry(unittest.TestCase):
    def test_read_image_registered(self):
        from backend.agents.tool_registry import get_tool_spec

        spec = get_tool_spec("read_image")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.timeout_s, 90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
