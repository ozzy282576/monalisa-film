"""Hand lettering.

The upstream project bakes handwriting into the master page with its image
tool (``--text-mode image2``) and only falls back to a system font when the user
explicitly asks for it.  This port keeps both modes, but defaults to the font
mode because the shipped OFL brush face (MaShanZheng) is a *real* glyph source:
every Chinese character is guaranteed correct, whereas an image model can and
does draw wrong strokes.

Geometry is ported from ``src/TextWipe.tsx``: the same box, the same font-size
heuristic, the same line-height, letter-spacing and -0.35deg tilt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import contract
from .imaging import RGBA

FONT_FILENAME = "MaShanZheng-Regular.ttf"

INK = (23, 23, 20)
MAX_WIDTH = 852.0
MAX_HEIGHT = 306.0
LINE_HEIGHT = 1.34
LETTER_SPACING = 0.025
TILT_DEGREES = -0.35
STROKE_PX = 0.0  # MaShanZheng is already a brush face; faux-bold muddies it


@dataclass(frozen=True)
class CaptionMetrics:
    font_size: float
    lines: Tuple[str, ...]
    line_height: float


def default_font_path(project_dir: Path) -> Path:
    candidate = project_dir / "assets" / "fonts" / FONT_FILENAME
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"handwriting font not found at {candidate}; run tools/bootstrap.sh"
    )


def font_size_for(text: str) -> float:
    """Port of ``fallbackFontSize`` in src/TextWipe.tsx."""
    lines = [line for line in text.split("\n") if line]
    line_count = max(1, len(lines))
    longest = max((len(line) for line in lines), default=1)
    width_limited = int(MAX_WIDTH / (longest * 1.08))
    height_limited = int(MAX_HEIGHT / (line_count * 1.28))
    return float(max(48, min(82, width_limited, height_limited)))


def metrics_for(text: str) -> CaptionMetrics:
    size = font_size_for(text)
    return CaptionMetrics(
        font_size=size,
        lines=tuple(line for line in text.split("\n") if line),
        line_height=size * LINE_HEIGHT,
    )


def _measure_line(font: ImageFont.FreeTypeFont, line: str, size: float) -> float:
    advance = 0.0
    for index, char in enumerate(line):
        advance += font.getlength(char)
        if index:
            advance += size * LETTER_SPACING
    return advance


def _draw_line(
    draw: ImageDraw.ImageDraw,
    origin: Tuple[float, float],
    line: str,
    font: ImageFont.FreeTypeFont,
    size: float,
    stroke: int,
    jitter: float,
    rng: np.random.Generator | None,
) -> None:
    x, baseline = origin
    for char in line:
        dx = dy = 0.0
        if rng is not None and jitter > 0:
            dx = float(rng.uniform(-jitter, jitter))
            dy = float(rng.uniform(-jitter, jitter))
        draw.text(
            (x + dx, baseline + dy),
            char,
            font=font,
            fill=INK,
            anchor="ls",
            stroke_width=stroke,
            stroke_fill=INK,
        )
        x += font.getlength(char) + size * LETTER_SPACING


def render_caption_plate(
    text: str,
    canvas_width: int,
    canvas_height: int,
    font_path: Path,
    jitter: float = 0.0,
    seed: int = 7,
) -> RGBA:
    """Render the caption into a transparent, canvas-sized RGBA plate."""
    factor = canvas_width / contract.DESIGN_WIDTH
    box = contract.caption_box(canvas_width)
    text_box = contract.CAPTION_TEXT_BOX

    plate = Image.new("RGBA", (int(round(box["width"])), int(round(box["height"]))), (0, 0, 0, 0))
    metrics = metrics_for(text)
    size = metrics.font_size * factor
    if size < 6:
        raise ValueError("caption box too small for the requested canvas")

    font = ImageFont.truetype(str(font_path), max(6, int(round(size))))
    draw = ImageDraw.Draw(plate)
    ascent, descent = font.getmetrics()
    line_height = metrics.line_height * factor
    leading = line_height - (ascent + descent)
    stroke = max(0, int(round(STROKE_PX * factor)))

    rng = np.random.default_rng(seed) if jitter > 0 else None
    origin_x = (text_box["left"] - contract.CAPTION_BOX["left"]) * factor
    origin_y = (text_box["top"] - contract.CAPTION_BOX["top"]) * factor
    for index, line in enumerate(metrics.lines):
        baseline = origin_y + index * line_height + leading / 2.0 + ascent
        _draw_line(draw, (origin_x, baseline), line, font, size, stroke, jitter * factor, rng)

    if abs(TILT_DEGREES) > 0.01:
        plate = plate.rotate(TILT_DEGREES, resample=Image.BICUBIC, expand=False)

    full = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    full.alpha_composite(plate, (int(round(box["left"])), int(round(box["top"]))))
    return np.asarray(full, dtype=np.float32) / 255.0


def text_extents(text: str, font_path: Path) -> Tuple[float, float]:
    """Approximate (width, height) of the laid-out caption in design space."""
    metrics = metrics_for(text)
    font = ImageFont.truetype(str(font_path), max(6, int(round(metrics.font_size))))
    width = max((_measure_line(font, line, metrics.font_size) for line in metrics.lines), default=0.0)
    height = metrics.line_height * max(1, len(metrics.lines))
    return width, height
