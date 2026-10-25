"""Pure selection rules for frame-level anomaly analysis.

Kept separate from the computer-vision runtime so the planned-edit boundaries can
be unit-tested without installing FFmpeg, OpenCV, PyAV, or MediaPipe.
"""
from __future__ import annotations

import math

OPENING_FADE_SECONDS = 0.25
CLOSING_FADE_SECONDS = 0.18
CUT_GUARD_FRAMES = 2


def selectable_frame_indices(
    indices: list[int],
    segment: dict,
    segment_index: int,
    segment_count: int,
    total_frames: int,
    fps: float,
) -> list[int]:
    """Return frames eligible for within-shot motion/outlier checks.

    The first fully exposed frame is still part of the planned opening fade's
    transition step. Exclude that endpoint too, otherwise its expected luma and
    frame-difference step is misreported as an in-shot flash.
    """
    usable = indices[CUT_GUARD_FRAMES:-CUT_GUARD_FRAMES] if len(indices) > 8 else list(indices)
    if int(segment.get("start_frame", -1)) == 0:
        last_fade_frame = math.ceil(fps * OPENING_FADE_SECONDS)
        usable = [i for i in usable if i > last_fade_frame]
    if segment_index == segment_count - 1 and int(segment.get("end_frame", -1)) >= total_frames:
        closing_start = total_frames - round(fps * CLOSING_FADE_SECONDS)
        usable = [i for i in usable if i < closing_start]
    return usable
