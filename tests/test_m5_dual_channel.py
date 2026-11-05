from datetime import datetime, timezone
import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.platform.domain_store import init_domain_db
from backend.platform.mistake_store import confirm_mistake, create_pending, init_mistake_db
from backend.platform.review_planner import list_outbox, run_review_push
from backend.tools.feishu_webhook import build_feishu_payload
from backend.workers.review_reply import process_reply_http, verify_feishu_signature


class TestM5DualChannelRetry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        init_domain_db(self.db_path)
        init_mistake_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            try:
                os.unlink(self.tmp.name)
            except OSError:
                pass

    def test_feishu_payload_signature(self):
        # Without secret: pure text payload
        plain = build_feishu_payload("测试卡片")
        self.assertEqual(plain["msg_type"], "text")
        self.assertEqual(plain["content"]["text"], "测试卡片")
        self.assertNotIn("sign", plain)

        # With secret and explicit timestamp: contains signature
        signed = build_feishu_payload("测试卡片", secret="my_feishu_secret", timestamp=1700000000)
        self.assertEqual(signed["msg_type"], "text")
        self.assertEqual(signed["timestamp"], "1700000000")
        self.assertIn("sign", signed)
        self.assertTrue(len(signed["sign"]) > 10)

    def test_feishu_reply_signature_verification(self):
        secret = "test_webhook_secret"
        ts = "1700000000"
        nonce = "abc123nonce"
        body = b'{"text": "ok"}'

        # Correct signature
        import hashlib
        import hmac

        bytes_to_sign = f"{ts}{nonce}{secret}".encode("utf-8") + body
        sig = hashlib.sha256(bytes_to_sign).hexdigest()

        self.assertTrue(verify_feishu_signature(ts, nonce, body, secret, sig))
        self.assertFalse(verify_feishu_signature(ts, nonce, body, secret, "wrong_sig"))

        # In process_reply_http:
        code_unauth, _ = process_reply_http(
            body,
            "student",
            feishu_secret=secret,
            lark_timestamp=ts,
            lark_nonce=nonce,
            lark_signature="wrong_sig",
        )
        self.assertEqual(code_unauth, 401)

    def test_dual_channel_retry_isolation(self):
        # 1. Seed a confirmed due mistake
        m_id = create_pending(
            "student",
            subject="数学",
            concept="微积分",
            error_type="概念混淆",
            question_text="求导",
            student_answer="x",
            correct_answer="2x",
            db_path=self.db_path,
        )
        confirm_mistake(m_id, db_path=self.db_path)

        # Make next_review_at in the past so it is due
        as_of = datetime(2026, 11, 5, 8, 0, 0, tzinfo=timezone.utc)
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE mistakes SET next_review_at = '2026-11-01T00:00:00+00:00' WHERE id = ?", (m_id,))
            conn.commit()

        feishu_calls = []
        smtp_calls = []

        def mock_feishu_sender(body: str):
            feishu_calls.append(body)

        def mock_smtp_sender(body: str):
            smtp_calls.append(body)
            if len(smtp_calls) == 1:
                # First run fails on SMTP
                raise RuntimeError("SMTP 535 Authentication failed")

        # First run: Feishu succeeds, SMTP fails
        res1 = run_review_push(
            "student",
            now=as_of,
            db_path=self.db_path,
            sender=mock_feishu_sender,
            mailer=mock_smtp_sender,
        )

        self.assertFalse(res1["sent"])
        self.assertEqual(res1["status"], "failed")
        self.assertIn("SMTP 535", res1["error"])
        self.assertEqual(len(feishu_calls), 1)
        self.assertEqual(len(smtp_calls), 1)

        # Inspect outbox in SQLite
        outbox = list_outbox("student", db_path=self.db_path)
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]["status"], "failed")
        cs = json.loads(outbox[0]["channel_status"])
        self.assertEqual(cs["feishu"], "sent")
        self.assertIn("failed", cs["smtp"])

        # Second run (retry on same day): Feishu MUST be skipped, SMTP succeeds!
        res2 = run_review_push(
            "student",
            now=as_of,
            db_path=self.db_path,
            sender=mock_feishu_sender,
            mailer=mock_smtp_sender,
        )

        self.assertTrue(res2["sent"])
        self.assertEqual(res2["status"], "sent")
        # Feishu call count MUST STILL BE 1 (isolated, not bombarded!)
        self.assertEqual(len(feishu_calls), 1)
        # SMTP was called the 2nd time and succeeded!
        self.assertEqual(len(smtp_calls), 2)

        # Inspect outbox after successful retry
        outbox2 = list_outbox("student", db_path=self.db_path)
        self.assertEqual(len(outbox2), 1)
        self.assertEqual(outbox2[0]["status"], "sent")
        cs2 = json.loads(outbox2[0]["channel_status"])
        self.assertEqual(cs2["feishu"], "sent")
        self.assertEqual(cs2["smtp"], "sent")

        # Third run: Already delivered, nothing called
        res3 = run_review_push(
            "student",
            now=as_of,
            db_path=self.db_path,
            sender=mock_feishu_sender,
            mailer=mock_smtp_sender,
        )
        self.assertEqual(res3["reason"], "already_delivered")
        self.assertEqual(len(feishu_calls), 1)
        self.assertEqual(len(smtp_calls), 2)


if __name__ == "__main__":
    unittest.main()
