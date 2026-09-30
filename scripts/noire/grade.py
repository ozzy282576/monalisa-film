"""Colour grading: a filmic tone curve plus creative colour shaping.

Why this is not just ``contrast + saturation``
----------------------------------------------
An earlier version multiplied by a fixed exposure and applied contrast about
0.5.  Measured on the real frames that produced mean luminance 0.306 with the
90th percentile at 0.312 — no highlights at all — which is exactly what "too
dark, too grey" looks like in numbers.  Raising the exposure to compensate then
blew the highlights: several beats clipped at P90 = 1.000.

A fixed curve cannot fix that, because the source panels have wildly different
range (one beat's median sits at 0.066, another's at 0.854).  So the tone stage
is *matched per beat*: each grade declares the tonal targets it wants, and the
curve maps that beat's own black / mid / white onto them.

That is what a colourist does when matching shots — it keeps the mood spread
(a night beat still lands darker than a daylight one) while guaranteeing every
beat has real blacks and real highlights.

Order of operations, and why:

    tone curve  -> S-curve -> film black lift -> split tone -> vibrance -> saturation

Chroma is preserved through the tone stage by applying the same curve to each
channel, which is what film actually does; highlights desaturate slightly as a
result, which is a feature.  Split toning comes last so the tint is not itself
stretched by the curve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np

RGB = Tuple[float, float, float]
LUMA_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

# LUT resolution for the tone curve.
_LUT_SIZE = 256

def _rgb(value: str | Tuple[int, int, int]) -> RGB:
    if isinstance(value, str):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    return tuple(channel / 255.0 for channel in value)  # type: ignore[return-value]

def _monotone_cubic(xs: np.ndarray, ys: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Fritsch-Carlson monotone cubic interpolation.

    Plain cubic splines overshoot, and an overshooting tone curve produces
    bright halos around dark ink lines.  Monotone interpolation cannot.
    """
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    h = np.diff(xs)
    delta = np.diff(ys) / h

    m = np.zeros_like(ys)
    if len(xs) > 2:
        same_sign = np.sign(delta[:-1]) * np.sign(delta[1:]) > 0
        w1 = 2.0 * h[1:] + h[:-1]
        w2 = h[:-1] + 2.0 * h[1:]
        denom = np.where(same_sign, w1 / np.where(delta[:-1] == 0, 1e-12, delta[:-1])
                         + w2 / np.where(delta[1:] == 0, 1e-12, delta[1:]), 1.0)
        harm = np.where(same_sign, 3.0 * (h[:-1] + h[1:]) / np.where(denom == 0, 1e-12, denom), 0.0)
        m[1:-1] = np.where(same_sign, harm, 0.0)
    m[0] = delta[0] if len(delta) else 0.0
    m[-1] = delta[-1] if len(delta) else 0.0

    idx = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    t = np.clip((x - xs[idx]) / np.maximum(h[idx], 1e-12), 0.0, 1.0)
    t2, t3 = t * t, t * t * t
    return (ys[idx] * (2 * t3 - 3 * t2 + 1)
            + m[idx] * h[idx] * (t3 - 2 * t2 + t)
            + ys[idx + 1] * (-2 * t3 + 3 * t2)
            + m[idx + 1] * h[idx] * (t3 - t2))

def source_stats(rgb: np.ndarray) -> Tuple[float, float, float]:
    """Black / mid / white levels (P2, P50, P98) of a frame, as 0..1."""
    luma = (rgb.astype(np.float32) / 255.0) @ LUMA_WEIGHTS
    p2, p50, p98 = np.percentile(luma, [2.0, 50.0, 98.0])
    return float(p2), float(p50), float(p98)

