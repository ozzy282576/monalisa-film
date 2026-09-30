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
    """A duotone ramp plus saturation passthrough.

    ``preserve_saturated`` keeps anything already colourful — the alert red on a
    4 m marker, the cold blue of luminol — from being dragged onto the ramp and
    turned navy.  The grade tints the *ink*; painted evidence colour survives.
    """

    shadow: RGB
    highlight: RGB
    strength: float = 1.0
    contrast: float = 1.0
    preserve_saturated: bool = True
    saturation_k: float = 4.0   # >25% saturation passes through untouched
    mode: str = "duotone"       # "duotone" tints ink; "enhance" grades colour art
    saturation: float = 1.0
    tint: RGB = (0.0, 0.0, 0.0)
    tint_strength: float = 0.0

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """``frame`` is uint8 (H, W, 3); returns uint8."""
        source = frame.astype(np.float32) / 255.0

        if self.mode == "enhance":
            return self._enhance(source)

        # Rec.709 luma keeps the ink linework's perceived brightness
        luma = source @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        if self.contrast != 1.0:
            luma = np.clip((luma - 0.5) * self.contrast + 0.5, 0.0, 1.0)

        shadow = np.array(self.shadow, dtype=np.float32)
        highlight = np.array(self.highlight, dtype=np.float32)
        # ramp: shadow colour at luma 0, highlight colour at luma 1
        graded = shadow[None, None, :] + (highlight - shadow)[None, None, :] * luma[..., None]

        mixed = source + (graded - source) * self.strength

        if self.preserve_saturated:
            high = source.max(axis=2)
            low = source.min(axis=2)
            saturation = np.where(high > 1e-4, (high - low) / np.maximum(high, 1e-4), 0.0)
            keep = np.clip(saturation * self.saturation_k, 0.0, 1.0)[..., None]
            mixed = mixed * (1.0 - keep) + source * keep

        return np.clip(mixed * 255.0 + 0.5, 0, 255).astype(np.uint8)

    def _enhance(self, source: np.ndarray) -> np.ndarray:
        """Grade already-coloured artwork: contrast, saturation, mood cast.

        Used once the frames are painted in colour.  Kept gentle on purpose —
        the artwork carries the palette, this only shapes it.
        """
        out = source
        if self.contrast != 1.0:
            out = np.clip((out - 0.5) * self.contrast + 0.5, 0.0, 1.0)
        if self.saturation != 1.0:
            luma = out @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
            out = np.clip(luma[..., None] + (out - luma[..., None]) * self.saturation,
                          0.0, 1.0)
        if self.tint_strength > 0.0:
            tint = np.array(self.tint, dtype=np.float32)
            out = out * (1.0 - self.tint_strength) + tint * self.tint_strength
        return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


# Colour grades: applied over natively painted frames.
COLOUR_GRADES = {
    # mood               contrast  saturation  tint
    "c_night":  Grade((0, 0, 0), (1, 1, 1), mode="enhance", contrast=1.07,
                      saturation=1.16, tint=(0.42, 0.53, 0.70), tint_strength=0.055),
    "c_rain":   Grade((0, 0, 0), (1, 1, 1), mode="enhance", contrast=1.05,
                      saturation=1.20, tint=(0.46, 0.56, 0.68), tint_strength=0.045),
    "c_amber":  Grade((0, 0, 0), (1, 1, 1), mode="enhance", contrast=1.06,
                      saturation=1.14, tint=(0.72, 0.56, 0.36), tint_strength=0.070),
    "c_cold":   Grade((0, 0, 0), (1, 1, 1), mode="enhance", contrast=1.08,
                      saturation=1.10, tint=(0.38, 0.56, 0.78), tint_strength=0.075),
    "c_warm":   Grade((0, 0, 0), (1, 1, 1), mode="enhance", contrast=1.05,
                      saturation=1.12, tint=(0.80, 0.62, 0.40), tint_strength=0.060),
    "c_flat":   Grade((0, 0, 0), (1, 1, 1), mode="enhance", contrast=1.04,
                      saturation=1.06),
}

# Duotone grades: applied over pure black-and-white ink frames.
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

# Per-beat colour script. Frames are painted in colour, so these are light
# grading passes that keep the palette coherent across 23 beats.
DEFAULT_GRADE_BY_BEAT = {
    "01": "c_night",   # 暴雨夜，孤楼
    "02": "c_rain",    # 警戒线，警灯
    "03": "c_amber",   # 丈夫，昏黄室内
    "04": "c_cold",    # 窗台积水
    "05": "c_amber",   # 倒地椅子，窗光
    "06": "c_flat",    # 对比构图，中性
    "07": "c_cold",    # 刑警蹲查
    "08": "c_amber",   # 卷尺
    "09": "c_cold",    # 刑警的眼睛
    "10": "c_night",   # 水袋放窗台
    "11": "c_night",   # 垂直落在墙根
    "12": "c_night",   # 4 米标记
    "13": "c_amber",   # 黑板演算
    "14": "c_night",   # 抛物线
    "15": "c_amber",   # 数值定格
    "16": "c_flat",    # 数据图表
    "17": "c_cold",    # 回头锁定
    "18": "c_amber",   # 甩出窗外
    "19": "c_rain",    # 闪电抓捕
    "20": "c_cold",    # 鲁米诺
    "21": "c_warm",    # 法庭
    "22": "c_warm",    # 雨停，阳光
    "23": "c_flat",    # 互动结尾
}

MONOCHROME_BEATS: tuple = ()


ALL_GRADES = {**COLOUR_GRADES, **GRADES}


def resolve(name: str | None, beat_id: str) -> Grade | None:
    key = name or DEFAULT_GRADE_BY_BEAT.get(beat_id, "none")
    if key in (None, "", "none"):
        return None
    if key not in ALL_GRADES:
        raise ValueError(f"unknown grade: {key}")
    return ALL_GRADES[key]
