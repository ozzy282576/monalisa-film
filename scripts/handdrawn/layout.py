"""Caption / illustration separation for composite pages.

Direct port of ``analyzeCompositeLayout`` from ``scripts/page-assets.mjs``.  The
upstream version shells out to ffmpeg to get a 256px grayscale preview; this port
uses Pillow so the detection runs with no external processes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image

from . import contract


@dataclass(frozen=True)
class CompositeLayout:
    has_caption: bool
    split_y: int
    caption_y: int
    caption_h: int
    width: int
    height: int


def _preview_gray(image: Image.Image, width: int = contract.LAYOUT_PREVIEW_WIDTH) -> np.ndarray:
    height = max(2, int(round(image.height * width / image.width / 2.0)) * 2)
    resized = image.convert("L").resize((width, height), Image.BOX)
    return np.asarray(resized, dtype=np.float32)


def analyze_composite(image: Image.Image) -> CompositeLayout:
    width, height = image.size
    gray = _preview_gray(image)
    preview_h, preview_w = gray.shape

    ink = (gray < contract.LAYOUT_INK_THRESHOLD).astype(np.float32).mean(axis=1)

    padded = np.pad(ink, 2, mode="edge")
    smoothed = np.convolve(padded, np.ones(5, dtype=np.float32) / 5.0, mode="valid")
    smoothed = smoothed[:preview_h]

    search_start = int(round(preview_h * contract.LAYOUT_SEARCH[0]))
    search_end = int(round(preview_h * contract.LAYOUT_SEARCH[1]))

    runs: List[tuple] = []
    run_start = None
    for y in range(search_start, search_end + 1):
        quiet = smoothed[y] < contract.LAYOUT_INK_RATIO
        if quiet and run_start is None:
            run_start = y
        closes = (not quiet) or y == search_end
        if closes and run_start is not None:
            end = y - 1 if not quiet else y
            runs.append((run_start, end, end - run_start + 1))
            run_start = None
    runs.sort(key=lambda item: (-item[2], item[0]))
    best = runs[0] if runs else None

    if best:
        split_preview = int(round((best[0] + best[1]) / 2.0))
    else:
        window = smoothed[search_start:search_end + 1]
        split_preview = search_start + int(np.argmin(window))

    split_preview = max(search_start, min(int(round(preview_h * contract.LAYOUT_MAX_SPLIT)), split_preview))

    content_rows = [y for y in range(split_preview) if ink[y] > contract.LAYOUT_INK_RATIO]
    scale_y = height / preview_h
    detected = (
        len(content_rows) > max(4, preview_h * 0.02)
        and best is not None
        and best[2] >= preview_h * 0.012
    )
    top_content = content_rows[0] if content_rows else 0
    bottom_content = content_rows[-1] if content_rows else split_preview
    padding = max(8, int(round(preview_h * contract.LAYOUT_PADDING_RATIO)))

    caption_y = max(0, int(round((top_content - padding) * scale_y)))
    caption_bottom = min(height, int(round((bottom_content + padding) * scale_y)))

    return CompositeLayout(
        has_caption=bool(detected),
        split_y=int(round(split_preview * scale_y)),
        caption_y=caption_y,
        caption_h=max(24, caption_bottom - caption_y),
        width=width,
        height=height,
    )


def analyze_file(path: Path) -> CompositeLayout:
    with Image.open(path) as handle:
        return analyze_composite(handle.convert("RGB"))
