"""Regression tests for the three-stage render, narration, and QC handoff."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / ".github" / "workflows"
PROJECT = ROOT / "production" / "chessboard64" / "workflows"


class Chessboard64DeliveryWorkflowTests(unittest.TestCase):
    def _paired(self, name: str) -> tuple[str, str]:
        installed = (GITHUB / name).read_text(encoding="utf-8")
        template = (PROJECT / name).read_text(encoding="utf-8")
        self.assertEqual(installed, template, f"{name} template and installed workflow diverged")
        return installed, template

    def test_render_workflow_has_runner_tts_fallback_and_artifact_receipts(self):
        text, _ = self._paired("chessboard64-render.yml")
        self.assertIn("edge-tts>=7,<8", text)
        self.assertIn("FORCE_EDGE_TTS: 'true'", text)
        self.assertIn("EDGE_TTS_VOICE: 'zh-CN-YunjianNeural'", text)
        self.assertIn("EDGE_TTS_PITCH: '-8Hz'", text)
        runner = (ROOT / "production/chessboard64/run_project.sh").read_text()
        self.assertIn("FORCE_EDGE_TTS", runner)
        self.assertIn("EDGE_TTS_PITCH", runner)
        self.assertIn("'narration_pitch': narration['pitch']", runner)
        self.assertIn("narration_pitch", (PROJECT.parent / "render.py").read_text())
        self.assertIn("generate_edge_audio.py", runner)
        self.assertIn("align_cuts_to_audio.py", (ROOT / "production/chessboard64/run_project.sh").read_text())
        self.assertIn("production/chessboard64/audio/*.mp3", text)
        self.assertIn("production/chessboard64/delivery/narration-manifest.json", text)
        self.assertIn("never committed to Git", (ROOT / "production/chessboard64/run_project.sh").read_text())

    def test_verbatim_workflow_uses_hash_verified_narration_from_same_render_artifact(self):
        text, _ = self._paired("chessboard64-verbatim.yml")
        self.assertIn("narration-manifest.json", text)
        self.assertIn('echo "AUDIO_DIR=$audio_dir"', text)
        self.assertIn('--narration "$AUDIO_DIR"', text)
        self.assertNotIn("fetch_audio.py", text, "verbatim QC must not silently substitute another voice")
        self.assertIn("SHA mismatch", text)

    def test_signed_media_urls_are_redacted_from_runner_diagnostics(self):
        workflow, _ = self._paired("chessboard64-render.yml")
        source = (ROOT / "production/chessboard64/fetch_sources.py").read_text(encoding="utf-8")
        self.assertIn("[SIGNED_QUERY_REDACTED]", workflow)
        self.assertIn("TOKEN_[REDACTED]", workflow)
        self.assertIn("def safe_url(url: str)", source)
        self.assertIn("[signed query redacted]", source)
        self.assertNotIn('print(f"FETCH {sid} {url}"', source)
        self.assertNotIn("Download failed for {url}", source)

    def test_visual_workflow_fails_closed_on_any_strict_machine_anomaly(self):
        text, _ = self._paired("chessboard64-visual-qc.yml")
        for condition in (
            "audit['status'] == 'PASS'",
            "video['decoded_frames'] == expected",
            "(video['width'], video['height']) == (1920, 1080)",
            "checks['unplanned_black_frame_count'] == 0",
            "checks['temporal_outlier_windows']",
            "checks['face_review_candidates']",
            "checks['hand_landmark_extreme_events']",
        ):
            self.assertIn(condition, text)
        self.assertIn("if: always()", text, "failed QC must still upload its evidence package")

    def test_direct_mp4_release_verifies_the_render_before_upload(self):
        text, _ = self._paired("chessboard64-release-mp4.yml")
        for requirement in (
            "gh run download",
            "render-manifest.json",
            "hashlib.sha256",
            "gh release create",
            "gh release upload",
            "releases/download/$RELEASE_TAG/$MP4_ASSET_NAME",
        ):
            self.assertIn(requirement, text)
        self.assertIn("MP4_RELEASE_REQUEST", text)
        self.assertNotIn("git add", text, "the MP4 must remain outside Git")


if __name__ == "__main__":
    unittest.main()