@dataclass(frozen=True)
class Grade:
    """A film look.

    ``mode="enhance"`` runs the filmic chain.  ``mode="duotone"`` is the older
    shadow-to-highlight ink ramp, kept because the monochrome look is still
    selectable per beat; there ``preserve_saturated`` stops painted evidence
    colour (alert red, luminol blue) from being dragged onto the ramp.
    """

    # -- duotone path (legacy monochrome look) --
    shadow: RGB = (0.0, 0.0, 0.0)
    highlight: RGB = (1.0, 1.0, 1.0)
    strength: float = 1.0
    preserve_saturated: bool = True
    saturation_k: float = 4.0
    tint: RGB = (0.0, 0.0, 0.0)
    tint_strength: float = 0.0

    # -- filmic path --
    mode: str = "duotone"
    # Tonal targets the tone curve maps this beat's P2/P50/P98 onto.
    t_black: float = 0.030
    t_mid: float = 0.34
    t_white: float = 0.90
    contrast: float = 1.0        # duotone path only
    s_curve: float = 0.0         # filmic S-curve blend, 0..1 (enhance path)
    black: float = 0.0           # output black lift — film black is never 0
    saturation: float = 1.0
    vibrance: float = 0.0        # lifts muted colour more than saturated colour
    shadow_desat: float = 0.0    # pulls chroma out of the darks, weighted to them
    blue_suppress: float = 0.0   # pulls chroma out of blue/cyan, weighted by blueness
    shadow_tint: RGB = (0.0, 0.0, 0.0)      # additive, weighted to the shadows
    shadow_amount: float = 0.0
    highlight_tint: RGB = (0.0, 0.0, 0.0)   # additive, weighted to the highlights
    highlight_amount: float = 0.0
    bloom: float = 0.0           # highlight glow, applied spatially by the camera

    # -- tone stage ---------------------------------------------------------
    def tone_lut(self, stats: Sequence[float]) -> np.ndarray:
        """256-entry curve mapping this frame's levels onto the grade's targets."""
        p_low, p_mid, p_high = (float(v) for v in stats)
        # Keep the control points strictly ordered whatever the source looks
        # like; a flat or inverted frame must not produce a folded curve.
        eps = 1e-3
        p_low = min(max(p_low, eps), 0.90)
        p_mid = min(max(p_mid, p_low + eps), 0.97)
        p_high = min(max(p_high, p_mid + eps), 0.999)

        xs = np.array([0.0, p_low, p_mid, p_high, 1.0], dtype=np.float64)
        ys = np.array([0.0, self.t_black, self.t_mid, self.t_white, 1.0], dtype=np.float64)
        # Guarantee the targets are themselves monotone.
        ys = np.maximum.accumulate(ys)
        ys = np.minimum(ys, np.array([0.0, 0.30, 0.70, 0.99, 1.0]))

        x = np.linspace(0.0, 1.0, _LUT_SIZE)
        return np.clip(_monotone_cubic(xs, ys, x), 0.0, 1.0).astype(np.float32)

    # -- colour stage -------------------------------------------------------
    def colour_stage(self, frame: np.ndarray) -> np.ndarray:
        """Split tone / contrast / vibrance / saturation on a float 0..255 array."""
        return self._colour(frame.astype(np.float32) / 255.0) * 255.0

    def _colour(self, out: np.ndarray) -> np.ndarray:
        """Split tone, vibrance and saturation. Input/output float 0..1."""
        luma = out @ LUMA_WEIGHTS

        # Strip chroma out of the darks before tinting. A painted panel can
        # carry a heavy cast in its shadows — the closing card came back with a
        # navy background where the script calls for black — and no amount of
        # additive tint removes it, because the colour is already there. This
        # is the qualifier a colourist would reach for: desaturate the low end.
        if self.shadow_desat > 0.0:
            weight = (1.0 - luma) ** 2 * self.shadow_desat
            out = luma[..., None] + (out - luma[..., None]) * (1.0 - weight)[..., None]
            luma = out @ LUMA_WEIGHTS

        # Teal into the shadows, warm into the highlights, weighted quadratically
        # so the tint stays out of the midtones. A flat tint instead — which is
        # what this used to do — just washes the whole frame and reads grey.
        if self.shadow_amount > 0.0:
            weight = (1.0 - luma) ** 2
            out = out + np.array(self.shadow_tint, dtype=np.float32) * (
                self.shadow_amount * weight)[..., None]
        if self.highlight_amount > 0.0:
            weight = luma ** 2
            out = out + np.array(self.highlight_tint, dtype=np.float32) * (
                self.highlight_amount * weight)[..., None]

        # Contrast as a smoothstep S-curve rather than a straight multiply.
        # A linear contrast pivots and then hard-clips at 1.0, which is what
        # blew 9% of a bright beat to flat white; smoothstep flattens towards
        # both ends instead, so highlights keep their shape.
        if self.s_curve > 0.0:
            smooth = out * out * (3.0 - 2.0 * out)
            out = out + (smooth - out) * self.s_curve

        if self.black > 0.0:
            out = self.black + out * (1.0 - self.black)

        out = np.clip(out, 0.0, 1.0)

        # Blue suppression. Measured on the source plates, 65% of the coloured
        # pixels are blue or cyan and 47% sit above 0.6 saturation — these were
        # painted as blue posters, and then saturation was *added* on top, which
        # is why the result read as flat poster art rather than as film. Pulling
        # chroma out of blue specifically, weighted by how blue each pixel is,
        # is what restores the warm/cool contrast the eye reads as cinematic.
        if self.blue_suppress > 0.0:
            luma = out @ LUMA_WEIGHTS
            red, green, blue = out[..., 0], out[..., 1], out[..., 2]
            chroma_full = out.max(axis=2) - out.min(axis=2)
            blueness = np.clip((blue - np.maximum(red, green))
                               / np.maximum(chroma_full, 1e-4), 0.0, 1.0)
            saturation_here = chroma_full / np.maximum(out.max(axis=2), 1e-4)
            apply = self.blue_suppress * blueness * np.clip(saturation_here * 1.5, 0.0, 1.0)
            out = luma[..., None] + (out - luma[..., None]) * (1.0 - apply)[..., None]
            out = np.clip(out, 0.0, 1.0)

        # Vibrance before saturation: it lifts muted colour and leaves colour
        # that is already strong alone, so skin and the evidence reds do not go
        # neon while the rain still gains some blue.
        luma = out @ LUMA_WEIGHTS
        chroma = out - luma[..., None]
        if self.vibrance > 0.0:
            high = out.max(axis=2)
            low = out.min(axis=2)
            sat = np.where(high > 1e-4, (high - low) / np.maximum(high, 1e-4), 0.0)
            out = luma[..., None] + chroma * (1.0 + self.vibrance * (1.0 - sat))[..., None]
            luma = out @ LUMA_WEIGHTS
            chroma = out - luma[..., None]
        if self.saturation != 1.0:
            out = luma[..., None] + chroma * self.saturation

        return np.clip(out, 0.0, 1.0)

    # -- entry points -------------------------------------------------------
    def apply_float(self, frame: np.ndarray, stats: Sequence[float] | None = None) -> np.ndarray:
        """Grade a float RGB array in 0..255; returns float 0..255."""
        source = frame.astype(np.float32) / 255.0
        if self.mode == "enhance":
            lut = self.tone_lut(stats if stats is not None else source_stats(frame))
            out = np.interp(source, np.linspace(0.0, 1.0, _LUT_SIZE), lut).astype(np.float32)
            return self._colour(out) * 255.0
        return self._duotone(source) * 255.0

    def apply(self, frame: np.ndarray, stats: Sequence[float] | None = None) -> np.ndarray:
        """``frame`` is uint8 (H, W, 3); returns uint8."""
        return np.clip(self.apply_float(frame, stats) + 0.5, 0, 255).astype(np.uint8)

    def _duotone(self, source: np.ndarray) -> np.ndarray:
        """Legacy ink ramp: tint luminance, let painted colour pass through."""
        luma = source @ LUMA_WEIGHTS
        if self.contrast != 1.0:
            luma = np.clip((luma - 0.5) * self.contrast + 0.5, 0.0, 1.0)

        shadow = np.array(self.shadow, dtype=np.float32)
        highlight = np.array(self.highlight, dtype=np.float32)
        graded = shadow[None, None, :] + (highlight - shadow)[None, None, :] * luma[..., None]
        mixed = source + (graded - source) * self.strength

        if self.preserve_saturated:
            high = source.max(axis=2)
            low = source.min(axis=2)
            saturation = np.where(high > 1e-4, (high - low) / np.maximum(high, 1e-4), 0.0)
            keep = np.clip(saturation * self.saturation_k, 0.0, 1.0)[..., None]
            mixed = mixed * (1.0 - keep) + source * keep

        return np.clip(mixed, 0.0, 1.0)

