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
# Tuning history, because these numbers are not arbitrary.  Three complaints
# drove them, in order:
#
#   1. "too dark" - fixed contrast about 0.5 plus a 0.42 vignette crushed the
#      frame to mean 0.31 / P90 0.31. No highlights, hence no depth.
#   2. "still too dark" - the fix raised t_mid and t_white, but ALSO lifted
#      t_black to ~0.05 and dropped saturation to 0.94. Lifting the black point
#      removes contrast, and low contrast in the midtones is what the eye
#      reports as grey.
#   3. "too dark, too grey, want it more cinematic" - this set.
#
# So these aim at film contrast rather than at raw brightness: blacks stay deep
# and clean, midtones sit high, highlights stay bright, S-curve is strong. A
# frame can be dark and still not look muddy - what looks muddy is the darks
# being lifted AND tinted AND desaturated at once, which is what pass 2 did.
#
# Per mood:
#   t_black  deep, near-zero - film black is black, not charcoal
#   t_mid    high, so the picture reads bright despite dark subject matter
#   t_white  just under 1.0, so rain and windows glow without clipping flat
#   s_curve  strong, buying contrast back without re-crushing the midtones
#   blue_suppress  tames the blue these plates were painted in, which is what
#                  restores the warm/cool split the eye reads as cinematic
COLOUR_GRADES = {
    # 01 11 12 14 - rain-soaked night
    "c_night": Grade(
        mode="enhance", t_black=0.014, t_mid=0.455, t_white=0.952,
        s_curve=0.54, black=0.004,
        vibrance=0.24, shadow_desat=0.26, blue_suppress=0.54, saturation=1.09,
        shadow_tint=(0.010, 0.044, 0.104), shadow_amount=1.0,
        highlight_tint=(0.150, 0.058, -0.042), highlight_amount=1.0,
        bloom=0.42),

    # 02 19 - cordon, police strobes
    "c_rain": Grade(
        mode="enhance", t_black=0.014, t_mid=0.465, t_white=0.955,
        s_curve=0.53, black=0.004,
        vibrance=0.24, shadow_desat=0.24, blue_suppress=0.50, saturation=1.09,
        shadow_tint=(0.010, 0.040, 0.098), shadow_amount=1.0,
        highlight_tint=(0.136, 0.056, -0.034), highlight_amount=1.0,
        bloom=0.38),

    # 03 05 08 13 15 18 - sodium-lit interiors
    "c_amber": Grade(
        mode="enhance", t_black=0.016, t_mid=0.490, t_white=0.958,
        s_curve=0.51, black=0.005,
        vibrance=0.22, shadow_desat=0.16, blue_suppress=0.30, saturation=1.09,
        shadow_tint=(0.036, 0.018, 0.054), shadow_amount=1.0,
        highlight_tint=(0.118, 0.056, -0.036), highlight_amount=1.0,
        bloom=0.38),

    # 04 07 09 17 20 - cold blue
    "c_cold": Grade(
        mode="enhance", t_black=0.014, t_mid=0.470, t_white=0.955,
        s_curve=0.53, black=0.004,
        vibrance=0.24, shadow_desat=0.26, blue_suppress=0.52, saturation=1.08,
        shadow_tint=(0.008, 0.034, 0.104), shadow_amount=1.0,
        highlight_tint=(0.104, 0.066, -0.014), highlight_amount=1.0,
        bloom=0.32),

    # 21 22 - courtroom and sunrise
    "c_warm": Grade(
        mode="enhance", t_black=0.022, t_mid=0.520, t_white=0.965,
        s_curve=0.48, black=0.006,
        vibrance=0.22, shadow_desat=0.12, blue_suppress=0.18, saturation=1.08,
        shadow_tint=(0.030, 0.014, 0.044), shadow_amount=1.0,
        highlight_tint=(0.112, 0.062, -0.030), highlight_amount=1.0,
        bloom=0.40),

    # 06 16 - neutral comparison / forensic chart; less drama on purpose
    "c_flat": Grade(
        mode="enhance", t_black=0.020, t_mid=0.480, t_white=0.946,
        s_curve=0.38, black=0.005,
        vibrance=0.16, shadow_desat=0.16, blue_suppress=0.34, saturation=1.04,
        shadow_tint=(0.006, 0.014, 0.038), shadow_amount=1.0,
        highlight_tint=(0.030, 0.014, -0.008), highlight_amount=1.0,
        bloom=0.20),

    # 23 - closing black card. Spotlight bright, surround must stay true black.
    "c_void": Grade(
        mode="enhance", t_black=0.002, t_mid=0.380, t_white=0.985,
        s_curve=0.46, black=0.0,
        vibrance=0.18, blue_suppress=0.24, saturation=1.02, shadow_desat=0.55,
        shadow_tint=(0.000, 0.004, 0.012), shadow_amount=1.0,
        highlight_tint=(0.030, 0.013, -0.008), highlight_amount=1.0,
        bloom=0.42),
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
