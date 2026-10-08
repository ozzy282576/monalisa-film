"""Audit the colour of a beat's source artwork.

Mean saturation is the wrong test: a blue-washed monochrome panel scores as
"saturated" as a painted one. Hue spread is also wrong — a deliberate colour
script (an all-indigo night scene) is legitimately full colour and gets flagged.

The measure that actually matches the eye is simply *how much of the frame is
coloured at all*: the fraction of pixels that clear a modest saturation floor.
Artwork that was never colourised sits at exactly 0% — the ink pipeline emitted
R=G=B — while painted panels clear several percent even when they are moody and
dark. Anything under ``MIN_COLOURED_FRACTION`` still reads as black-and-white.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image

# A pixel counts as "coloured" when it clears this saturation floor with enough
# brightness to be visible. Both values were calibrated against frames judged by
# eye: every painted panel cleared 5%, every never-colourised panel sat at 0%.
_MIN_SAT = 0.20
_MIN_VALUE = 0.15
# Below this share of coloured pixels the frame still reads as black-and-white.
MIN_COLOURED_FRACTION = 0.05


def colour_stats(path: Path) -> Tuple[float, float]:
    """Return ``(coloured_fraction, mean_saturation)``."""
    hsv = np.asarray(Image.open(path).convert("HSV"), dtype=np.float32) / 255.0
    sat, val = hsv[..., 1], hsv[..., 2]
    coloured = float(((sat >= _MIN_SAT) & (val >= _MIN_VALUE)).mean())
    return coloured, float(sat.mean())


def audit(project_dir: Path, beat_ids: List[str]) -> Tuple[List[str], List[str]]:
    image_dir = project_dir / "images"
    coloured: List[str] = []
    monochrome: List[str] = []
    print(f"{'beat':<6}{'coloured':>10}{'mean sat':>10}   verdict")
    for beat_id in beat_ids:
        path = image_dir / f"{beat_id}.png"
        if not path.exists():
            print(f"{beat_id:<6}{'-':>10}{'-':>10}   MISSING")
            monochrome.append(beat_id)
            continue
        coloured_frac, sat = colour_stats(path)
        is_mono = coloured_frac < MIN_COLOURED_FRACTION
        (monochrome if is_mono else coloured).append(beat_id)
        verdict = "monochrome  <-- still needs painting" if is_mono else "colour"
        print(f"{beat_id:<6}{coloured_frac:>9.2%}{sat:>10.3f}   {verdict}")
    return coloured, monochrome


def main(argv: List[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", default="examples/douyin-physics")
    parser.add_argument("--beats", default="01-23")
    args = parser.parse_args(argv)

    project_dir = Path(args.project)
    if not project_dir.is_absolute():
        project_dir = repo / project_dir

    if "-" in args.beats and "," not in args.beats:
        lo, hi = args.beats.split("-")
        beat_ids = [f"{i:02d}" for i in range(int(lo), int(hi) + 1)]
    else:
        beat_ids = [b.strip() for b in args.beats.split(",") if b.strip()]

    coloured, monochrome = audit(project_dir, beat_ids)
    print(f"\ncoloured: {len(coloured)}/{len(beat_ids)}")
    if monochrome:
        print("still monochrome: " + ", ".join(monochrome))
    return 0


if __name__ == "__main__":
    sys.exit(main())
