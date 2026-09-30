"""Font stack with per-character fallback.

The bundled brush face (MaShanZheng) is a real Chinese glyph source but has **no
math symbols** — ``√``, ``²`` and ``≈`` come out as tofu boxes.  A noire explainer
full of formulas therefore needs a fallback chain: Chinese from the brush face,
math and Latin from DejaVu.

Coverage is probed by rendering each codepoint and comparing against the font's
``.notdef`` signature, so no font-parsing dependency is required and the answer
reflects what the rasteriser will actually do.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_PROBE_SIZE = (240, 240)
_PROBE_ORIGIN = (60, 60)
_NOTDEF = "\uE000"  # Private Use Area: guaranteed absent from these fonts


def _signature(font: ImageFont.FreeTypeFont, char: str) -> bytes:
    canvas = Image.new("L", _PROBE_SIZE, 0)
    ImageDraw.Draw(canvas).text(_PROBE_ORIGIN, char, font=font, fill=255)
    return np.asarray(canvas, dtype=np.uint8).tobytes()


class FontStack:
    """A list of fonts consulted in order, per character."""

    def __init__(self, entries: Sequence[Tuple[str, Path, int]]) -> None:
        self.names: List[str] = []
        self.fonts: List[ImageFont.FreeTypeFont] = []
        for name, path, size in entries:
            if not Path(path).exists():
                raise FileNotFoundError(f"font missing: {path}")
            self.names.append(name)
            self.fonts.append(ImageFont.truetype(str(path), size))
        self._notdef = [_signature(font, _NOTDEF) for font in self.fonts]
        self._coverage: Dict[str, int] = {}

    def pick(self, char: str) -> int:
        """Index of the first font that really draws ``char``."""
        cached = self._coverage.get(char)
        if cached is not None:
            return cached
        choice = 0
        for index, font in enumerate(self.fonts):
            signature = _signature(font, char)
            if signature == self._notdef[index]:
                continue  # tofu
            if not signature.strip(b"\x00"):
                continue  # blank
            choice = index
            break
        self._coverage[char] = choice
        return choice

    @property
    def primary(self) -> ImageFont.FreeTypeFont:
        return self.fonts[0]

    def font_for(self, char: str) -> ImageFont.FreeTypeFont:
        return self.fonts[self.pick(char)]

    def measure(self, text: str, tracking: float = 0.0) -> float:
        total = 0.0
        for char in text:
            total += self.font_for(char).getlength(char) + tracking
        return total

    def line_height(self) -> float:
        ascent, descent = self.primary.getmetrics()
        return ascent + descent


def cjk_stack(project_dir: Path, size: int, latin_size: Optional[int] = None) -> FontStack:
    """Brush face for Chinese, DejaVu for math/Latin."""
    fonts_dir = Path(project_dir) / "assets" / "fonts"
    latin_size = latin_size or size
    return FontStack([
        ("mashanzheng", fonts_dir / "MaShanZheng-Regular.ttf", size),
        ("dejavu", fonts_dir / "DejaVuSans.ttf", latin_size),
    ])


@lru_cache(maxsize=16)
def cached_stack(project_dir: str, size: int) -> FontStack:
    return cjk_stack(Path(project_dir), size)


def draw_text(
    draw: ImageDraw.ImageDraw,
    origin: Tuple[float, float],
    text: str,
    stack: FontStack,
    fill,
    anchor: str = "la",
    tracking: float = 0.0,
    stroke_width: int = 0,
    stroke_fill=None,
) -> float:
    """Draw ``text`` left to right, switching font per character.

    Returns the advance width so callers can lay out multi-part lines.
    """
    x, y = origin
    for char in text:
        font = stack.font_for(char)
        draw.text(
            (x + tracking / 2.0, y), char, font=font, fill=fill, anchor=anchor,
            stroke_width=stroke_width, stroke_fill=stroke_fill,
        )
        x += font.getlength(char) + tracking
    return x - origin[0]
