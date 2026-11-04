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
        self.assertGreaterEqual(len(dataset["samples"]), 56)
        self.assertEqual(dataset.get("version"), "v3")
        self.assertEqual(validate_against_registry(dataset), [])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
