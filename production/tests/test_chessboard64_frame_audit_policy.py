from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production" / "chessboard64"))

from frame_audit_policy import selectable_frame_indices  # noqa: E402


class Chessboard64FrameAuditPolicyTests(unittest.TestCase):
    def test_opening_fade_endpoint_is_excluded_but_next_frame_is_scanned(self):
        selected = selectable_frame_indices(
            list(range(30)),
            {"start_frame": 0, "end_frame": 30},
            segment_index=0,
            segment_count=2,
            total_frames=60,
            fps=30.0,
        )
        self.assertNotIn(8, selected)  # final transition step of the 0.25 s fade
        self.assertIn(9, selected)     # first stable fully exposed frame
        self.assertEqual(selected, list(range(9, 28)))

    def test_cut_and_closing_fade_guards_remain_unchanged(self):
        selected = selectable_frame_indices(
            list(range(30, 60)),
            {"start_frame": 30, "end_frame": 60},
            segment_index=1,
            segment_count=2,
            total_frames=60,
            fps=30.0,
        )
        self.assertEqual(selected, list(range(32, 55)))


if __name__ == "__main__":
    unittest.main()
