from datetime import datetime, timezone
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.api.local_client import (
    backup_database_api,
    get_documents_api,
    list_mastery_api,
    restore_database_api,
)
from backend.platform.dataset_catalog import validate_and_clean_dataset
from backend.platform.db_backup import count_database_records
from backend.platform.domain_store import (
    add_document_record,
    init_domain_db,
    list_document_records,
    list_mastery,
    upsert_mastery,
    upsert_user,
)
from backend.platform.eval_runner import live_run
from backend.platform.faithfulness import (
    GOLDEN_CALIBRATION_SAMPLES,
    calibrate_faithfulness_judge,
)
from backend.platform.mistake_store import (
    confirm_mistake,
    create_pending,
    init_mistake_db,
    list_mistakes,
)
from backend.platform.review_planner import run_review_push


class TestM6M1M7Closure(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.tmp.name) / "app.db"
        self.backup_path = Path(self.tmp.name) / "backups" / "app_snapshot.db"
        init_domain_db(self.db_path)
        init_mistake_db(self.db_path)

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    # ==========================================================
    # Subtask 4.1: M6 数据集清洗自检与成本熔断
    # ==========================================================
    def test_m6_dataset_validation_and_sanitization(self):
        dirty_dataset = {
            "name": "dirty_bench",
            "version": "v1.0",
            "samples": [
                {"id": "s1", "input": "什么是牛顿第一定律？", "expected_tools": ["rag_search"]},
                {"id": "s2", "input": "", "expected_tools": []},  # Empty question, must be stripped
                {"id": "s1", "input": "重复ID的样本", "expected_tools": []},  # Duplicate ID
                {"id": "s3", "input": "解释动能定理", "expected_tools": ["explain_concept"]},
            ],
        }
        cleaned, issues = validate_and_clean_dataset(dirty_dataset)
        self.assertEqual(len(cleaned["samples"]), 2)
        self.assertEqual([s["id"] for s in cleaned["samples"]], ["s1", "s3"])
        self.assertTrue(len(issues) >= 2)
        self.assertTrue(any("缺少问题内容" in iss for iss in issues))
        self.assertTrue(any("重复样本" in iss for iss in issues))

    def test_m6_budget_circuit_breaker(self):
        dataset = {
            "name": "mock_cost_dataset",
            "version": "v1.0",
            "samples": [
                {"id": f"c_{i}", "input": f"问题 {i}", "expected_tools": []}
                for i in range(5)
            ],
        }
        # Run live_run with max_cost_yuan = -1 or very low threshold (simulate 0 budget)
        results = live_run(dataset, limit=5, max_cost_yuan=0.000001)
        # First sample runs, exceeds cost, remaining samples are tripped by circuit breaker
        self.assertEqual(len(results), 5)
        tripped = [r for r in results if "评测预算已耗尽" in str(r.get("output"))]
        self.assertTrue(len(tripped) >= 3)
        self.assertFalse(tripped[0]["passed"])

    # ==========================================================
    # Subtask 4.2: M1 忠实度裁判黄金校准 (Judge Calibration)
    # ==========================================================
    def test_m1_faithfulness_judge_golden_calibration(self):
        report = calibrate_faithfulness_judge()
        self.assertEqual(report["total"], len(GOLDEN_CALIBRATION_SAMPLES))
        # Golden standard: rule-based faithfulness judge achieves 100% calibration on golden benchmark
        self.assertEqual(report["accuracy"], 1.0)
        self.assertTrue(report["passed"])
        self.assertEqual(report["confusion"]["fp"], 0)
        self.assertEqual(report["confusion"]["fn"], 0)
        self.assertTrue(report["confusion"]["tp"] >= 2)
        self.assertTrue(report["confusion"]["tn"] >= 3)

        # Plug in custom LLM mock judge to verify judge extensibility
        def mock_llm_judge(ans, ctx):
            return "牛顿" in ans or "光年" in ans

        custom_report = calibrate_faithfulness_judge(judge_fn=mock_llm_judge)
        self.assertEqual(custom_report["accuracy"], 1.0)
        self.assertTrue(custom_report["passed"])

    # ==========================================================
    # Subtask 4.3: M7 生产级灾难破坏与全状态一键恢复演练
    # ==========================================================
    def test_m7_full_system_disaster_recovery_drill(self):
        # 1. Populate comprehensive golden state across domain tables
        upsert_user("student", "张三", db_path=self.db_path)
        add_document_record("doc_math", "高中数学核心概念.pdf", chunks=12, user_id="student", db_path=self.db_path)
        add_document_record("doc_phys", "大学物理电磁学.pdf", chunks=8, user_id="student", db_path=self.db_path)

        upsert_mastery("导数概念", is_correct=True, user_id="student", db_path=self.db_path)
        upsert_mastery("洛必达法则", is_correct=False, user_id="student", db_path=self.db_path)

        m1 = create_pending(
            "student",
            subject="数学",
            concept="洛必达法则",
            error_type="概念错误",
            question_text="求 0/0 极限",
            student_answer="直接代入",
            correct_answer="求导后再代入",
            db_path=self.db_path,
        )
        confirm_mistake(m1, db_path=self.db_path)

        # Seed review push outbox
        run_review_push(
            "student",
            now=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc),
            db_path=self.db_path,
        )

        initial_counts = count_database_records(self.db_path)
        self.assertTrue(initial_counts.get("users", 0) >= 1)
        self.assertEqual(initial_counts.get("documents", 0), 2)
        self.assertEqual(initial_counts.get("mastery", 0), 2)
        self.assertEqual(initial_counts.get("mistakes", 0), 1)

        # 2. Hot atomic backup via API
        backup_res = backup_database_api(dest=str(self.backup_path), db_path=self.db_path)
        self.assertTrue(os.path.isfile(backup_res["backup_path"]))
        backup_counts = count_database_records(Path(backup_res["backup_path"]))
        self.assertEqual(backup_counts, initial_counts)

        # 3. Simulate disaster: Destructive corruption!
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM documents")
            conn.execute("DELETE FROM mistakes")
            conn.execute("UPDATE mastery SET score = 0.0, attempts = 999")
            conn.commit()

        # Verify corruption
        ruined_docs = list_document_records(db_path=self.db_path)
        ruined_mistakes = list_mistakes("student", db_path=self.db_path)
        self.assertEqual(len(ruined_docs), 0)
        self.assertEqual(len(ruined_mistakes), 0)

        # 4. Trigger one-click disaster recovery via API
        restore_res = restore_database_api(str(self.backup_path), db_path=self.db_path)
        self.assertTrue(restore_res["restored"])

        # 5. Verify 100% full recovery!
        restored_counts = count_database_records(self.db_path)
        self.assertEqual(restored_counts, initial_counts)

        # Verify business data and API responses
        docs_api_res = get_documents_api(db_path=self.db_path)
        self.assertEqual(docs_api_res["total_documents"], 2)
        self.assertEqual(len(docs_api_res["documents"]), 2)

        mastery_api_res = list_mastery_api("student", db_path=self.db_path)
        self.assertEqual(len(mastery_api_res), 2)

        recovered_mistakes = list_mistakes("student", db_path=self.db_path)
        self.assertEqual(len(recovered_mistakes), 1)
        self.assertEqual(recovered_mistakes[0]["id"], m1)
        self.assertEqual(recovered_mistakes[0]["concept"], "洛必达法则")


if __name__ == "__main__":
    unittest.main()
