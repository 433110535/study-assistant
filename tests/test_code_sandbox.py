"""代码沙箱：通过、失败、拒绝、超时与分级提示。不调用大模型。"""
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCodeSandbox(unittest.TestCase):
    def test_print_and_math(self):
        from backend.tools.code_sandbox import run_student_code

        result = run_student_code("import math\nprint(math.sqrt(4))")
        self.assertEqual(result["status"], "passed", result)
        self.assertIn("2.0", result["stdout"])

    def test_tests_pass_with_class(self):
        from backend.tools.code_sandbox import run_student_code

        code = (
            "class Box:\n"
            "    def __init__(self, n):\n"
            "        self.n = n\n"
            "    def inc(self):\n"
            "        self.n += 1\n"
        )
        tests = "box = Box(1)\nbox.inc()\nassert box.n == 2\n"
        result = run_student_code(code, tests=tests)
        self.assertEqual(result["status"], "passed", result)

    def test_assertion_failure_keeps_stdout(self):
        from backend.tools.code_sandbox import run_student_code

        result = run_student_code(
            "def add(a, b):\n    print('before')\n    return a - b\n",
            tests="assert add(1, 2) == 3\n",
        )
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["exception_type"], "AssertionError")
        self.assertIn("before", result["stdout"])

    def test_zero_division_reports_line(self):
        from backend.tools.code_sandbox import format_run_result, run_student_code

        result = run_student_code("print('hi')\nx = 1 / 0\n")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exception_type"], "ZeroDivisionError")
        self.assertEqual(result["line"], 2)
        text = format_run_result(result)
        self.assertNotIn("1 / 0", text)

    def test_rejects_import_open_and_dunder(self):
        from backend.tools.code_sandbox import run_student_code

        imported = run_student_code("import os\nos.listdir('.')\n")
        self.assertEqual(imported["status"], "rejected", imported)
        opened = run_student_code("open('secret.txt', 'w')\n")
        self.assertEqual(opened["status"], "rejected", opened)
        escaped = run_student_code("print(().__class__)\n")
        self.assertEqual(escaped["status"], "rejected", escaped)

    def test_timeout(self):
        from backend.tools.code_sandbox import run_student_code

        result = run_student_code("while True:\n    pass\n", timeout_s=1)
        self.assertEqual(result["status"], "timeout", result)
        self.assertEqual(result["exception_type"], "TimeoutError")

    def test_child_env_drops_secrets(self):
        from backend.tools.code_sandbox import _child_env

        previous = os.environ.get("DASHSCOPE_API_KEY")
        os.environ["DASHSCOPE_API_KEY"] = "sk-test-secret"
        try:
            env = _child_env()
        finally:
            if previous is None:
                os.environ.pop("DASHSCOPE_API_KEY", None)
            else:
                os.environ["DASHSCOPE_API_KEY"] = previous
        self.assertNotIn("DASHSCOPE_API_KEY", env)
        self.assertNotIn("PYTHONPATH", env)

    def test_hints_stay_graded(self):
        from backend.tools.code_sandbox import format_run_result, hint_for_level, run_student_code

        result = run_student_code("x = 1 / 0\n")
        observation = format_run_result(result)
        level1 = hint_for_level(1, observation)
        level2 = hint_for_level(2, observation)
        self.assertIn("除数为 0", level1)
        self.assertNotIn("行号：", level1)
        self.assertNotIn("def ", level1)
        self.assertIn("行号：1", level2)
        self.assertIn("不要输出修改后的完整代码", level2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
