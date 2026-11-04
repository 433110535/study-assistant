"""评测集校验与工具选择打分（不调用大模型）"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestEvalRunner(unittest.TestCase):
    def test_dataset_covers_registered_tools(self):
        from backend.platform.eval_runner import load_dataset, validate_against_registry

        dataset = load_dataset()
        self.assertEqual(len(dataset["samples"]), 100)
        self.assertEqual(dataset.get("version"), "v5")
        self.assertEqual(validate_against_registry(dataset), [])

    def test_v3_snapshot_stays_free_of_passages(self):
        from backend.platform.eval_runner import load_dataset

        v3 = load_dataset(PROJECT_ROOT / "eval" / "datasets" / "qa_baseline_v3.json")
        v4 = load_dataset(PROJECT_ROOT / "eval" / "datasets" / "qa_baseline_v4.json")
        self.assertEqual(v3.get("version"), "v3")
        self.assertEqual(len(v4["samples"]), 56)
        self.assertTrue(all("contexts" not in sample for sample in v3["samples"]))
        self.assertEqual(
            [(sample["id"], sample["expected_tools"]) for sample in v3["samples"]],
            [(sample["id"], sample["expected_tools"]) for sample in v4["samples"]],
        )

    def test_dry_run_scores_faithfulness_only_for_retrieval_items(self):
        from backend.platform.eval_runner import (
            check_release_gate,
            dry_run,
            load_dataset,
            mean_faithfulness,
        )

        dataset = load_dataset()
        results = dry_run(dataset)
        applicable = [item for item in results if item["faithfulness_applicable"]]
        retrieval_ids = {
            sample["id"]
            for sample in dataset["samples"]
            if "rag_search" in sample["expected_tools"]
        }
        self.assertEqual(retrieval_ids, {item["sample_id"] for item in applicable})
        self.assertEqual(len(applicable), 16)
        self.assertEqual(mean_faithfulness(results), 1.0)
        self.assertTrue(all(item["passed"] for item in results))
        gate = check_release_gate(1.0, faithfulness=mean_faithfulness(results))
        self.assertTrue(gate["passed"])
        self.assertIn("faithfulness", gate["checked"])

    def test_failure_attribution_counts_missing_tools(self):
        import json

        from backend.platform.eval_runner import attribute_failures

        rows = attribute_failures(
            [
                {
                    "passed": False,
                    "detail": json.dumps({"missing": ["rag_search"], "passed": False}),
                },
                {
                    "passed": False,
                    "detail": {"missing": ["rag_search", "read_image"]},
                },
                {"passed": True, "detail": {"missing": ["grade_item"]}},
                {"passed": False, "detail": "schema_ok"},
            ]
        )
        self.assertEqual(
            rows,
            [
                {"tool": "rag_search", "count": 2},
                {"tool": "other", "count": 1},
                {"tool": "read_image", "count": 1},
            ],
        )

    def test_failure_board_reads_latest_run(self):
        import json

        from backend.platform.eval_runner import load_failure_board, save_eval_run

        db = Path(tempfile.mkdtemp()) / "app.db"
        dataset = {"name": "tiny", "version": "v0", "samples": [{"id": "a"}]}
        save_eval_run(
            dataset,
            "dry-run",
            [
                {
                    "sample_id": "a",
                    "passed": False,
                    "tools_used": [],
                    "detail": json.dumps({"missing": ["rag_search"]}),
                    "output": "",
                },
                {
                    "sample_id": "b",
                    "passed": True,
                    "tools_used": ["explain_concept"],
                    "detail": "ok",
                    "output": "",
                },
                {
                    "sample_id": "c",
                    "passed": False,
                    "tools_used": [],
                    "detail": "timeout",
                    "output": "",
                },
            ],
            db_path=db,
        )
        board = load_failure_board(db)
        latest = board["latest"]
        self.assertEqual(
            latest["failure_attribution"],
            [
                {"tool": "other", "count": 1},
                {"tool": "rag_search", "count": 1},
            ],
        )
        self.assertEqual(
            [(item["sample_id"], item["missing"]) for item in latest["failed_samples"]],
            [("a", ["rag_search"]), ("c", [])],
        )
        self.assertFalse(latest["gate"]["passed"])
        self.assertIsNone(latest["faithfulness"])
        self.assertEqual(board["earlier"], [])

    def test_failure_board_recomputes_old_summary(self):
        import json
        import sqlite3

        from backend.platform.eval_runner import load_failure_board, save_eval_run

        db = Path(tempfile.mkdtemp()) / "app.db"
        dataset = {"name": "tiny", "version": "v0", "samples": [{"id": "a"}]}
        save_eval_run(
            dataset,
            "live",
            [
                {
                    "sample_id": "a",
                    "passed": False,
                    "tools_used": [],
                    "detail": json.dumps({"missing": ["read_image"]}),
                    "output": "",
                }
            ],
            db_path=db,
        )
        with sqlite3.connect(db) as conn:
            conn.execute(
                "UPDATE eval_runs SET summary_json = ?",
                (json.dumps({"passed": 0, "total": 1, "accuracy": 0}),),
            )
        board = load_failure_board(db)
        self.assertEqual(
            board["latest"]["failure_attribution"],
            [{"tool": "read_image", "count": 1}],
        )

    def test_live_faithfulness_uses_retrieved_passages_only(self):
        from backend.platform.eval_runner import passages_from_rag_result, score_live_answer

        raw = (
            "【资料1】来源: 教材, 相似度: 80.0%\n"
            "链式法则：先对最外层函数求导，再乘以内层函数的导数。\n\n"
            "【资料2】来源: 笔记, 相似度: 60.0%\n"
            "这条不会被引用。"
        )
        self.assertEqual(
            passages_from_rag_result(raw),
            [
                "链式法则：先对最外层函数求导，再乘以内层函数的导数。",
                "这条不会被引用。",
            ],
        )
        self.assertEqual(passages_from_rag_result("未在知识库中找到相关内容。"), [])
        grounded = score_live_answer(
            "先对最外层函数求导，再乘以内层函数的导数。",
            [raw],
        )
        self.assertTrue(grounded["applicable"])
        self.assertEqual(grounded["score"], 1.0)
        missed = score_live_answer("苹果是红色的水果。", ["未在知识库中找到相关内容。"])
        self.assertTrue(missed["applicable"])
        self.assertEqual(missed["score"], 0.0)
        skipped = score_live_answer("直接回答，没有检索。", [])
        self.assertFalse(skipped["applicable"])
        self.assertIsNone(skipped["score"])
        self.assertTrue(missed["empty_context"])
        self.assertFalse(skipped["empty_context"])

    def test_attribution_counts_empty_retrieval_and_unfaithful_answers(self):
        from backend.platform.eval_runner import attribute_failures

        rows = attribute_failures(
            [
                {
                    "passed": True,
                    "faithfulness_applicable": True,
                    "faithfulness": 0.5,
                    "detail": {"missing": []},
                },
                {
                    "passed": True,
                    "empty_context": True,
                    "faithfulness_applicable": True,
                    "faithfulness": 0.0,
                    "detail": "ok",
                },
                {
                    "passed": True,
                    "faithfulness_applicable": True,
                    "faithfulness": 1.0,
                    "detail": "ok",
                },
            ]
        )
        self.assertEqual(
            rows,
            [
                {"tool": "empty_retrieval", "count": 1},
                {"tool": "unfaithful", "count": 1},
            ],
        )

    def test_timeout_and_cost_are_counted_separately_from_the_answer_text(self):
        from backend.platform.eval_runner import attribute_failures, cost_limit_from_env

        rows = attribute_failures(
            [
                {
                    "passed": True,
                    "tool_results": ["工具 run_code 执行超时（>5s），请稍后重试。"],
                    "output": "这次没有超时。",
                },
                {
                    "passed": True,
                    "output": "执行超时只是回答里的词。",
                    "tool_results": ["正常返回"],
                    "cost_yuan": 1.2,
                    "cost_limit_yuan": 0.5,
                },
                {
                    "passed": True,
                    "cost_yuan": 0.1,
                    "cost_limit_yuan": 0.5,
                },
            ]
        )
        self.assertEqual(
            rows,
            [
                {"tool": "over_cost", "count": 1},
                {"tool": "timeout", "count": 1},
            ],
        )
        self.assertIsNone(cost_limit_from_env({}))
        self.assertIsNone(cost_limit_from_env({"EVAL_MAX_COST_YUAN": "abc"}))
        self.assertEqual(cost_limit_from_env({"EVAL_MAX_COST_YUAN": "0.5"}), 0.5)

    def test_failure_board_is_empty_without_runs(self):
        from backend.platform.eval_runner import load_failure_board

        board = load_failure_board(Path(tempfile.mkdtemp()) / "missing.db")
        self.assertIsNone(board["latest"])
        self.assertEqual(board["earlier"], [])

    def test_ungrounded_sentence_fails_the_faithfulness_gate(self):
        from backend.platform.eval_runner import check_release_gate, dry_run, mean_faithfulness

        dataset = {
            "name": "tiny",
            "version": "v0",
            "samples": [
                {
                    "id": "grounded",
                    "input": "检索贝叶斯定理",
                    "expected_tools": ["rag_search"],
                    "contexts": ["贝叶斯定理把后验概率写成先验概率与似然的乘积，再除以证据。"],
                    "answer": "贝叶斯定理把后验概率写成先验概率与似然的乘积，再除以证据。苹果是红色的水果。",
                },
                {
                    "id": "direct",
                    "input": "你好",
                    "expected_tools": [],
                },
            ],
        }
        results = dry_run(dataset)
        self.assertEqual(
            [item["faithfulness_applicable"] for item in results],
            [True, False],
        )
        self.assertEqual(mean_faithfulness(results), 0.5)
        gate = check_release_gate(1.0, faithfulness=0.5)
        self.assertFalse(gate["passed"])

    def test_v5_adds_forty_four_items_in_the_agreed_mix(self):
        from collections import Counter

        import backend.agents.react_tools  # noqa: F401  注册全部工具
        from backend.agents.tool_registry import get_all_specs
        from backend.platform.eval_runner import load_dataset

        v4 = load_dataset(PROJECT_ROOT / "eval" / "datasets" / "qa_baseline_v4.json")
        v5 = load_dataset()
        self.assertEqual(
            [(sample["id"], sample["expected_tools"]) for sample in v4["samples"]],
            [(sample["id"], sample["expected_tools"]) for sample in v5["samples"][:56]],
        )
        added = v5["samples"][56:]
        counts = Counter(tuple(sample["expected_tools"]) for sample in added)
        self.assertEqual(
            dict(counts),
            {
                ("get_learning_state",): 3,
                ("plan_review",): 3,
                ("send_message",): 2,
                ("reschedule",): 3,
                ("save_mistake",): 2,
                ("make_variants",): 2,
                ("diagnose_error",): 2,
                ("explain_traceback",): 2,
                ("hint_level",): 2,
                ("grade_item",): 2,
                ("run_code",): 2,
                ("run_tests",): 2,
                ("rag_search",): 6,
                ("explain_concept",): 3,
                ("generate_questions",): 3,
                ("generate_study_plan",): 2,
                ("read_image",): 2,
                (): 1,
            },
        )
        covered = {name for sample in v5["samples"] for name in sample["expected_tools"]}
        registered = {spec.name for spec in get_all_specs()}
        self.assertEqual(registered - covered, set())
        for sample in added:
            if sample["expected_tools"] == ["rag_search"]:
                self.assertEqual(sample["answer"], sample["contexts"][0])
            else:
                self.assertNotIn("contexts", sample)

    def test_score_requires_expected_tools(self):
        from backend.platform.eval_runner import score_tool_selection

        hit = score_tool_selection(["rag_search", "explain_concept"], ["explain_concept", "rag_search"])
        self.assertTrue(hit["passed"])
        miss = score_tool_selection(["read_image"], [])
        self.assertFalse(miss["passed"])
        direct = score_tool_selection([], [])
        self.assertTrue(direct["passed"])
        extra = score_tool_selection([], ["rag_search"])
        self.assertFalse(extra["passed"])

    def test_dry_run_persists(self):
        from backend.platform.eval_runner import dry_run, load_dataset, save_eval_run

        dataset = load_dataset()
        db = Path(tempfile.mkdtemp()) / "app.db"
        results = dry_run(dataset)
        run_id = save_eval_run(dataset, "dry-run", results, db_path=db)
        self.assertTrue(run_id)
        self.assertEqual(sum(1 for item in results if item["passed"]), len(results))

    def test_gate_blocks_degraded_accuracy(self):
        from backend.platform.eval_runner import check_release_gate

        below = check_release_gate(0.85)
        self.assertFalse(below["passed"])
        self.assertTrue(below["reasons"])

        dropped = check_release_gate(0.96, baseline_accuracy=1.0)
        self.assertFalse(dropped["passed"])

        held = check_release_gate(0.98, baseline_accuracy=1.0)
        self.assertTrue(held["passed"])
        self.assertIn("faithfulness", held["not_checked"])

    def test_gate_blocks_low_or_dropped_faithfulness(self):
        from backend.platform.eval_runner import check_release_gate

        low = check_release_gate(0.95, faithfulness=0.80)
        self.assertFalse(low["passed"])
        self.assertTrue(any("忠实度" in reason for reason in low["reasons"]))
        self.assertIn("faithfulness", low["checked"])
        self.assertNotIn("faithfulness", low["not_checked"])

        dropped = check_release_gate(
            0.95,
            faithfulness=0.86,
            baseline_faithfulness=0.90,
        )
        self.assertFalse(dropped["passed"])

        held = check_release_gate(
            0.95,
            faithfulness=0.85,
            baseline_faithfulness=0.88,
        )
        self.assertTrue(held["passed"])
        self.assertEqual(held["faithfulness"], 0.85)


class TestFaithfulness(unittest.TestCase):
    def test_quote_from_context_scores_one(self):
        from backend.platform.faithfulness import score_faithfulness

        scored = score_faithfulness(
            "先对最外层函数求导，再乘以内层函数的导数。",
            ["链式法则：对复合函数求导，先对最外层函数求导，再乘以内层函数的导数。"],
        )
        self.assertTrue(scored["applicable"])
        self.assertEqual(scored["score"], 1.0)
        self.assertEqual(scored["grounded"], 1)
        self.assertEqual(scored["claims"], 1)

    def test_mixed_answer_scores_half(self):
        from backend.platform.faithfulness import score_faithfulness

        scored = score_faithfulness(
            "先对最外层函数求导，再乘以内层函数的导数。苹果是红色的水果。",
            ["链式法则：对复合函数求导，先对最外层函数求导，再乘以内层函数的导数。"],
        )
        self.assertEqual(scored["score"], 0.5)
        self.assertEqual(scored["grounded"], 1)
        self.assertEqual(scored["claims"], 2)

    def test_answer_without_context_scores_zero(self):
        from backend.platform.faithfulness import score_faithfulness

        scored = score_faithfulness("苹果是红色的水果。", [])
        self.assertTrue(scored["applicable"])
        self.assertEqual(scored["score"], 0.0)

    def test_short_reply_is_not_scored(self):
        from backend.platform.faithfulness import score_faithfulness

        scored = score_faithfulness("好", ["好的，我们继续。"])
        self.assertFalse(scored["applicable"])
        self.assertIsNone(scored["score"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
