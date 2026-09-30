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
    bloom_threshold: float = 0.72   # only genuinely bright pixels may glow

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
        lut = np.clip(_monotone_cubic(xs, ys, x), 0.0, 1.0)

        # The S-curve and the black lift are both pointwise, so they fold into
        # this same table. Applying them as separate full-frame passes cost five
        # extra sweeps over 1.5M pixels per frame for an identical result.
        if self.s_curve > 0.0:
            smooth = lut * lut * (3.0 - 2.0 * lut)
            lut = lut + (smooth - lut) * self.s_curve
        if self.black > 0.0:
            lut = self.black + lut * (1.0 - self.black)

        return np.clip(lut, 0.0, 1.0).astype(np.float32)

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
        # One pass, one chroma split. ``chroma_max`` is the raw peak-minus-trough
        # spread, which orders muted and vivid colour the same way the true HSV
        # saturation does but without the per-pixel divide the earlier version
        # paid for — that divide alone was a quarter of the frame's render time.
        luma = out @ LUMA_WEIGHTS
        chroma = out - luma[..., None]
        if self.vibrance > 0.0:
            # Pairwise maximum/minimum rather than ``chroma.max(axis=2)``.
            # Reducing the trailing axis of an (H, W, 3) array sends numpy
            # through generic reduction machinery and cost 21 ms per frame;
            # two chained elementwise ops on contiguous planes cost 0.9 ms for
            # exactly the same numbers.
            r, gg, b = out[..., 0], out[..., 1], out[..., 2]
            spread = (np.maximum(np.maximum(r, gg), b)
                      - np.minimum(np.minimum(r, gg), b))
            gain = np.clip(1.0 + self.vibrance * (1.0 - spread * 3.0), 1.0, 1.0 + self.vibrance)
            chroma = chroma * gain[..., None]
        if self.saturation != 1.0:
            chroma = chroma * self.saturation

        return np.clip(luma[..., None] + chroma, 0.0, 1.0)

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
# These used to carry ``blue_suppress`` ~0.5 and ``shadow_desat`` ~0.26, added to
# tame a cyan cast in the painted plates. Measured against the artwork, that was
# the wrong trade: the plates arrive with mean saturation 0.50-0.64 and the grade
# was handing back 0.45 — the correction for the cast *was* the grey. Both now
# stay at zero and the cast is handled as a split tone instead, which rebalances
# the colour rather than removing it.
#
# Exposure is the other half. The painted plates are dark (mean luminance
# 0.20-0.23, median as low as 0.085), so the tone curve has real work to do;
# ``t_mid`` is the target for each beat's median and sits near 0.55 for night
# beats — a normal film exposure, not a lift.
COLOUR_GRADES = {
    # 01 11 12 14 — rain-soaked night
    "c_night": Grade(
        mode="enhance", t_black=0.034, t_mid=0.600, t_white=0.918,
        s_curve=0.46, black=0.010,
        vibrance=0.40, saturation=1.22,
        shadow_tint=(0.000, 0.038, 0.092), shadow_amount=1.0,
        highlight_tint=(0.120, 0.050, -0.030), highlight_amount=1.0,
        bloom=0.34, bloom_threshold=0.80),

    # 02 19 — cordon, police strobes
    "c_rain": Grade(
        mode="enhance", t_black=0.036, t_mid=0.610, t_white=0.925,
        s_curve=0.45, black=0.010,
        vibrance=0.40, saturation=1.21,
        shadow_tint=(0.000, 0.034, 0.086), shadow_amount=1.0,
        highlight_tint=(0.110, 0.048, -0.026), highlight_amount=1.0,
        bloom=0.32, bloom_threshold=0.78),

    # 03 05 08 13 15 18 — sodium-lit interiors
    "c_amber": Grade(
        mode="enhance", t_black=0.038, t_mid=0.630, t_white=0.935,
        s_curve=0.44, black=0.012,
        vibrance=0.38, saturation=1.20,
        shadow_tint=(0.026, 0.014, 0.044), shadow_amount=1.0,
        highlight_tint=(0.100, 0.046, -0.026), highlight_amount=1.0,
        bloom=0.32, bloom_threshold=0.78),

    # 04 07 09 17 20 — cold blue
    "c_cold": Grade(
        mode="enhance", t_black=0.036, t_mid=0.615, t_white=0.928,
        s_curve=0.45, black=0.010,
        vibrance=0.40, saturation=1.20,
        shadow_tint=(0.000, 0.030, 0.090), shadow_amount=1.0,
        highlight_tint=(0.088, 0.052, -0.014), highlight_amount=1.0,
        bloom=0.32, bloom_threshold=0.76),

    # 21 22 — courtroom and sunrise
    "c_warm": Grade(
        mode="enhance", t_black=0.044, t_mid=0.660, t_white=0.950,
        s_curve=0.42, black=0.014,
        vibrance=0.36, saturation=1.18,
        shadow_tint=(0.022, 0.012, 0.036), shadow_amount=1.0,
        highlight_tint=(0.092, 0.048, -0.024), highlight_amount=1.0,
        bloom=0.42, bloom_threshold=0.74),

    # 06 16 — neutral comparison / forensic chart; less drama on purpose
    "c_flat": Grade(
        mode="enhance", t_black=0.046, t_mid=0.635, t_white=0.940,
        s_curve=0.36, black=0.014,
        vibrance=0.28, saturation=1.12,
        shadow_tint=(0.006, 0.012, 0.032), shadow_amount=1.0,
        highlight_tint=(0.040, 0.020, -0.008), highlight_amount=1.0,
        bloom=0.22, bloom_threshold=0.80),

    # 23 — closing black card. Spotlight bright, surround must stay true black.
    "c_void": Grade(
        mode="enhance", t_black=0.004, t_mid=0.510, t_white=0.965,
        s_curve=0.44, black=0.0,
        vibrance=0.24, saturation=1.10, shadow_desat=0.45,
        shadow_tint=(0.000, 0.004, 0.012), shadow_amount=1.0,
        highlight_tint=(0.030, 0.013, -0.008), highlight_amount=1.0,
        bloom=0.46, bloom_threshold=0.70),
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
    "12": "c_night",  # 4 米标记
    "13": "c_amber",   # 黑板演算
    "14": "c_night",  # 抛物线
    "15": "c_amber",   # 数值定格
    "16": "c_flat",   # 数据图表
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
