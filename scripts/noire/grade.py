"""Zero-cost colour grading for ink artwork.

Re-generating 23 frames in colour costs 23 more image generations.  Grading the
existing black-and-white frames costs nothing and is a legitimate look in its own
right: the ink skeleton is untouched, and colour is applied as a *duotone ramp*
from a shadow colour to a highlight colour — the same mechanism as a hand-tinted
press photo or a two-plate risograph.

Luminance is preserved as the ramp position, so contrast and linework survive
exactly; only the hue changes.  Because the evidence colours (alert red, cold
blue) are drawn *on top* of the graded frame at render time, they keep their full
saturation against the graded background.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

RGB = Tuple[float, float, float]


def _rgb(value: str | Tuple[int, int, int]) -> RGB:
    if isinstance(value, str):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    return tuple(channel / 255.0 for channel in value)  # type: ignore[return-value]


@dataclass(frozen=True)
class Grade:
    """A duotone ramp plus a saturation nudge."""

    shadow: RGB
    highlight: RGB
    strength: float = 1.0
    contrast: float = 1.0

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """``frame`` is uint8 (H, W, 3); returns uint8."""
        source = frame.astype(np.float32) / 255.0

        # Rec.709 luma keeps the ink linework's perceived brightness
        luma = source @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        if self.contrast != 1.0:
            luma = np.clip((luma - 0.5) * self.contrast + 0.5, 0.0, 1.0)

        shadow = np.array(self.shadow, dtype=np.float32)
        highlight = np.array(self.highlight, dtype=np.float32)
        # ramp: shadow colour at luma 0, highlight colour at luma 1
        graded = shadow[None, None, :] + (highlight - shadow)[None, None, :] * luma[..., None]

        mixed = source + (graded - source) * self.strength
        return np.clip(mixed * 255.0 + 0.5, 0, 255).astype(np.uint8)


# Curated grades. Each keeps deep blacks genuinely dark so the noir reads.
GRADES = {
    "none": None,

    # rain-soaked night: cold slate shadows, moonlit highlights
    "night": Grade(shadow=_rgb("#0A1016"), highlight=_rgb("#DDE7EC"),
                   strength=0.85, contrast=1.06),

    # interrogation / corridor: sickly sodium light
    "amber": Grade(shadow=_rgb("#140D06"), highlight=_rgb("#F2E0BC"),
                   strength=0.85, contrast=1.04),

    # flashback, memory, courtroom: bleached and burnt
    "bleach": Grade(shadow=_rgb("#16110C"), highlight=_rgb("#EFE6D6"),
                    strength=0.6, contrast=1.12),

    # deep cold — luminol, the puddle, the detective's stare
    "cold": Grade(shadow=_rgb("#060D16"), highlight=_rgb("#CFE2F0"),
                  strength=0.9, contrast=1.08),

    # the verdict: heavy, oppressive, almost monochrome
    "iron": Grade(shadow=_rgb("#0B0B0D"), highlight=_rgb("#D9D6D2"),
                  strength=0.75, contrast=1.15),
}

# Beats default to the mood the script asked for; override per-beat with "grade".
DEFAULT_GRADE_BY_BEAT = {
    "01": "night", "02": "night", "03": "amber", "04": "cold", "05": "night",
    "06": "bleach", "07": "cold", "08": "amber", "09": "cold", "10": "night",
    "11": "night", "12": "night", "13": "amber", "14": "night", "15": "amber",
    "16": "bleach", "17": "night", "18": "amber", "19": "night", "20": "cold",
    "21": "iron", "22": "bleach", "23": "iron",
}


def resolve(name: str | None, beat_id: str) -> Grade | None:
    key = name or DEFAULT_GRADE_BY_BEAT.get(beat_id, "none")
    if key in (None, "", "none"):
        return None
    if key not in GRADES:
        raise ValueError(f"unknown grade: {key}")
    return GRADES[key]
