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

    def test_arithmetic_variant_keeps_hidden_answer(self):
        from backend.tools.grading import format_variants, make_variants

        result = make_variants("计算 8/2", count=1)
        self.assertEqual(result["status"], "ready")
        self.assertIsNotNone(result["items"][0]["answer"])
        self.assertNotIn("答案:", format_variants(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