# Colour script: applied over natively painted frames.
#
# ``t_mid`` is the tonal target for each mood's median — this is what fixes the
# "too dark" complaint, and it is per-grade so a night beat still lands darker
# than the courtroom. ``t_white`` stays under 1.0 so rain streaks and windows
# never clip to flat white.
COLOUR_GRADES = {
    "c_night": Grade(
        mode="enhance", t_black=0.052, t_mid=0.430, t_white=0.905,
        s_curve=0.44, black=0.010,
        vibrance=0.18, shadow_desat=0.2, blue_suppress=0.52, saturation=0.94,
        shadow_tint=(0.012, 0.058, 0.128), shadow_amount=1.0,
        highlight_tint=(0.120, 0.048, -0.029), highlight_amount=1.0,
        bloom=0.40),

    "c_rain": Grade(
        mode="enhance", t_black=0.050, t_mid=0.440, t_white=0.908,
        s_curve=0.43, black=0.010,
        vibrance=0.18, shadow_desat=0.18, blue_suppress=0.48, saturation=0.95,
        shadow_tint=(0.010, 0.050, 0.116), shadow_amount=1.0,
        highlight_tint=(0.099, 0.042, -0.019), highlight_amount=1.0,
        bloom=0.35),

    "c_amber": Grade(
        mode="enhance", t_black=0.055, t_mid=0.465, t_white=0.912,
        s_curve=0.41, black=0.012,
        vibrance=0.2, shadow_desat=0.14, blue_suppress=0.34, saturation=0.98,
        shadow_tint=(0.042, 0.021, 0.063), shadow_amount=1.0,
        highlight_tint=(0.136, 0.064, -0.042), highlight_amount=1.0,
        bloom=0.35),

    "c_cold": Grade(
        mode="enhance", t_black=0.052, t_mid=0.445, t_white=0.910,
        s_curve=0.43, black=0.010,
        vibrance=0.18, shadow_desat=0.18, blue_suppress=0.44, saturation=0.96,
        shadow_tint=(0.008, 0.040, 0.130), shadow_amount=1.0,
        highlight_tint=(0.072, 0.063, 0.000), highlight_amount=1.0,
        bloom=0.30),

    "c_warm": Grade(
        mode="enhance", t_black=0.060, t_mid=0.500, t_white=0.922,
        s_curve=0.39, black=0.012,
        vibrance=0.22, shadow_desat=0.1, blue_suppress=0.16, saturation=1.0,
        shadow_tint=(0.033, 0.015, 0.048), shadow_amount=1.0,
        highlight_tint=(0.128, 0.072, -0.035), highlight_amount=1.0,
        bloom=0.38),

    # The closing card is meant to be a black void with a spotlight. Every
    # other grade lifts the shadows and cools them, which turned that black a
    # flat navy. Here the shadow tint runs *negative* on blue instead, which
    # cancels the cast in the darks without touching the lit pool.
    "c_soft": Grade(
        mode="enhance", t_black=0.045, t_mid=0.440, t_white=0.912,
        s_curve=0.30, black=0.010,
        vibrance=0.16, shadow_desat=0.16, blue_suppress=0.42, saturation=0.96,
        shadow_tint=(0.006, 0.014, 0.040), shadow_amount=1.0,
        highlight_tint=(0.026, 0.012, -0.006), highlight_amount=1.0,
        bloom=0.20),

    "c_void": Grade(
        mode="enhance", t_black=0.004, t_mid=0.330, t_white=0.925,
        s_curve=0.30, black=0.0,
        vibrance=0.16, blue_suppress=0.3, saturation=0.94, shadow_desat=0.45,
        shadow_tint=(0.000, 0.004, 0.014), shadow_amount=1.0,
        highlight_tint=(0.028, 0.012, -0.008), highlight_amount=1.0,
        bloom=0.38),

    "c_flat": Grade(
        mode="enhance", t_black=0.055, t_mid=0.460, t_white=0.905,
        s_curve=0.32, black=0.010,
        vibrance=0.14, shadow_desat=0.14, blue_suppress=0.34, saturation=0.95,
        shadow_tint=(0.004, 0.010, 0.032), shadow_amount=1.0,
        highlight_tint=(0.010, 0.006, 0.000), highlight_amount=1.0,
        bloom=0.14),

}

# Duotone grades: the earlier monochrome ink look, still selectable per beat.
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

# Per-beat colour script. Frames are painted in colour, so these keep the
# palette coherent across 23 beats.
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
    "12": "c_soft",   # 4 米标记
    "13": "c_amber",   # 黑板演算
    "14": "c_soft",   # 抛物线
    "15": "c_amber",   # 数值定格
    "16": "c_soft",    # 数据图表
    "17": "c_cold",    # 回头锁定
    "18": "c_amber",   # 甩出窗外
    "19": "c_rain",    # 闪电抓捕
    "20": "c_cold",    # 鲁米诺
    "21": "c_warm",    # 法庭
    "22": "c_warm",    # 雨停，阳光
    "23": "c_void",    # 互动结尾，全黑需保持全黑
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
