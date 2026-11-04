"""工具执行器按 ToolSpec.retries 重试异常和超时，参数错误不重试。"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class _Agent:
    pass


class TestToolRetries(unittest.TestCase):
    def setUp(self):
        import backend.agents.react_tools as tools
        from backend.agents.tool_registry import get_tool_spec

        self.tools = tools
        self.spec = get_tool_spec("grade_item")
        self.original_fn = self.spec.fn
        self.original_retries = self.spec.retries
        self.original_timeout = self.spec.timeout_s

    def tearDown(self):
        self.spec.fn = self.original_fn
        self.spec.retries = self.original_retries
        self.spec.timeout_s = self.original_timeout

    def test_retries_then_returns_the_later_success(self):
        calls = {"n": 0}

        def flaky(agent, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("temporary")
            return "判分完成"

        self.spec.fn = flaky
        self.spec.retries = 2
        result = self.tools.execute_tool(_Agent(), "grade_item", {})
        self.assertEqual(result, "判分完成")
        self.assertEqual(calls["n"], 3)

    def test_exhausted_retries_return_the_last_failure(self):
        calls = {"n": 0}

        def always_fail(agent, **kwargs):
            calls["n"] += 1
            raise RuntimeError("still down")

        self.spec.fn = always_fail
        self.spec.retries = 1
        result = self.tools.execute_tool(_Agent(), "grade_item", {})
        self.assertIn("still down", result)
        self.assertEqual(calls["n"], 2)

    def test_bad_arguments_are_not_retried(self):
        calls = {"n": 0}

        def bad_args(agent, **kwargs):
            calls["n"] += 1
            raise TypeError("missing question_text")

        self.spec.fn = bad_args
        self.spec.retries = 5
        result = self.tools.execute_tool(_Agent(), "grade_item", {})
        self.assertIn("工具参数错误", result)
        self.assertEqual(calls["n"], 1)

    def test_zero_retries_calls_once(self):
        calls = {"n": 0}

        def once(agent, **kwargs):
            calls["n"] += 1
            raise RuntimeError("once")

        self.spec.fn = once
        self.spec.retries = 0
        self.tools.execute_tool(_Agent(), "grade_item", {})
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
