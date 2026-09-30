"""Rendering contract for the 9:16 noire explainer.

Different product from the diary-comic pipeline in ``handdrawn/``: full-bleed
cinematic frames, spot colour used as *evidence colour*, bottom subtitles inside
the Douyin UI safe area, and per-beat durations driven by the real narration
audio rather than a character-count heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# --- Canvas ---------------------------------------------------------------

WIDTH = 1080
HEIGHT = 1920
FPS = 30
RATIO = "9:16"
BACKGROUND = (0, 0, 0)  # pure black: this look is ink on black, not paper

PREVIEW_SCALE = 0.5  # 540x960

# --- Evidence colour ------------------------------------------------------
# The whole frame is black/white except these two, and each beat uses at most one.

ALERT_RED = (193, 18, 31)      # #C1121F  4 m mark, trajectory, 3.6 m/s, guilt
COLD_BLUE = (46, 110, 142)     # #2E6E8E  puddle, detective's eyes, luminol, grid

INK = (10, 10, 10)
PAPER = (245, 244, 240)
SUBTITLE_FILL = (255, 255, 255)
SUBTITLE_STROKE = (0, 0, 0)

# --- Subtitle box ---------------------------------------------------------
# Douyin chrome covers roughly the bottom 15%; the right edge carries buttons and
# the lower-left carries the caption/username block, so subtitles sit centred
# above all of it.

SUBTITLE = {
    "centre_x": 0.5,
    "baseline_min": 0.775,   # fraction of canvas height
    "baseline_max": 0.880,
    "max_lines": 2,
    "line_gap": 1.22,
    "font_size": 60,
    "stroke_width": 9,
    "tracking": 2.0,
    "shadow_offset": (0, 5),
    "shadow_alpha": 0.85,
    "max_width": 0.86,       # fraction of canvas width
    # A gradient scrim under the caption. Without it, white lettering over a
    # blown-out white ground (the mud, the lawn, the puddle) is unreadable.
    "scrim_top": 0.715,
    "scrim_alpha": 0.66,
    "scrim_curve": 2.2,
}

# Big annotation callouts (the "4 m", "v ≈ 3.6 m/s" style beats)
ANNOTATION = {
    "max_width": 0.90,       # fraction of canvas width before auto-shrink
    "shrink": 0.90,
    "max_steps": 8,
    "font_size": 132,
    "stroke_width": 10,
    "tracking": 4.0,
    "shadow_alpha": 0.6,
    # A soft dark plate behind the annotation. The accent colours carry meaning
    # (red = the physical impossibility, blue = the forensic detail) so they
    # cannot simply be recoloured for contrast. Once the frames were graded
    # brighter, red-on-red-brown and grey-blue-on-grey-blue stopped being
    # readable; a feathered plate keeps the accent legible over any artwork.
    "plate_alpha": 0.46,
    "plate_bleed_x": 0.60,   # fraction of font size added around the text
    "plate_bleed_y": 0.34,
    "plate_feather": 22.0,
}

# --- Motion ---------------------------------------------------------------

@dataclass(frozen=True)
class Motion:
    """Ken-Burns camera move over a still frame."""

    scale_from: float
    scale_to: float
    centre_from: Tuple[float, float]
    centre_to: Tuple[float, float]
    ease: str = "smoothstep"

    @property
    def max_scale(self) -> float:
        return max(self.scale_from, self.scale_to)


MOTIONS: Dict[str, Motion] = {
    "push_in":       Motion(1.00, 1.09, (0.50, 0.50), (0.50, 0.50)),
    "push_in_high":  Motion(1.02, 1.12, (0.50, 0.44), (0.50, 0.40)),
    "pull_out":      Motion(1.10, 1.00, (0.50, 0.50), (0.50, 0.50)),
    "pan_right":     Motion(1.12, 1.12, (0.38, 0.50), (0.62, 0.50)),
    "pan_left":      Motion(1.12, 1.12, (0.62, 0.50), (0.38, 0.50)),
    "tilt_down":     Motion(1.10, 1.10, (0.50, 0.34), (0.50, 0.62)),
    "creep_in":      Motion(1.00, 1.05, (0.50, 0.50), (0.50, 0.52)),
    "hold":          Motion(1.00, 1.00, (0.50, 0.50), (0.50, 0.50)),
}

# --- Look -----------------------------------------------------------------

# 0.42 measured as a 45% cut to the 90th percentile on a night frame —
# it was reading as "too dark" rather than as mood. The mood now comes
# from the grade's split tone and black lift instead.
VIGNETTE_STRENGTH = 0.12

# Depth of field. Everything on a drawn panel is equally sharp, which is the
# single biggest reason the frames read as illustration rather than as film — a
# real lens cannot hold a subject and its background both in focus. A radial
# defocus away from the focus point buys most of the cinematic quality on its
# own, and costs one blur and one composite per frame.
DEPTH_OF_FIELD = 0.42
FOCUS_POINT = (0.5, 0.44)     # fraction of the frame; slightly above centre
DOF_FALLOFF = 1.15            # higher keeps more of the centre sharp
GRAIN_STRENGTH = 0.030
IMPACT_FLASH_FRAMES = 3      # hard-cut accents
CROSSFADE_FRAMES = 8


def canvas_size(preview: bool) -> Tuple[int, int]:
    if preview:
        return (int(WIDTH * PREVIEW_SCALE), int(HEIGHT * PREVIEW_SCALE))
    return (WIDTH, HEIGHT)


def ease_value(name: str, t: float) -> float:
    t = min(1.0, max(0.0, t))
    if name == "linear":
        return t
    if name == "ease_in":
        return t * t
    if name == "ease_out":
        return 1.0 - (1.0 - t) ** 2
    return t * t * (3.0 - 2.0 * t)  # smoothstep


@dataclass(frozen=True)
class Beat:
    """One scripted beat."""

    id: str
    scene: str
    narration: str
    on_screen: Optional[str]
    annotation: Optional[str]
    motion: str
    accent: Optional[str]      # "red" | "blue" | None
    sfx: Tuple[str, ...]
    min_duration: float
    image: Optional[str] = None
