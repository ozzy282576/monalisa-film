"""Retry and moderation regressions for the free CogVideoX-Flash generator."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1] / "chessboard64"
sys.path.insert(0, str(PROJECT))
import generate_cogvideox as gen  # noqa: E402


class GenerationPolicyTests(unittest.TestCase):
    def test_receipts_for_graphic_slots_are_archived_not_left_as_active_video(self):
        legacy = {"id": "S16", "status": "completed", "request_hash": "old-hash"}
        doc = {"shots": {"S10": {"id": "S10", "status": "completed"}, "S16": legacy}}
        self.assertEqual(gen.archive_inactive_receipts(doc, {"S10"}), ["S16"])
        self.assertNotIn("S16", doc["shots"])
        self.assertEqual(doc["previous_results"]["S16"], [legacy])
        self.assertEqual(gen.archive_inactive_receipts(doc, {"S10"}), [])
        self.assertEqual(doc["previous_results"]["S16"], [legacy])

    def test_forced_refresh_archives_expired_same_prompt_receipts_without_reusing_them(self):
        wanted = "same-prompt-hash"
        current = {"id": "S08", "status": "completed", "request_hash": wanted,
                   "video_url": "expired-current-url", "sha256": "current-sha"}
        history = {"id": "S08", "status": "completed", "request_hash": wanted,
                   "video_url": "expired-history-url", "sha256": "history-sha"}
        doc = {"shots": {"S08": current}, "previous_results": {"S08": [history]}}

        gen.prepare_forced_regeneration(doc, "S08", wanted)

        self.assertEqual(doc["shots"]["S08"], {"id": "S08"})
        self.assertEqual([row["status"] for row in doc["previous_results"]["S08"]],
                         ["expired", "expired"])
        self.assertEqual(gen.reuse_receipt(doc, "S08", wanted), "generate")

    def test_provider_sdk_retries_are_bounded_by_the_generator_loop(self):
        calls = {}

        class FakeZhipuAI:
            def __init__(self, **kwargs):
                calls.update(kwargs)

        with patch.dict(sys.modules, {"zhipuai": SimpleNamespace(ZhipuAI=FakeZhipuAI)}):
            client = gen.create_client("test-key")

        self.assertIsInstance(client, FakeZhipuAI)
        self.assertEqual(calls, {
            "api_key": "test-key",
            "timeout": gen.PROVIDER_REQUEST_TIMEOUT_SECONDS,
            "max_retries": 0,
        })
        self.assertEqual(gen.PROVIDER_REQUEST_TIMEOUT_SECONDS, 120)

    def test_rejected_submission_backoff_is_additive(self):
        self.assertEqual([gen.retry_delay(n) for n in range(1, 5)], [20, 25, 30, 35])
        self.assertEqual(gen.retry_delay(21), 120)
        with self.assertRaises(ValueError):
            gen.retry_delay(0)

    def test_moderation_is_separated_from_transient_rejection(self):
        self.assertTrue(gen.moderation_block("HTTP 400: error code 1301"))
        self.assertTrue(gen.moderation_block("敏感内容"))
        self.assertFalse(gen.moderation_block("HTTP 429: rate limit"))
        self.assertTrue(gen.retryable("HTTP 429: rate limit"))
        self.assertFalse(gen.retryable("HTTP 400: error code 1301"))

    def test_transient_task_failures_are_retried(self):
        self.assertTrue(gen.transient_fail("temporary connection timeout 503"))
        self.assertFalse(gen.transient_fail("1301 sensitive content"))

    def test_submit_rate_limit_retries_until_workflow_deadline(self):
        source = Path(gen.__file__).read_text(encoding="utf-8")
        self.assertIn("while not task_id and time.monotonic() < deadline", source)
        self.assertNotIn("attempt < 20", source)


if __name__ == "__main__":
    unittest.main()
