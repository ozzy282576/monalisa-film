"""Synthetic regressions for chessboard64's pause-aware TTS post-processing."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1] / "chessboard64"
sys.path.insert(0, str(PROJECT))
import tighten_pauses as tp  # noqa: E402


def tone(seconds: float, amplitude: float = 0.12) -> np.ndarray:
    count = round(seconds * tp.RATE)
    t = np.arange(count, dtype=np.float32) / tp.RATE
    return amplitude * np.sin(2 * np.pi * 220 * t)


def sample(*parts: tuple[str, float]) -> np.ndarray:
    chunks = []
    for kind, seconds in parts:
        chunks.append(np.zeros(round(seconds * tp.RATE), np.float32) if kind == "silence"
                      else tone(seconds))
    return np.concatenate(chunks)


class TightenPausesTests(unittest.TestCase):
    def test_long_explicit_pause_is_kept_at_half_second(self):
        x = sample(("silence", 0.2), ("tone", 0.5), ("silence", 0.9),
                   ("tone", 0.5), ("silence", 0.4))
        y, _cuts, preserved = tp.tighten(x, [0.7])
        self.assertEqual(len(preserved), 1)
        self.assertAlmostEqual(preserved[0]["kept_seconds"], 0.5, places=3)
        self.assertEqual(preserved[0]["inserted_seconds"], 0.0)
        self.assertLess(len(y), len(x))

    def test_short_explicit_pause_is_padded_without_cutting_speech(self):
        x = sample(("silence", 0.2), ("tone", 0.5), ("silence", 0.2),
                   ("tone", 0.5), ("silence", 0.4))
        y, _cuts, preserved = tp.tighten(x, [0.7])
        self.assertEqual(len(preserved), 1)
        self.assertAlmostEqual(preserved[0]["kept_seconds"], 0.5, places=3)
        self.assertAlmostEqual(preserved[0]["inserted_seconds"], 0.3, places=2)
        # The added half-second pause offsets most of the ordinary lead/tail tightening.
        self.assertGreater(len(y), len(x) - round(0.5 * tp.RATE))

    def test_ordinary_long_silence_is_capped(self):
        x = sample(("tone", 0.5), ("silence", 1.0), ("tone", 0.5))
        _y, cuts, preserved = tp.tighten(x)
        interior = [row for row in cuts if abs(row[0] - 0.5) < 0.02]
        self.assertEqual(len(interior), 1)
        self.assertAlmostEqual(interior[0][2], tp.CAP, places=3)
        self.assertEqual(preserved, [])

    def test_phrase_alignment_finds_the_pause_after_matching_clause(self):
        x = sample(("silence", 0.2), ("tone", 0.6), ("silence", 0.5),
                   ("tone", 0.6), ("silence", 0.3))
        start, warning = tp.explicit_pause_start(
            "N02", "第一句。第二句。", x, {"N02": "第一句"})
        self.assertIsNone(warning)
        self.assertIsNotNone(start)
        self.assertAlmostEqual(start, 0.8, places=2)

    def test_final_phrase_gets_a_pause_appended_if_tts_has_none(self):
        x = tone(1.0)
        start, warning = tp.explicit_pause_start(
            "N02", "目标短语。", x, {"N02": "目标短语"})
        self.assertIsNone(warning)
        self.assertAlmostEqual(start, 1.0, places=2)
        y, _cuts, preserved = tp.tighten(x, [start])
        self.assertAlmostEqual(len(y) / tp.RATE, 1.5, places=2)
        self.assertTrue(preserved[0]["appended_after_clip"])


if __name__ == "__main__":
    unittest.main()
