import unittest

from backend.tools.code_sandbox import (
    format_run_result,
    hint_for_level,
    run_student_code,
)


class TestM3SandboxHardening(unittest.TestCase):
    def test_infinite_loop_timeout_and_process_cleanup(self):
        # A while-loop that does not stop
        code = "while True:\n    pass\n"
        res = run_student_code(code, timeout_s=0.5)
        self.assertEqual(res["status"], "timeout")
        self.assertEqual(res["exception_type"], "TimeoutError")
        self.assertIn("超过", res["exception_message"])

    def test_output_flooding_truncation(self):
        # Flood output with 20000 characters
        code = "print('X' * 20000)\n"
        res = run_student_code(code)
        self.assertEqual(res["status"], "passed")
        self.assertTrue(len(res["stdout"]) <= 4100)
        self.assertTrue(res["truncated"])

    def test_forbidden_operations_rejected(self):
        # Network import
        res_net = run_student_code("import socket\n")
        self.assertEqual(res_net["status"], "rejected")
        self.assertIn("不允许导入 socket", res_net["exception_message"])

        # File write attempt
        res_file = run_student_code("open('test.txt', 'w').write('hi')\n")
        self.assertEqual(res_file["status"], "rejected")
        self.assertIn("不允许调用 open", res_file["exception_message"])

        # System command attempt
        res_sys = run_student_code("import os\n")
        self.assertEqual(res_sys["status"], "rejected")
        self.assertIn("不允许导入 os", res_sys["exception_message"])

    def test_memory_bomb_caught_at_64mb(self):
        # Allocate over 64MB memory
        code = (
            "data = []\n"
            "for _ in range(100):\n"
            "    data.append(bytearray(2 * 1024 * 1024))\n"
        )
        res = run_student_code(code, timeout_s=4)
        self.assertEqual(res["status"], "memory")
        self.assertEqual(res["exception_type"], "MemoryError")
        self.assertIn("内存", res["exception_message"])

    def test_graded_hint_levels(self):
        # Code with ZeroDivisionError
        code = "a = 10\nb = 0\nc = a / b\n"
        res = run_student_code(code)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["exception_type"], "ZeroDivisionError")
        self.assertEqual(res["line"], 3)

        formatted = format_run_result(res)
        self.assertIn("ZeroDivisionError", formatted)

        # Level 1: Category only, no code line leak
        h1 = hint_for_level(1, formatted)
        self.assertIn("除数为 0", h1)
        self.assertNotIn("c = a / b", h1)

        # Level 2: Line number included
        h2 = hint_for_level(2, formatted)
        self.assertIn("3", h2)

        # Level 3: Inspection direction
        h3 = hint_for_level(3, formatted)
        self.assertIn("检查除数", h3)


if __name__ == "__main__":
    unittest.main()
