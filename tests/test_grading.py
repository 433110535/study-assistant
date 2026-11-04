"""对照标准答案的判分、错因和变式。不调用大模型。"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestGrading(unittest.TestCase):
    def test_numeric_equivalence(self):
        from backend.tools.grading import grade_item

        self.assertEqual(grade_item("求值", "1/2", "0.5")["status"], "correct")
        self.assertEqual(grade_item("求值", "1", "0.5||2/2")["status"], "correct")
        self.assertEqual(grade_item("求值", "２", "2.0")["status"], "correct")
        self.assertEqual(grade_item("求值", "50%", "0.5")["status"], "correct")

    def test_incorrect_and_blank(self):
        from backend.tools.grading import grade_item

        wrong = grade_item("2+2", "5", "4")
        self.assertEqual(wrong["status"], "incorrect")
        self.assertEqual(wrong["score"], 0)
        blank = grade_item("2+2", "  ", "4")
        self.assertEqual(blank["reason"], "未作答")

    def test_ungraded_without_key(self):
        from backend.tools.grading import format_grade, grade_item

        result = grade_item("2+2", "4", "")
        self.assertEqual(result["status"], "ungraded")
        self.assertIsNone(result["score"])
        self.assertIn("不要告诉用户", format_grade(result))

    def test_diagnosis_rules(self):
        from backend.tools.grading import ERROR_CALC, ERROR_CONCEPT, ERROR_READING, diagnose_error

        self.assertEqual(diagnose_error("2+2", "4", "4")["error_type"], "")
        self.assertEqual(diagnose_error("2+2", "", "4")["error_type"], ERROR_READING)
        self.assertEqual(diagnose_error("2+2", "-4", "4")["error_type"], ERROR_CALC)
        self.assertEqual(diagnose_error("2+2", "40", "4")["error_type"], ERROR_CALC)
        copied = diagnose_error("质量为 2kg 的物体受 4N 力，加速度是多少？", "4", "2")
        self.assertEqual(copied["error_type"], ERROR_READING)
        concept = diagnose_error("Python 用什么关键字定义函数？", "函数", "def")
        self.assertEqual(concept["error_type"], ERROR_CONCEPT)
        missing = diagnose_error("2+2", "4", "")
        self.assertEqual(missing["error_type"], "其他")

    def test_variants_shift_numbers_without_leaking_answer(self):
        from backend.tools.grading import format_variants, make_variants

        question = "小明有3个苹果，又买了5个，一共几个？"
        first = make_variants(question, count=3)
        again = make_variants(question, count=3)
        self.assertEqual(first["status"], "ready")
        self.assertEqual([item["stem"] for item in first["items"]], [item["stem"] for item in again["items"]])
        stems = [item["stem"] for item in first["items"]]
        self.assertEqual(len(set(stems)), 3)
        for stem in stems:
            self.assertNotEqual(stem, question)
            self.assertNotIn("3个苹果", stem)
        text = format_variants(first)
        self.assertIn("不附答案", text)
        self.assertNotIn("answer", text.lower())

    def test_variants_refuse_without_numbers(self):
        from backend.tools.grading import make_variants

        result = make_variants("什么是递归？")
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["items"], [])

    def test_text_variant_swaps_listed_names_without_a_model(self):
        from backend.tools.grading import format_variants, make_variants

        question = "小明比小红高吗？"
        result = make_variants(question, count=3)
        again = make_variants(question, count=3)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            [item["stem"] for item in result["items"]],
            ["小红比小华高吗？", "小华比小李高吗？", "小李比小王高吗？"],
        )
        self.assertEqual(
            [item["stem"] for item in result["items"]],
            [item["stem"] for item in again["items"]],
        )
        self.assertTrue(all(item["answer"] is None for item in result["items"]))
        text = format_variants(result)
        self.assertIn("不附答案", text)
        self.assertNotIn("答案:", text)

    def test_text_variant_swaps_listed_objects(self):
        from backend.tools.grading import make_variants

        result = make_variants("买一个苹果。", count=1)
        self.assertEqual(result["items"][0]["stem"], "买一个香蕉。")
        self.assertIsNone(result["items"][0]["answer"])

    def test_object_variants_do_not_repeat_original_or_each_other(self):
        from backend.tools.grading import make_variants

        question = "买一个苹果。"
        result = make_variants(question, count=5)
        again = make_variants(question, count=5)
        self.assertEqual(result["status"], "ready")
        stems = [item["stem"] for item in result["items"]]
        self.assertEqual(stems, [item["stem"] for item in again["items"]])
        self.assertGreaterEqual(len(stems), 1)
        self.assertLess(len(stems), 5)
        self.assertEqual(len(set(stems)), len(stems))
        self.assertNotIn(question, stems)
        self.assertTrue(all(item["answer"] is None for item in result["items"]))
        self.assertEqual(stems, ["买一个香蕉。", "买一个橘子。", "买一个梨。"])

        names = make_variants("小明比小红高吗？", count=5)
        name_stems = [item["stem"] for item in names["items"]]
        self.assertEqual(names["status"], "ready")
        self.assertEqual(len(name_stems), 5)
        self.assertEqual(len(set(name_stems)), len(name_stems))
        self.assertNotIn("小明比小红高吗？", name_stems)
        self.assertEqual(
            name_stems[:3],
            ["小红比小华高吗？", "小华比小李高吗？", "小李比小王高吗？"],
        )

    def test_arithmetic_variant_keeps_hidden_answer(self):
        from backend.tools.grading import format_variants, make_variants

        result = make_variants("计算 8/2", count=1)
        self.assertEqual(result["status"], "ready")
        self.assertIsNotNone(result["items"][0]["answer"])
        self.assertNotIn("答案:", format_variants(result))


class TestGradePaper(unittest.TestCase):
    """整卷按题号离线判分。期望值是写死的字面结果，不调用模型。"""

    def test_two_numeric_items_one_right_one_wrong_have_no_total(self):
        from backend.tools.grading import grade_paper

        paper = (
            "1. 3+4等于多少？\n"
            "作答：7\n"
            "标准答案：7\n"
            "\n"
            "2. 9-4等于多少？\n"
            "作答：4\n"
            "标准答案：5\n"
        )
        result = grade_paper(paper)
        self.assertEqual(set(result), {"items", "graded_count", "ungraded_count"})
        self.assertEqual(result["graded_count"], 2)
        self.assertEqual(result["ungraded_count"], 0)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["number"], "1")
        self.assertEqual(result["items"][0]["question_text"], "3+4等于多少？")
        self.assertEqual(result["items"][0]["student_answer"], "7")
        self.assertEqual(result["items"][0]["correct_answer"], "7")
        self.assertEqual(result["items"][0]["status"], "correct")
        self.assertEqual(result["items"][0]["score"], 1)
        self.assertEqual(result["items"][1]["number"], "2")
        self.assertEqual(result["items"][1]["status"], "incorrect")
        self.assertEqual(result["items"][1]["score"], 0)
        self.assertNotIn("total", result)
        self.assertNotIn("total_score", result)

    def test_missing_key_on_second_item_is_ungraded(self):
        from backend.tools.grading import grade_paper

        paper = (
            "1. 3+4等于多少？\n"
            "作答：7\n"
            "标准答案：7\n"
            "\n"
            "2. 9-4等于多少？\n"
            "作答：5\n"
        )
        result = grade_paper(paper)
        self.assertEqual(result["items"][0]["status"], "correct")
        self.assertEqual(result["items"][1]["status"], "ungraded")
        self.assertIsNone(result["items"][1]["score"])
        self.assertEqual(result["items"][1]["correct_answer"], "")
        self.assertEqual(result["graded_count"], 1)
        self.assertEqual(result["ungraded_count"], 1)

    def test_answer_key_dict_grades_without_inline_key(self):
        from backend.tools.grading import grade_paper

        paper = (
            "1. 3+4等于多少？\n"
            "作答：7\n"
            "\n"
            "2、9-4等于多少？\n"
            "作答：4\n"
        )
        result = grade_paper(paper, {"1": "7", "2": "5"})
        self.assertEqual(result["items"][0]["status"], "correct")
        self.assertEqual(result["items"][0]["correct_answer"], "7")
        self.assertEqual(result["items"][1]["number"], "2")
        self.assertEqual(result["items"][1]["status"], "incorrect")
        self.assertEqual(result["items"][1]["correct_answer"], "5")
        self.assertEqual(result["graded_count"], 2)
        self.assertEqual(result["ungraded_count"], 0)

    def test_supported_item_without_student_answer_is_ungraded(self):
        from backend.tools.grading import grade_paper

        paper = "1. 3+4等于多少？\n标准答案：7\n"
        result = grade_paper(paper)
        self.assertEqual(result["items"][0]["status"], "ungraded")
        self.assertEqual(result["items"][0]["student_answer"], "")
        self.assertIsNone(result["items"][0]["score"])
        self.assertEqual(result["graded_count"], 0)
        self.assertEqual(result["ungraded_count"], 1)

    def test_unsupported_types_stay_ungraded_even_when_answers_match(self):
        from backend.tools.grading import grade_paper

        paper = (
            "1. 多选题：2 和 4 里哪些是偶数？\n"
            "作答：2\n"
            "标准答案：2\n"
            "\n"
            "2. 小车速度是 3 m/s，行驶多少米？\n"
            "作答：6\n"
            "标准答案：6\n"
            "\n"
            "3. 解答：为什么 2+2=4？\n"
            "作答：因为加法\n"
            "标准答案：因为加法\n"
            "\n"
            "（4）____ 加 ____ 等于 5\n"
            "作答：2\n"
            "标准答案：2\n"
            "\n"
            "第5题 写出圆的面积公式\n"
            "作答：πr^2\n"
            "标准答案：πr^2\n"
        )
        result = grade_paper(paper)
        self.assertEqual(
            [item["status"] for item in result["items"]],
            ["unsupported", "unsupported", "unsupported", "unsupported", "unsupported"],
        )
        self.assertEqual([item["number"] for item in result["items"]], ["1", "2", "3", "4", "5"])
        self.assertTrue(all(item["score"] is None for item in result["items"]))
        self.assertEqual(result["graded_count"], 0)
        self.assertEqual(result["ungraded_count"], 5)

    def test_unsupported_wins_when_answer_is_missing(self):
        from backend.tools.grading import grade_paper

        paper = "1. 简答：说明什么是加法\n标准答案：加法是合并\n"
        result = grade_paper(paper)
        self.assertEqual(result["items"][0]["status"], "unsupported")
        self.assertEqual(result["items"][0]["student_answer"], "")
        self.assertEqual(result["graded_count"], 0)
        self.assertEqual(result["ungraded_count"], 1)

    def test_unit_in_answer_does_not_change_stem_type(self):
        from backend.tools.grading import grade_paper

        paper = "1. 3+4等于多少？\n作答：7kg\n标准答案：7\n"
        result = grade_paper(paper)
        self.assertEqual(result["items"][0]["status"], "incorrect")
        self.assertEqual(result["items"][0]["score"], 0)

    def test_fraction_still_uses_single_item_equivalence(self):
        from backend.tools.grading import grade_paper

        paper = "第1题 求值\n作答：1/2\n标准答案：0.5||2/2\n"
        result = grade_paper(paper)
        self.assertEqual(result["items"][0]["status"], "correct")
        self.assertEqual(result["items"][0]["score"], 1)

    def test_empty_or_unnumbered_paper_is_empty_result(self):
        from backend.tools.grading import grade_paper

        empty = {"items": [], "graded_count": 0, "ungraded_count": 0}
        self.assertEqual(grade_paper(""), empty)
        self.assertEqual(grade_paper("   \n没有题号，只有一段话"), empty)
        self.assertEqual(grade_paper("作答：1\n标准答案：1\n"), empty)
        self.assertEqual(grade_paper("", {"1": "7"}), empty)

    def test_format_paper_lists_items_without_a_total(self):
        from backend.tools.grading import format_paper, grade_paper

        paper = (
            "1. 3+4等于多少？\n"
            "作答：7\n"
            "标准答案：7\n"
            "\n"
            "2. 9-4等于多少？\n"
            "作答：4\n"
            "标准答案：5\n"
        )
        text = format_paper(grade_paper(paper))
        self.assertIn("已判 2", text)
        self.assertIn("未判 0", text)
        self.assertIn("第1题", text)
        self.assertIn("正确", text)
        self.assertIn("第2题", text)
        self.assertIn("不正确", text)
        self.assertNotIn("总分", text)


class TestQuizPaperPage(unittest.TestCase):
    """习题页整卷文本要出现逐题结果。识图用替身，不请求视觉模型。"""

    def _quiz(self):
        from streamlit.testing.v1 import AppTest

        app = str(PROJECT_ROOT / "frontend" / "app.py")
        at = AppTest.from_file(app, default_timeout=120)
        at.session_state["authenticated"] = True
        at.session_state["auth_user"] = "student"
        at.session_state["current_page"] = "quiz"
        at.run()
        return at

    def test_pasted_paper_shows_each_item(self):
        from unittest import mock

        paper = (
            "1. 3+4等于多少？\n"
            "作答：7\n"
            "标准答案：7\n"
            "\n"
            "2. 9-4等于多少？\n"
            "作答：4\n"
            "标准答案：5\n"
        )
        with mock.patch(
            "backend.tools.vision.read_image",
            side_effect=AssertionError("整卷文本判分不应调用识图"),
        ):
            at = self._quiz()
            self.assertEqual([str(item.value) for item in at.exception], [])
            at.text_area(key="grade_paper_text").set_value(paper)
            at.button(key="grade_paper_run").click().run()
        self.assertEqual([str(item.value) for item in at.exception], [])
        shown = "\n".join(item.value for item in list(at.text) + list(at.markdown))
        self.assertIn("第1题", shown)
        self.assertIn("正确", shown)
        self.assertIn("第2题", shown)
        self.assertIn("不正确", shown)
        self.assertNotIn("总分", shown)

    def test_vision_error_string_is_shown_and_page_survives(self):
        from unittest import mock

        def fake_read(image_path, focus="全部"):
            return "未配置 DASHSCOPE_API_KEY，无法识图。请在 .env 中设置通义千问 API Key。"

        with mock.patch("backend.tools.vision.read_image", side_effect=fake_read):
            at = self._quiz()
            at.file_uploader(key="grade_paper_image").set_value(
                ("paper.png", b"\x89PNG\r\n\x1a\n", "image/png")
            )
            at.button(key="grade_paper_run").click().run()
        self.assertEqual([str(item.value) for item in at.exception], [])
        errors = "\n".join(item.value for item in at.error)
        self.assertIn("DASHSCOPE_API_KEY", errors)
        shown = "\n".join(item.value for item in at.text)
        self.assertNotIn("第1题", shown)

    def test_replaced_vision_text_is_graded_offline(self):
        from unittest import mock

        paper = "1. 3+4等于多少？\n作答：7\n标准答案：7\n"

        def fake_read(image_path, focus="全部"):
            return paper

        with mock.patch("backend.tools.vision.read_image", side_effect=fake_read):
            at = self._quiz()
            at.file_uploader(key="grade_paper_image").set_value(
                ("paper.png", b"\x89PNG\r\n\x1a\n", "image/png")
            )
            at.button(key="grade_paper_run").click().run()
        self.assertEqual([str(item.value) for item in at.exception], [])
        shown = "\n".join(item.value for item in list(at.text) + list(at.markdown))
        self.assertIn("第1题", shown)
        self.assertIn("正确", shown)
        self.assertNotIn("总分", shown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
