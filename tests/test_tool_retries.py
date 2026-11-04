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
        tools.reset_tool_circuit()
        # 旧用例只断言重试次数。退避落地后把真睡眠换成空等，避免套件卡住。
        self.original_sleep = tools.time.sleep
        tools.time.sleep = lambda _seconds: None

    def tearDown(self):
        self.spec.fn = self.original_fn
        self.spec.retries = self.original_retries
        self.spec.timeout_s = self.original_timeout
        self.tools.time.sleep = self.original_sleep

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


class TestToolBackoff(unittest.TestCase):
    """重试之间等待 min(8, 0.5 * 2^attempt) 秒，再加抖动。attempt 从 0 起。"""

    def setUp(self):
        import backend.agents.react_tools as tools
        from backend.agents.tool_registry import get_tool_spec

        self.tools = tools
        self.spec = get_tool_spec("grade_item")
        self.original_fn = self.spec.fn
        self.original_retries = self.spec.retries
        self.original_timeout = self.spec.timeout_s
        tools.reset_tool_circuit()

    def tearDown(self):
        self.spec.fn = self.original_fn
        self.spec.retries = self.original_retries
        self.spec.timeout_s = self.original_timeout
        self.tools.reset_tool_circuit()

    def test_waits_exponentially_with_jitter_between_retries(self):
        calls = {"n": 0}

        def flaky(agent, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("temporary")
            return "判分完成"

        slept = []

        self.spec.fn = flaky
        self.spec.retries = 2
        result = self.tools.execute_tool(
            _Agent(),
            "grade_item",
            {},
            sleeper=slept.append,
            jitter=lambda: 0.25,
        )
        self.assertEqual(result, "判分完成")
        self.assertEqual(calls["n"], 3)
        # 0.5 * 2^0 + 0.25，然后 0.5 * 2^1 + 0.25。成功后不再等。
        self.assertEqual(slept, [0.75, 1.25])

    def test_backoff_is_capped_then_jitter_is_added(self):
        def always_fail(agent, **kwargs):
            raise RuntimeError("still down")

        slept = []
        self.spec.fn = always_fail
        # 6 次重试 = 7 次调用，中间等 6 次。第 5、6 次等待应停在 8 秒再加抖动。
        self.spec.retries = 6
        result = self.tools.execute_tool(
            _Agent(),
            "grade_item",
            {},
            sleeper=slept.append,
            jitter=lambda: 0.25,
        )
        self.assertIn("still down", result)
        self.assertEqual(slept, [0.75, 1.25, 2.25, 4.25, 8.25, 8.25])

    def test_bad_arguments_do_not_wait(self):
        def bad_args(agent, **kwargs):
            raise TypeError("missing question_text")

        slept = []
        self.spec.fn = bad_args
        self.spec.retries = 5
        result = self.tools.execute_tool(
            _Agent(),
            "grade_item",
            {},
            sleeper=slept.append,
            jitter=lambda: 0.25,
        )
        self.assertIn("工具参数错误", result)
        self.assertEqual(slept, [])

    def test_first_success_does_not_wait(self):
        self.spec.fn = lambda agent, **kwargs: "判分完成"
        self.spec.retries = 3
        slept = []
        result = self.tools.execute_tool(
            _Agent(),
            "grade_item",
            {},
            sleeper=slept.append,
            jitter=lambda: 0.25,
        )
        self.assertEqual(result, "判分完成")
        self.assertEqual(slept, [])

    def test_timeout_also_waits_before_the_next_attempt(self):
        def timed_out(agent, **kwargs):
            raise TimeoutError("slow")

        slept = []
        self.spec.fn = timed_out
        self.spec.retries = 1
        result = self.tools.execute_tool(
            _Agent(),
            "grade_item",
            {},
            sleeper=slept.append,
            jitter=lambda: 0.25,
        )
        self.assertIn("执行超时", result)
        self.assertEqual(slept, [0.75])

    def test_registered_tools_keep_zero_retries(self):
        from backend.agents.tool_registry import get_all_specs

        for spec in get_all_specs():
            self.assertEqual(spec.retries, 0, spec.name)


class TestToolCircuit(unittest.TestCase):
    def setUp(self):
        import backend.agents.react_tools as tools
        from backend.agents.tool_registry import get_tool_spec

        self.tools = tools
        self.spec = get_tool_spec("hint_level")
        self.original_fn = self.spec.fn
        self.original_retries = self.spec.retries
        self.now = 1_000.0
        tools._circuit.clock = lambda: self.now
        tools.reset_tool_circuit()

    def tearDown(self):
        self.spec.fn = self.original_fn
        self.spec.retries = self.original_retries
        self.tools._circuit.clock = __import__("time").monotonic
        self.tools.reset_tool_circuit()

    def test_three_failures_open_the_circuit(self):
        calls = {"n": 0}

        def down(agent, **kwargs):
            calls["n"] += 1
            raise RuntimeError("down")

        self.spec.fn = down
        self.spec.retries = 0
        for _ in range(3):
            result = self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
            self.assertIn("down", result)
        blocked = self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.assertIn("熔断", blocked)
        self.assertEqual(calls["n"], 3)

    def test_cooldown_allows_the_next_call(self):
        calls = {"n": 0}

        def down(agent, **kwargs):
            calls["n"] += 1
            raise RuntimeError("down")

        self.spec.fn = down
        for _ in range(3):
            self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.now += 30
        again = self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.assertIn("down", again)
        self.assertEqual(calls["n"], 4)

    def test_success_clears_the_failure_count(self):
        calls = {"n": 0}

        def fail(agent, **kwargs):
            calls["n"] += 1
            raise RuntimeError("down")

        self.spec.fn = fail
        self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.spec.fn = lambda agent, **kwargs: "ok"
        self.assertEqual(
            self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None),
            "ok",
        )
        self.spec.fn = fail
        calls["n"] = 0
        for _ in range(2):
            self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.assertEqual(calls["n"], 2)
        self.assertIn(
            "down",
            self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None),
        )
        blocked = self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
        self.assertIn("熔断", blocked)
        self.assertEqual(calls["n"], 3)

    def test_parameter_errors_do_not_open_the_circuit(self):
        calls = {"n": 0}

        def bad(agent, **kwargs):
            calls["n"] += 1
            raise TypeError("missing")

        self.spec.fn = bad
        for _ in range(4):
            result = self.tools.execute_tool(_Agent(), "hint_level", {}, sleeper=lambda _s: None)
            self.assertIn("工具参数错误", result)
        self.assertEqual(calls["n"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
