"""Rendering contract for the hand-drawn story video.

Every number in this module is a direct port of the upstream
``story-to-handdrawn-video`` Remotion components (``src/Scene.tsx``,
``src/LayerWipe.tsx``, ``src/TextWipe.tsx``, ``src/StoryVideo.tsx``,
``src/storyboard.ts``) and of ``DESIGN.md``.  All coordinates are expressed in
the 1080x1440 *design space*; :func:`scaled` converts them to the output canvas
so the 720x960 preview is pixel-proportional to the final render.

Keeping the contract in one place is what makes this port faithful: the Python
renderer never invents geometry, it only rasterises the geometry the upstream
Remotion project already declares.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

# --- Canvas (DESIGN.md "Canvas") -------------------------------------------

DESIGN_WIDTH = 1080
DESIGN_HEIGHT = 1440
DESIGN_FPS = 30
PREVIEW_SCALE = 2.0 / 3.0  # 1080x1440 -> 720x960
RATIO = "3:4"
BACKGROUND = "#FFFFFF"

# --- Layout ----------------------------------------------------------------
# TextWipe:  top 86 / left 96 / width 888 / height 288, zIndex 40
# LayerWipe: left 74 / right 74 / top 382 / bottom 42, zIndex 10/20/30
CAPTION_BOX = {"top": 86, "left": 96, "width": 888, "height": 288}
CAPTION_TEXT_BOX = {"top": 92, "left": 104, "right": 96}  # font fallback branch
ILLUSTRATION_BOX = {"top": 382, "left": 74, "right": 74, "bottom": 42}

# --- Layer ordering --------------------------------------------------------

Z_BW = 10
Z_DETAIL = 20
Z_COLOR = 30
Z_TEXT = 40

# --- CSS filter chains (LayerWipe treatmentFilter) -------------------------

TREATMENTS: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "bw": (("grayscale", 1.0), ("contrast", 1.72), ("brightness", 1.12)),
    "detail": (("grayscale", 1.0), ("contrast", 1.28), ("brightness", 1.055)),
    "color": (("brightness", 1.035), ("contrast", 1.04)),
}

# Local BW derivation, ported from scripts/page-assets.mjs:
#   format=gray, eq=contrast=1.18:brightness=0.035,
#   unsharp=5:5:0.55:5:5:0
BW_DERIVE = {
    "contrast": 1.18,
    "brightness": 0.035,
    "unsharp_radius": 2.0,  # (msize 5 - 1) / 2
    "unsharp_percent": 55,  # luma_amount 0.55
}

# Master plate normalisation (page-assets.mjs): crop below the caption split,
# then contain-fit into a white-padded square.
PLATE_SQUARE = 1024
TEXT_PLATE_SIZE = (1536, 512)

# Composite-page layout detection (page-assets.mjs analyzeCompositeLayout)
LAYOUT_PREVIEW_WIDTH = 256
LAYOUT_INK_THRESHOLD = 238
LAYOUT_INK_RATIO = 0.012
LAYOUT_SEARCH = (0.22, 0.52)
LAYOUT_MAX_SPLIT = 0.50
LAYOUT_PADDING_RATIO = 0.018


@dataclass(frozen=True)
class RevealStep:
    """One layer of the ``text -> bw_full -> detail -> color`` reveal."""

    layer: str
    start_ratio: float
    duration_ratio: float
    z: int
    treatment: str


# Scene.tsx, speed mode: `enable_detail` false, layers [text, bw_full, color]
SPEED_REVEAL = (
    RevealStep("text", 0.00, 0.22, Z_TEXT, "text"),
    RevealStep("bw_full", 0.18, 0.40, Z_BW, "bw"),
    RevealStep("color", 0.52, 0.36, Z_COLOR, "color"),
)

# Scene.tsx, quality mode: `enable_detail` true
QUALITY_REVEAL = (
    RevealStep("text", 0.00, 0.16, Z_TEXT, "text"),
    RevealStep("bw_full", 0.16, 0.32, Z_BW, "bw"),
    RevealStep("detail", 0.48, 0.17, Z_DETAIL, "detail"),
    RevealStep("color", 0.65, 0.23, Z_COLOR, "color"),
)

# When a scene only carries the color plate it appears immediately
# (`staticColor`), with durationFrames = 1.
STATIC_COLOR = RevealStep("color", 0.0, 0.0, Z_COLOR, "color")

# --- Timing ----------------------------------------------------------------

DEFAULT_TRANSITION_SEC = 0.7
DEFAULT_PAGE_DURATION_SEC = 4.4
PAGE_FLIP_BOTTOM_SPLIT = 0.78
PAGE_FLIP_TOP_DELAY = 0.28
PAGE_FLIP_BOW = 0.19
PAGE_FLIP_BOW_BOTTOM = 0.78
PAGE_FLIP_FOLD_BASE = 24
PAGE_FLIP_FOLD_SPAN = 0.20


def scaled(value: float, canvas_width: int) -> float:
    """Convert a design-space measurement to the output canvas."""
    return value * (canvas_width / DESIGN_WIDTH)


def canvas_size(export_width: int, export_height: int) -> Tuple[int, int]:
    return int(export_width), int(export_height)


def caption_box(canvas_width: int) -> Dict[str, float]:
    factor = canvas_width / DESIGN_WIDTH
    return {
        "top": CAPTION_BOX["top"] * factor,
        "left": CAPTION_BOX["left"] * factor,
        "width": CAPTION_BOX["width"] * factor,
        "height": CAPTION_BOX["height"] * factor,
    }


def illustration_box(canvas_width: int, canvas_height: int) -> Dict[str, float]:
    factor = canvas_width / DESIGN_WIDTH
    return {
        "top": ILLUSTRATION_BOX["top"] * factor,
        "left": ILLUSTRATION_BOX["left"] * factor,
        "right": canvas_width - ILLUSTRATION_BOX["right"] * factor,
        "bottom": canvas_height - ILLUSTRATION_BOX["bottom"] * factor,
    }


def reveal_schedule(
    duration_frames: int,
    layers: Tuple[str, ...],
    enable_detail: bool,
) -> Tuple[RevealStep, ...]:
    """Reproduce Scene.tsx layer selection, including the ``staticColor`` case."""
    speed_mode = "detail" not in layers
    static_color = "color" in layers and "bw_full" not in layers and "detail" not in layers
    if static_color:
        return (STATIC_COLOR,)
    template = QUALITY_REVEAL if enable_detail else SPEED_REVEAL
    return tuple(step for step in template if step.layer in layers)


def reveal_frames(
    duration_frames: int,
    step: RevealStep,
    layers: Tuple[str, ...],
) -> Tuple[int, int]:
    """Absolute (start_frame, duration_frames) for one layer inside a scene."""
    if step is STATIC_COLOR:
        return 0, 1
    start = round(duration_frames * step.start_ratio)
    length = round(duration_frames * step.duration_ratio)
    return start, max(1, length)


def transition_frames(storyboard: dict) -> int:
    """Ported from src/storyboard.ts ``transitionFramesFor`` (whole storyboard)."""
    project = storyboard.get("project", {})
    if project.get("transition") != "page-flip":
        return 0
    fps = int(project.get("fps", DESIGN_FPS))
    requested = max(
        1, round(float(project.get("transition_sec") or DEFAULT_TRANSITION_SEC) * fps)
    )
    shortest = min(
        round(float(scene["duration_sec"]) * fps) for scene in storyboard["scenes"]
    )
    return min(requested, max(1, shortest * 45 // 100))


def total_frames(storyboard: dict) -> int:
    """Ported from src/storyboard.ts ``totalFramesFor`` (whole storyboard)."""
    project = storyboard.get("project", {})
    fps = int(project.get("fps", DESIGN_FPS))
    scene_frames = sum(
        round(float(scene["duration_sec"]) * fps) for scene in storyboard["scenes"]
    )
    overlap = transition_frames(storyboard) * max(0, len(storyboard["scenes"]) - 1)
    return max(1, scene_frames - overlap)


def timing_for_text(text: str) -> float:
    """Per-beat duration derived from caption length (4.4s .. 6.2s)."""
    lines = [line for line in text.split("\n") if line.strip()]
    characters = sum(len(line) for line in lines) or 1
    longest = max((len(line) for line in lines), default=1)
    width_driven = 3.9 + longest * 0.085
    density_driven = 3.6 + characters * 0.055
    return round(max(4.4, min(6.2, max(width_driven, density_driven))), 1)
