from datetime import datetime, timedelta, timezone
import os
import tempfile
import unittest
from pathlib import Path

from backend.api.local_client import grade_paper_text
from backend.platform.domain_store import init_domain_db, list_mastery
from backend.platform.mistake_store import confirm_mistake, list_mistakes
from backend.platform.review_planner import get_learning_state
from backend.tools.grading import grade_paper


class TestM4PaperEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        init_domain_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            try:
                os.unlink(self.tmp.name)
            except OSError:
                pass

    def test_grade_paper_enhanced_unit_and_multichoice(self):
        paper = (
            "1. 多选题：下列哪些是偶数？\n"
            "作答：2, 4\n"
            "标准答案：2, 4\n\n"
            "2. 铁丝长 1.5m，等于多少 cm？\n"
            "作答：150cm\n"
            "标准答案：1.5m\n\n"
            "3. 椭圆 a = 5, b = 3，求 c 和离心率 e 分别是？（双空）____ 和 ____\n"
            "作答：4; 0.8\n"
            "标准答案：4; 0.8\n"
        )
        # Without enhanced: legacy returns unsupported for multi-choice, unit, multi-blank
        legacy = grade_paper(paper, enhanced=False)
        self.assertEqual(legacy["items"][0]["status"], "unsupported")
        self.assertEqual(legacy["items"][1]["status"], "unsupported")
        self.assertEqual(legacy["items"][2]["status"], "unsupported")

        # With enhanced: grades accurately
        res = grade_paper(paper, enhanced=True)
        items = res["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["status"], "correct")
        self.assertEqual(items[1]["status"], "correct")
        self.assertEqual(items[2]["status"], "correct")

    def test_paper_grade_full_loop_collects_mistakes_and_updates_mastery(self):
        math_paper = (
            "1. 单选题：函数 y = 2x + 1 的斜率是？\n"
            "作答：2\n"
            "标准答案：2\n\n"
            "2. 多选题：下列哪些是偶数？\n"
            "作答：2, 4, 6\n"
            "标准答案：2, 4, 6\n\n"
            "3. 汽车速度是 72 km/h，折合多少 m/s？\n"
            "作答：50m/s\n"
            "标准答案：20 m/s\n\n"
            "4. 方程两根分别是？（双空）____ 和 ____\n"
            "作答：2; 4\n"
            "标准答案：2; 3\n\n"
            "5. 计算 12 * 8 = ?\n"
            "作答：96\n"
            "标准答案：96\n"
        )

        res = grade_paper_text(
            math_paper,
            enhanced=True,
            auto_collect_mistakes=True,
            user_id="math_student",
            subject="高中数学",
            db_path=self.db_path,
        )

        self.assertIn("items", res)
        items = res["items"]
        self.assertEqual(len(items), 5)

        self.assertEqual(items[0]["status"], "correct")
        self.assertEqual(items[1]["status"], "correct")
        self.assertEqual(items[2]["status"], "incorrect")
        self.assertIn(items[3]["status"], ("partial", "incorrect"))
        self.assertEqual(items[4]["status"], "correct")

        # Auto-collected mistakes
        self.assertEqual(res["collected_count"], 2)
        collected_ids = res["collected_mistake_ids"]
        self.assertEqual(len(collected_ids), 2)

        # Verify pending mistakes in SQLite
        pending_list = list_mistakes("math_student", status="pending", db_path=self.db_path)
        self.assertEqual(len(pending_list), 2)

        # Verify mastery updated in domain_store
        mastery_list = list_mastery("math_student", db_path=self.db_path)
        self.assertTrue(len(mastery_list) > 0)

        # Confirm a mistake and verify review schedule
        m_id = collected_ids[0]
        confirmed = confirm_mistake(m_id, db_path=self.db_path)
        self.assertTrue(confirmed)

        remaining_pending = list_mistakes("math_student", status="pending", db_path=self.db_path)
        self.assertEqual(len(remaining_pending), 1)

        confirmed_list = list_mistakes("math_student", status="confirmed", db_path=self.db_path)
        self.assertEqual(len(confirmed_list), 1)
        self.assertEqual(confirmed_list[0]["id"], m_id)

        # Learning state due list tomorrow/day after tomorrow
        future_now = datetime.now(timezone.utc) + timedelta(days=2)
        state = get_learning_state("math_student", now=future_now, db_path=self.db_path)
        self.assertIn("due", state)
        self.assertEqual(len(state["due"]), 1)
        self.assertEqual(state["due"][0]["id"], m_id)


if __name__ == "__main__":
    unittest.main()
