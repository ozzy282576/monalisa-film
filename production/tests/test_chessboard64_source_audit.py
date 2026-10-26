"""出片前源片体检闸门的回归测试：过期链接、缺时长、超限慢放都必须拦下。"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "chessboard64"
sys.path.insert(0, str(PROJECT))


def load_project_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load project module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_sources = load_project_module("chessboard64_audit_sources", PROJECT / "audit_sources.py")
render = load_project_module("chessboard64_render_for_audit", PROJECT / "render.py")
align = load_project_module("chessboard64_align_for_audit", PROJECT / "align_cuts_to_audio.py").align


def signed(hours_ahead: float) -> str:
    expiry = int(time.time() + hours_ahead * 3600)
    return f"https://example.invalid/chessboard64.mp4?Expires={expiry}&Signature=abc"


class SourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.story = json.loads((PROJECT / "story.json").read_text(encoding="utf-8"))
        cls.mapping = json.loads((PROJECT / "audio" / "cut-clauses.json").read_text(encoding="utf-8"))
        cls.timings = json.loads((PROJECT / "audio" / "clause-times.json").read_text(encoding="utf-8"))
        cls.dynamic = [shot["id"] for shot in cls.story["shots"] if shot["kind"] == "cogvideo"]

    def receipts(self, **overrides):
        shots = {}
        for sid in self.dynamic:
            shots[sid] = {"id": sid, "status": "completed", "video_url": signed(20),
                          "sha256": "a" * 64, "media": {"duration": 5.108}}
        for sid, row in overrides.items():
            shots[sid] = row
        return {"shots": shots}

    def run_audit(self, receipts, min_ttl_hours=2.0):
        return audit_sources.audit(receipts, self.story, render, align,
                                   self.mapping, self.timings, min_ttl_hours)

    def test_every_dynamic_shot_is_audited_and_a_healthy_set_passes(self):
        rows, problems = self.run_audit(self.receipts())
        self.assertEqual(problems, [])
        self.assertEqual([row["id"] for row in rows], self.dynamic)
        self.assertEqual(len(rows), 38)
        self.assertTrue(all(row["factor"] <= render.MAX_SLOW_MOTION_FACTOR for row in rows))

    def test_expired_or_near_expiry_links_block_the_render(self):
        receipts = self.receipts(S08={"id": "S08", "status": "completed", "video_url": signed(0.5),
                                      "sha256": "b" * 64, "media": {"duration": 5.108}})
        rows, problems = self.run_audit(receipts)
        self.assertEqual(problems, ["S08"])
        blocked = next(row for row in rows if row["id"] == "S08")
        self.assertIn("签名链接", blocked["note"])

    def test_unfinished_or_unmeasured_receipts_block_the_render(self):
        receipts = self.receipts(
            S19={"id": "S19", "status": "submitting"},
            S23={"id": "S23", "status": "completed", "video_url": signed(20), "sha256": "c" * 64},
        )
        _, problems = self.run_audit(receipts)
        self.assertEqual(problems, ["S19", "S23"])

    def test_sources_too_short_for_their_slot_block_the_render(self):
        receipts = self.receipts(S09={"id": "S09", "status": "completed", "video_url": signed(20),
                                      "sha256": "d" * 64, "media": {"duration": 1.5}})
        _, problems = self.run_audit(receipts)
        self.assertIn("S09", problems)

    def test_audit_never_echoes_signed_query_parameters(self):
        receipts = self.receipts()
        rows, _ = self.run_audit(receipts)
        self.assertNotIn("Signature", json.dumps(rows))
        self.assertIsNotNone(audit_sources.signed_url_expiry(signed(3)))
        self.assertIsNone(audit_sources.signed_url_expiry("https://example.invalid/clip.mp4"))


if __name__ == "__main__":
    unittest.main()
