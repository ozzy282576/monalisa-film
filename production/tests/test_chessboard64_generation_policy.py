"""Retry and moderation regressions for the free CogVideoX-Flash generator."""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    def test_forced_refresh_reissues_only_a_fresh_url_with_matching_source_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, qa = root / "sources", root / "qa"
            sources.mkdir()
            qa.mkdir()
            original = root / "original.mp4"
            original.write_bytes(b"verified provider video bytes")
            wanted = "same-prompt-hash"
            row = {
                "id": "S19", "status": "expired", "request_hash": wanted,
                "task_id": "prior-task", "sha256": gen.digest(original),
                "bytes": original.stat().st_size,
            }
            doc = {"shots": {"S19": {"id": "S19"}},
                   "previous_results": {"S19": [row]}}
            expiry = int(time.time()) + gen.MIN_REFRESH_URL_TTL_SECONDS + 7200
            url = "https://example.invalid/video.mp4?Expires=%d" % expiry
            videos = SimpleNamespace(retrieve_videos_result=Mock(return_value={
                "task_status": "SUCCESS", "video_result": [{"url": url}],
            }))
            client = SimpleNamespace(videos=videos)
            saved = []

            def fake_download(_url, dest):
                shutil.copyfile(original, dest)

            with patch.object(gen, "download", side_effect=fake_download), \
                 patch.object(gen, "inspect_clip", return_value={"duration": 5.0}), \
                 patch.object(gen, "checkpoint", side_effect=lambda *a, **kw: saved.append(kw)):
                recovered = gen.refresh_forced_source_from_task(
                    client, doc, "S19", wanted, sources, qa, publish=True
                )

            self.assertTrue(recovered)
            self.assertEqual(videos.retrieve_videos_result.call_args.kwargs, {"id": "prior-task"})
            self.assertEqual((sources / "S19.mp4").read_bytes(), original.read_bytes())
            self.assertEqual(saved[-1]["status"], "completed")
            self.assertEqual(saved[-1]["request_hash"], wanted)
            self.assertEqual(saved[-1]["sha256"], row["sha256"])
            self.assertEqual(saved[-1]["video_url"], url)

    def test_forced_refresh_harvests_a_submitted_task_that_was_never_collected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, qa = root / "sources", root / "qa"
            sources.mkdir()
            qa.mkdir()
            media = root / "fresh.mp4"
            media.write_bytes(b"freshly harvested provider video")
            wanted = "same-prompt-hash"
            # 上一轮被取消时只留下 queued 收据：有 task_id，没有 SHA-256。
            doc = {"shots": {"S23": {"id": "S23"}},
                   "previous_results": {"S23": [{"id": "S23", "status": "queued",
                                                 "request_hash": wanted,
                                                 "task_id": "cancelled-run-task"}]}}
            url = "https://example.invalid/v.mp4?Expires=%d" % (
                int(time.time()) + gen.MIN_REFRESH_URL_TTL_SECONDS + 3600)
            client = SimpleNamespace(videos=SimpleNamespace(
                retrieve_videos_result=Mock(return_value={
                    "task_status": "SUCCESS", "video_result": [{"url": url}]})))
            saved = []
            with patch.object(gen, "download", side_effect=lambda _u, dest: shutil.copyfile(media, dest)), \
                 patch.object(gen, "inspect_clip", return_value={"duration": 5.1}), \
                 patch.object(gen, "checkpoint", side_effect=lambda *a, **kw: saved.append(kw)):
                recovered = gen.refresh_forced_source_from_task(
                    client, doc, "S23", wanted, sources, qa)
            self.assertTrue(recovered)
            self.assertEqual(saved[-1]["status"], "completed")
            self.assertEqual(saved[-1]["sha256"], gen.digest(media))

    def test_forced_refresh_never_downloads_an_expired_task_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, qa = root / "sources", root / "qa"
            sources.mkdir()
            qa.mkdir()
            wanted = "same-prompt-hash"
            row = {"request_hash": wanted, "task_id": "prior-task", "sha256": "abc"}
            doc = {"shots": {"S19": {"id": "S19"}},
                   "previous_results": {"S19": [row]}}
            expired_url = "https://example.invalid/video.mp4?Expires=%d" % (int(time.time()) - 1)
            client = SimpleNamespace(videos=SimpleNamespace(
                retrieve_videos_result=Mock(return_value={
                    "task_status": "SUCCESS", "video_result": [{"url": expired_url}],
                })
            ))
            download = Mock()
            with patch.object(gen, "download", download):
                recovered = gen.refresh_forced_source_from_task(
                    client, doc, "S19", wanted, sources, qa
                )
            self.assertFalse(recovered)
            download.assert_not_called()

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

    def test_submissions_sweep_every_shot_instead_of_blocking_on_one(self):
        source = Path(gen.__file__).read_text(encoding="utf-8")
        # 1305 是全模型限流：必须轮流扫所有待生成镜头抢放行窗口，不能卡在某一镜上。
        self.assertIn("while needs_generation and time.monotonic() < submit_deadline", source)
        self.assertIn("SUBMIT_SWEEP", source)
        # 收获与提交分离：任务在服务端并行出片，本地不再「交一条等一条」，
        # 而且每扫一轮提交就顺手收一次，已出片的镜头立刻落地。
        self.assertIn("def harvest_sweep(harvest_deadline)", source)
        self.assertIn("harvested = harvest_sweep(deadline)", source)
        self.assertIn("while queued and time.monotonic() < deadline", source)
        self.assertNotIn("attempt < 20", source)
        self.assertGreaterEqual(gen.SUBMIT_PHASE_SECONDS, 60 * 60)
        self.assertLessEqual(gen.HARVEST_SWEEP_SECONDS, 30)

    def test_persisted_errors_never_leak_signed_urls_or_keys(self):
        self.assertEqual(gen.redact("timeout for https://cdn.invalid/a.mp4?Expires=1&Signature=xyz"),
                         "timeout for [URL_REDACTED]")
        self.assertIn("[REDACTED]", gen.redact('api_key="sk-secret-value"'))
        self.assertNotIn("sk-secret-value", gen.redact('api_key="sk-secret-value"'))


if __name__ == "__main__":
    unittest.main()
