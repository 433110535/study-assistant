"""数据集版本一旦登记就冻结，内容变了不能沿用同一个版本号。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDatasetCatalog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "app.db"
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, version: str, sample_id: str) -> Path:
        path = self.dir / f"{name}_{version}.json"
        path.write_text(
            json.dumps(
                {
                    "name": name,
                    "version": version,
                    "changelog": "测试快照",
                    "samples": [{"id": sample_id, "input": "你好", "expected_tools": []}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_same_file_registers_once(self):
        from backend.platform.dataset_catalog import list_versions, register_file

        path = self._write("qa_baseline", "v9", "q001")
        first = register_file(path, db_path=self.db)
        second = register_file(path, db_path=self.db)
        rows = list_versions(db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(len(first["content_hash"]), 64)
        self.assertEqual(rows[0]["sample_count"], 1)
        self.assertEqual(rows[0]["version"], "v9")
        self.assertEqual(rows[0]["changelog"], "测试快照")

    def test_changed_bytes_cannot_reuse_a_version(self):
        from backend.platform.dataset_catalog import register_file

        path = self._write("qa_baseline", "v9", "q001")
        register_file(path, db_path=self.db)
        path.write_text(
            json.dumps(
                {
                    "name": "qa_baseline",
                    "version": "v9",
                    "samples": [{"id": "q002", "input": "改过", "expected_tools": []}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as caught:
            register_file(path, db_path=self.db)
        self.assertIn("已冻结", str(caught.exception))

    def test_eval_run_records_the_file_hash(self):
        from backend.platform.dataset_catalog import list_versions
        from backend.platform.eval_runner import dry_run, load_dataset, save_eval_run

        dataset = load_dataset()
        results = dry_run(dataset)
        save_eval_run(dataset, "dry-run", results, db_path=self.db)
        rows = list_versions("qa_baseline", db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["version"], "v5")
        self.assertEqual(rows[0]["sample_count"], 100)
        self.assertEqual(rows[0]["content_hash"], dataset["_content_hash"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
