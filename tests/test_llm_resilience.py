"""模型调用的退避和熔断。不访问网络。"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestModelResilience(unittest.TestCase):
    def setUp(self):
        from backend.llm_helper import reset_model_circuit
        import backend.llm_helper as helper

        self.helper = helper
        self.now = 1_000.0
        helper._circuit.clock = lambda: self.now
        reset_model_circuit()

    def tearDown(self):
        import time

        self.helper._circuit.clock = time.monotonic
        self.helper.reset_model_circuit()

    def test_retries_with_the_same_backoff_as_tools(self):
        calls = {"n": 0}

        def call():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("temporary")
            return "ok"

        slept = []
        result = self.helper.invoke_model(
            call,
            sleeper=slept.append,
            jitter=lambda: 0.25,
        )
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(slept, [0.75, 1.25])

    def test_three_exhausted_calls_open_the_circuit(self):
        calls = {"n": 0}

        def call():
            calls["n"] += 1
            raise RuntimeError("down")

        for _ in range(3):
            with self.assertRaises(RuntimeError):
                self.helper.invoke_model(call, sleeper=lambda _s: None, jitter=lambda: 0)
        with self.assertRaises(self.helper.LLMUnavailable):
            self.helper.invoke_model(call, sleeper=lambda _s: None, jitter=lambda: 0)
        self.assertEqual(calls["n"], 9)

    def test_cooldown_allows_another_attempt(self):
        calls = {"n": 0}

        def call():
            calls["n"] += 1
            raise RuntimeError("down")

        for _ in range(3):
            with self.assertRaises(RuntimeError):
                self.helper.invoke_model(call, sleeper=lambda _s: None, jitter=lambda: 0)
        self.now += 30
        with self.assertRaises(RuntimeError):
            self.helper.invoke_model(call, sleeper=lambda _s: None, jitter=lambda: 0)
        self.assertEqual(calls["n"], 12)

    def test_success_clears_the_failure_count(self):
        calls = {"n": 0}

        def fail():
            calls["n"] += 1
            raise RuntimeError("down")

        for _ in range(2):
            with self.assertRaises(RuntimeError):
                self.helper.invoke_model(fail, sleeper=lambda _s: None, jitter=lambda: 0)
        self.assertEqual(self.helper.invoke_model(lambda: "ok", sleeper=lambda _s: None), "ok")
        calls["n"] = 0
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                self.helper.invoke_model(fail, sleeper=lambda _s: None, jitter=lambda: 0)
        self.assertEqual(calls["n"], 6)
        with self.assertRaises(RuntimeError):
            self.helper.invoke_model(fail, sleeper=lambda _s: None, jitter=lambda: 0)

    def test_type_error_is_not_retried_or_counted(self):
        calls = {"n": 0}

        def bad():
            calls["n"] += 1
            raise TypeError("bad messages")

        for _ in range(4):
            with self.assertRaises(TypeError):
                self.helper.invoke_model(bad, sleeper=lambda _s: None, jitter=lambda: 0)
        self.assertEqual(calls["n"], 4)

    def test_stream_retries_only_before_the_first_chunk(self):
        opens = {"n": 0}

        def open_stream():
            opens["n"] += 1
            if opens["n"] < 3:
                raise RuntimeError("down")
            return iter(["ok"])

        slept = []
        chunks = list(
            self.helper.stream_model(
                open_stream,
                sleeper=slept.append,
                jitter=lambda: 0.25,
            )
        )
        self.assertEqual(chunks, ["ok"])
        self.assertEqual(opens["n"], 3)
        self.assertEqual(slept, [0.75, 1.25])

        def cut():
            yield "已发出"
            raise RuntimeError("cut")

        with self.assertRaises(RuntimeError):
            list(self.helper.stream_model(cut, sleeper=slept.append, jitter=lambda: 0))
        self.assertEqual(slept, [0.75, 1.25])

    def test_client_retries_stay_off(self):
        with mock.patch("backend.llm_helper.ChatOpenAI") as client:
            client.return_value.bind_tools.return_value.invoke.return_value = "bound"
            llm = self.helper.get_llm()
        self.assertEqual(client.call_args.kwargs["max_retries"], 0)
        self.assertEqual(client.call_args.kwargs["request_timeout"], 60)
        self.assertIsInstance(llm, self.helper.ResilientLLM)
        bound = llm.bind_tools([])
        self.assertIsInstance(bound, self.helper.ResilientLLM)

    def test_named_circuit_does_not_trip_the_model(self):
        def down():
            raise RuntimeError("down")

        for _ in range(3):
            with self.assertRaises(RuntimeError):
                self.helper.invoke_named(
                    "vision",
                    down,
                    label="识图",
                    sleeper=lambda _s: None,
                    jitter=lambda: 0,
                )
        with self.assertRaises(self.helper.LLMUnavailable) as caught:
            self.helper.invoke_named("vision", down, label="识图", sleeper=lambda _s: None)
        self.assertIn("识图", str(caught.exception))
        self.assertEqual(self.helper.invoke_model(lambda: "ok", sleeper=lambda _s: None), "ok")

    def test_async_invoke_uses_the_same_circuit(self):
        calls = {"n": 0}

        async def call():
            calls["n"] += 1
            raise RuntimeError("down")

        async def scenario():
            for _ in range(3):
                with self.assertRaises(RuntimeError):
                    await self.helper.ainvoke_model(
                        call,
                        sleeper=lambda _s: None,
                        jitter=lambda: 0,
                    )
            with self.assertRaises(self.helper.LLMUnavailable):
                await self.helper.ainvoke_model(call, sleeper=lambda _s: None, jitter=lambda: 0)

        asyncio.run(scenario())
        self.assertEqual(calls["n"], 9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
