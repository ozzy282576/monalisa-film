"""Bottom subtitles and big annotation callouts.

Subtitles are laid out inside the Douyin safe area with a per-character font
fallback (Chinese from the brush face, math/Latin from DejaVu), a hard black
outline and a soft drop shadow, so they stay legible over pure black and
blown-out white alike.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from PIL import Image, ImageDraw, ImageFilter

from . import contract
from .fonts import FontStack, cached_stack, draw_text


def wrap(text: str, stack: FontStack, max_width: float, tracking: float) -> List[str]:
    """Greedy wrap; CJK has no spaces so a character count is the right unit."""
    if not text:
        return []
    lines: List[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if not current or stack.measure(candidate, tracking) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = char
    if current:
        lines.append(current)
    return lines


# CJK line-breaking rules (行首禁则 / 行尾禁则). Breaking these looks broken to
# any Chinese reader, so violations dominate the scoring.
NO_LINE_START = set("。，、！？；：）】》」』…—～·%”’!,.;:?)]}")
NO_LINE_END = set("（【《「『“‘([{")
BREAK_AFTER = set("。，、！？；：…—～")


def balanced_wrap(
    text: str,
    stack: FontStack,
    max_width: float,
    tracking: float,
    max_lines: int = 2,
) -> List[str]:
    """Wrap into the fewest lines that fit, balanced, and typographically legal.

    Greedy wrapping on CJK leaves a stub second line ("...除了那" / "个老刑警。")
    and happily starts a line with a comma.  Captions are short, so we can search
    every split and rank them: punctuation violations first, then the widest
    line, with a nudge toward breaking after punctuation.
    """
    if not text:
        return []

    # one representative CJK glyph: the tolerance for preferring a nicer break
    tolerance = 1.15 * stack.measure("汉", tracking)

    for count in range(1, max_lines + 1):
        candidates: List[Tuple[int, float, List[str], int]] = []
        for cuts in _all_splits(len(text), count):
            parts = _slice(text, cuts)
            widest = max(stack.measure(part, tracking) for part in parts)
            if widest > max_width:
                continue
            violations = sum(
                1 for part in parts
                if part[0] in NO_LINE_START or part[-1] in NO_LINE_END
            )
            punctuation_breaks = sum(1 for cut in cuts if text[cut - 1] in BREAK_AFTER)
            candidates.append((violations, widest, parts, punctuation_breaks))

        valid = [c for c in candidates if c[0] == 0]
        if not valid:
            continue
        # Prefer breaking after punctuation, but never pay more than one glyph
        # of width to get it, and never for a single-line caption.
        best_widest = min(c[1] for c in valid)
        if count > 1:
            nicer = [c for c in valid
                     if c[1] <= best_widest + tolerance and c[3] > 0]
            if nicer:
                return max(nicer, key=lambda c: (c[3], -c[1]))[2]
        return min(valid, key=lambda c: c[1])[2]

    return wrap(text, stack, max_width, tracking)[:max_lines]


def _slice(text: str, cuts: Tuple[int, ...]) -> List[str]:
    parts: List[str] = []
    previous = 0
    for cut in cuts:
        parts.append(text[previous:cut])
        previous = cut
    parts.append(text[previous:])
    return [part for part in parts if part]


def _all_splits(length: int, count: int) -> Iterable[Tuple[int, ...]]:
    """Every way to cut ``length`` characters into ``count`` non-empty runs."""
    if count <= 1:
        yield ()
        return
    for first in range(1, length - count + 2):
        for rest in _all_splits(length - first, count - 1):
            yield (first, *(first + offset for offset in rest))


class TextPanel:
    """Reusable renderer for subtitle and annotation text."""

    def __init__(self, project_dir: Path, canvas_width: int, canvas_height: int = contract.HEIGHT) -> None:
        self.project_dir = Path(project_dir)
        self.factor = canvas_width / contract.WIDTH
        self.canvas_height = canvas_height
        self._scrim: Optional[Image.Image] = None

    def _scrim_layer(self, width: int, height: int) -> Image.Image:
        """Cached black gradient, transparent at the top, opaque at the bottom."""
        if self._scrim is not None and self._scrim.size == (width, height):
            return self._scrim
        cfg = contract.SUBTITLE
        top = int(round(height * cfg["scrim_top"]))
        mask = np.zeros((height, width), dtype=np.float32)
        if top < height:
            rows = height - top
            ramp = np.linspace(0.0, 1.0, rows, dtype=np.float32) ** cfg["scrim_curve"]
            mask[top:] = (ramp * cfg["scrim_alpha"])[:, None]
        alpha = Image.fromarray((mask * 255.0).astype(np.uint8), "L")
        self._scrim = Image.new("RGB", (width, height), (0, 0, 0))
        self._scrim.putalpha(alpha)
        return self._scrim

    def apply_scrim(self, frame: Image.Image) -> Image.Image:
        width, height = frame.size
        frame.paste(self._scrim_layer(width, height), (0, 0), self._scrim_layer(width, height))
        return frame

    def _stack(self, design_size: int) -> Tuple[FontStack, int, float]:
        size = max(12, int(round(design_size * self.factor)))
        return cached_stack(str(self.project_dir), size), size, self.factor

    def _shadow(
        self,
        canvas: Image.Image,
        lines: Sequence[str],
        stack: FontStack,
        size: int,
        tracking: float,
        centre_x: float,
        top: float,
        line_gap: float,
        offset: Tuple[float, float],
        alpha: float,
    ) -> None:
        layer = Image.new("L", canvas.size, 0)
        draw = ImageDraw.Draw(layer)
        y = top + offset[1]
        for line in lines:
            width = stack.measure(line, tracking)
            draw_text(draw, (centre_x - width / 2.0, y), line, stack,
                      fill=int(255 * alpha), anchor="la", tracking=tracking)
            y += size * line_gap
        blurred = layer.filter(ImageFilter.GaussianBlur(max(2.0, 6 * self.factor)))
        canvas.paste(Image.new("RGB", canvas.size, (0, 0, 0)), (0, 0), blurred)

    def subtitle(self, frame: Image.Image, text: str) -> Image.Image:
        text = (text or "").strip()
        if not text:
            return frame
        cfg = contract.SUBTITLE
        width, height = frame.size
        self.apply_scrim(frame)

        # Auto-shrink: a caption the script did not anticipate must not be
        # silently truncated to two lines, so step the size down until it fits.
        lines, stack, size, factor, tracking = [], None, 0, self.factor, 0.0
        design = cfg["font_size"]
        for _ in range(9):
            stack, size, factor = self._stack(design)
            tracking = cfg["tracking"] * factor
            candidate = balanced_wrap(
                text, stack, width * cfg["max_width"], tracking, cfg["max_lines"]
            )
            if candidate and len(candidate) <= cfg["max_lines"] and "".join(candidate) == text:
                lines = candidate
                break
            design = int(design * 0.92)
        if not lines:
            stack, size, factor = self._stack(cfg["font_size"])
            tracking = cfg["tracking"] * factor
            lines = balanced_wrap(
                text, stack, width * cfg["max_width"], tracking, cfg["max_lines"]
            )
        if not lines:
            return frame

        line_gap = cfg["line_gap"]
        block = size * line_gap * len(lines)
        baseline = height * (cfg["baseline_min"] + cfg["baseline_max"]) / 2.0
        top = baseline - block / 2.0
        centre_x = width * cfg["centre_x"]

        self._shadow(
            frame, lines, stack, size, tracking, centre_x, top, line_gap,
            (cfg["shadow_offset"][0] * factor, cfg["shadow_offset"][1] * factor),
            cfg["shadow_alpha"],
        )
        draw = ImageDraw.Draw(frame)
        stroke = max(1, int(round(cfg["stroke_width"] * factor)))
        y = top
        for line in lines:
            line_width = stack.measure(line, tracking)
            draw_text(draw, (centre_x - line_width / 2.0, y), line, stack,
                      fill=contract.SUBTITLE_FILL, anchor="la", tracking=tracking,
                      stroke_width=stroke, stroke_fill=contract.SUBTITLE_STROKE)
            y += size * line_gap
        return frame

    def _plate(
        self,
        frame: Image.Image,
        centre_x: float,
        top: float,
        width: float,
        height: float,
        size: float,
        cfg: dict,
    ) -> None:
        """Feathered dark plate behind an annotation.

        Accent colours are semantic and cannot be swapped for contrast, so the
        contrast is bought from the background instead.
        """
        alpha = float(cfg.get("plate_alpha", 0.0))
        if alpha <= 0.0:
            return
        bleed_x = size * float(cfg.get("plate_bleed_x", 0.0))
        bleed_y = size * float(cfg.get("plate_bleed_y", 0.0))
        x0 = int(centre_x - width / 2.0 - bleed_x)
        x1 = int(centre_x + width / 2.0 + bleed_x)
        y0 = int(top - bleed_y)
        y1 = int(top + height + bleed_y)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(frame.size[0], x1), min(frame.size[1], y1)
        if x1 <= x0 or y1 <= y0:
            return

        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mask).rectangle([0, 0, mask.size[0] - 1, mask.size[1] - 1],
                                       fill=int(round(alpha * 255)))
        feather = max(1.0, float(cfg.get("plate_feather", 12.0)) * self.factor)
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
        frame.paste(Image.new("RGB", mask.size, (0, 0, 0)), (x0, y0), mask)

    def annotation(
        self,
        frame: Image.Image,
        text: str,
        accent: Optional[str] = None,
        position: Tuple[float, float] = (0.5, 0.24),
    ) -> Image.Image:
        text = (text or "").strip()
        if not text:
            return frame
        cfg = contract.ANNOTATION
        lines = text.split("\n")
        # Auto-shrink to fit the safe width. Long annotations ("立定跳远世界纪录
        # 3.71 m") used to run off both edges of the frame, unreadable. Same
        # ladder as the subtitle: step the size down until it fits, and only
        # give up after max_steps.
        max_width = frame.size[0] * cfg["max_width"]
        size_key = cfg["font_size"]
        chosen = None
        for _ in range(int(cfg["max_steps"]) + 1):
            stack, size, factor = self._stack(size_key)
            tracking = cfg["tracking"] * factor
            if max(stack.measure(line, tracking) for line in lines) <= max_width:
                chosen = (stack, size, factor, tracking)
                break
            size_key = size_key * cfg["shrink"]
        if chosen is None:
            stack, size, factor = self._stack(size_key)
            tracking = cfg["tracking"] * factor
            chosen = (stack, size, factor, tracking)
        stack, size, factor, tracking = chosen
        colour = {"red": contract.ALERT_RED, "blue": contract.COLD_BLUE}.get(
            accent or "", contract.PAPER
        )
        line_gap = 1.15
        block = size * line_gap * len(lines)
        top = frame.size[1] * position[1] - block / 2.0
        centre_x = frame.size[0] * position[0]
        widest = max(stack.measure(line, tracking) for line in lines)

        self._plate(frame, centre_x, top, widest, block, size, cfg)
        self._shadow(frame, lines, stack, size, tracking, centre_x, top,
                     line_gap, (0, 6 * factor), cfg["shadow_alpha"])
        draw = ImageDraw.Draw(frame)
        stroke = max(1, int(round(cfg["stroke_width"] * factor)))
        y = top
        for line in lines:
            line_width = stack.measure(line, tracking)
            draw_text(draw, (centre_x - line_width / 2.0, y), line, stack,
                      fill=colour, anchor="la", tracking=tracking,
                      stroke_width=stroke, stroke_fill=contract.SUBTITLE_STROKE)
            y += size * line_gap
        return frame
