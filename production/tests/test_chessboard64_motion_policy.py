"""Regression checks for narration re-timing and forward-only source playback."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "chessboard64"
sys.path.insert(0, str(PROJECT))

import render  # noqa: E402
from align_cuts_to_audio import align  # noqa: E402


class Chessboard64MotionPolicyTests(unittest.TestCase):
    def test_retimed_clause_map_shortens_courtroom_and_supermarket_slots(self):
        mapping = json.loads((PROJECT / "audio" / "cut-clauses.json").read_text(encoding="utf-8"))
        timings = json.loads((PROJECT / "audio" / "clause-times.json").read_text(encoding="utf-8"))
        aligned = align(mapping, timings, render.CUTS)
        durations = {}
        for entries in aligned.values():
            for current, following in zip(entries, entries[1:]):
                durations[current[1]] = following[0] - current[0]
        self.assertLess(durations["S06"], 6.0)
        self.assertLess(durations["S09"], 5.5)
        self.assertEqual(mapping["N02"][0]["shot"], "S10")
        self.assertIn("超市做理货员", mapping["N02"][0]["clause"])
        self.assertIn("公开报道说", mapping["N02"][3]["clause"])
        self.assertIn("六十三个记号", mapping["N02"][5]["clause"])

    def test_excessive_slow_motion_fails_instead_of_reversing_or_ping_ponging(self):
        take, factor = render.plan_time_stretch(5.2, 4.868, "S06")
        self.assertAlmostEqual(take, 4.868)
        self.assertLessEqual(factor, render.MAX_SLOW_MOTION_FACTOR)
        with self.assertRaisesRegex(RuntimeError, "reverse playback and ping-pong loops are prohibited"):
            render.plan_time_stretch(8.733, 4.868, "S09")
        source = (PROJECT / "render.py").read_text(encoding="utf-8")
        self.assertNotIn("pingpong=True", source)
        self.assertNotIn("reverse,trim", source)

    def test_static_opening_is_removed_from_s04_source_window(self):
        self.assertEqual(render.WINDOWS["S04"], (1.4, 3.6))


if __name__ == "__main__":
    unittest.main()
