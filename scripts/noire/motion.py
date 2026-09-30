"""Ken-Burns camera moves over still frames.

Each scene's artwork is up-scaled once to ``max_scale``; every frame is then a
``Image.resize(..., box=...)`` call, which crops and resamples in a single pass.
That keeps a 3600-frame 1080x1920 render comfortably inside a couple of minutes
without ever touching a per-pixel Python loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image, ImageFilter

from . import contract
from . import grade as grade_module

# Pre-generated grain tiles: cheaper and more stable than fresh noise per frame.
_GRAIN_TILES = 8


def cover_resize(image: Image.Image, width: int, height: int) -> Image.Image:
    """CSS ``object-fit: cover`` — fill the frame, crop the overflow."""
    source_w, source_h = image.size
    scale = max(width / source_w, height / source_h)
    target = (max(1, int(round(source_w * scale))), max(1, int(round(source_h * scale))))
    resized = image.resize(target, Image.LANCZOS)
    left = (target[0] - width) // 2
    top = (target[1] - height) // 2
    return resized.crop((left, top, left + width, top + height))


@dataclass
class Camera:
    """A prepared camera for one scene."""

    big: Image.Image
    width: int
    height: int
    motion: contract.Motion
    _vignette: np.ndarray
    _grain: list
    _stats: tuple | None = None
    _lut: np.ndarray | None = None
    _defocus: np.ndarray | None = None
    _defocus_mask: np.ndarray | None = None

    @classmethod
    def prepare(
        cls,
        image: Image.Image,
        motion: contract.Motion,
        width: int,
        height: int,
    ) -> "Camera":
        base = cover_resize(image.convert("RGB"), width, height)
        scale = motion.max_scale
        big = base.resize(
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            Image.LANCZOS,
        )
        return cls(
            big=big, width=width, height=height, motion=motion,
            _vignette=_vignette_mask(width, height),
            _grain=_grain_tiles(width, height),
            _stats=_on_screen_stats(big, motion, width, height),
            _defocus=_defocused_plate(big, width, height),
            _defocus_mask=(_defocus_mask(width, height)
                           if contract.DEPTH_OF_FIELD > 0.0 else None),
        )

    def window(self, t: float) -> Tuple[float, float, float, float]:
        """Source box for eased progress ``t`` in 0..1."""
        return _window_box(self.motion, self.big.size, t)

    def frame(self, t: float, frame_index: int, grade=None) -> np.ndarray:
        """uint8 RGB frame for eased progress ``t``.

        Order matters and mirrors a real camera: the grade is the film stock, so
        it is applied to the exposed image *before* the lens artefacts. Grading
        after the vignette would darken shadows that the vignette already
        darkened, and the split tone would fight the falloff.
        """
        box = self.window(t)
        cropped = self.big.resize((self.width, self.height), Image.BILINEAR, box=box)
        arr = np.asarray(cropped, dtype=np.float32)

        if grade is not None:
            # Tone-map on uint8 through a cached LUT: identical curve for every
            # frame of the beat, so the exposure cannot flicker as the camera moves.
            if grade.mode == "enhance":
                if self._lut is None:
                    # 256-entry table in 0..255 units, indexed directly. A linear
                    # interpolation over the full luma plane measured 28 ms;
                    # the gather measures 1.3 ms for the same 8-bit result.
                    self._lut = (grade.tone_lut(self._stats) * 255.0).astype(np.float32)
                # Tone-map LUMINANCE and keep the channel ratios.
                #
                # Running the curve through each channel independently was the
                # obvious reading of "film applies the curve per channel", and it
                # is wrong for painted artwork: a steep per-channel curve
                # multiplies saturation, so a crimson arc went pink once lifted
                # and a cream report page went yellow. Riding a single luminance
                # curve keeps the painted colour as the artist left it.
                luma = arr @ grade_module.LUMA_WEIGHTS
                mapped = self._lut[np.clip(luma, 0.0, 255.0).astype(np.uint8)]
                gain = mapped * np.reciprocal(np.maximum(luma, 1.0))
                # Cap the gain per pixel so no channel clips. Without this, a
                # saturated red lifts until R pins at 255 while G and B keep
                # climbing — the hue survives but the colour washes out, which
                # is why the crimson arc was reading as pink.
                r, gg, b = arr[..., 0], arr[..., 1], arr[..., 2]
                brightest = np.maximum(np.maximum(r, gg), b)
                np.minimum(gain, 252.0 * np.reciprocal(np.maximum(brightest, 1.0)),
                           out=gain)
                arr = np.clip(arr * gain[..., None], 0.0, 255.0)
                arr = grade.colour_stage(arr)
            else:
                arr = grade.apply_float(arr, self._stats)
            if grade.bloom > 0.0:
                arr = _bloom(arr, grade.bloom, grade.bloom_threshold)

        if contract.DEPTH_OF_FIELD > 0.0:
            arr = _depth_of_field(arr, self._defocus, self._defocus_mask)

        arr *= self._vignette
        arr += self._grain[frame_index % _GRAIN_TILES]
        return np.clip(arr, 0.0, 255.0).astype(np.uint8)


def _defocused_plate(big: Image.Image, width: int, height: int) -> np.ndarray:
    """A blurred copy of the whole plate, cropped to the lens' widest view.

    Precomputed once per beat: blurring per frame would cost more than the rest
    of the render combined.
    """
    if contract.DEPTH_OF_FIELD <= 0.0:
        return None
    plate = big.resize((width, height), Image.BILINEAR).filter(
        ImageFilter.GaussianBlur(radius=max(1.0, width * 0.011)))
    return np.asarray(plate, dtype=np.float32)


def _window_box(motion: contract.Motion, big_size: Tuple[int, int],
                t: float) -> Tuple[float, float, float, float]:
    """Source box for eased progress ``t`` in 0..1, in ``big`` coordinates."""
    e = contract.ease_value(motion.ease, t)
    scale = motion.scale_from + (motion.scale_to - motion.scale_from) * e
    cx = motion.centre_from[0] + (motion.centre_to[0] - motion.centre_from[0]) * e
    cy = motion.centre_from[1] + (motion.centre_to[1] - motion.centre_from[1]) * e

    big_w, big_h = big_size
    win_w = big_w / max(1e-6, scale)
    win_h = big_h / max(1e-6, scale)
    x0 = min(max(0.0, cx * big_w - win_w / 2.0), big_w - win_w)
    y0 = min(max(0.0, cy * big_h - win_h / 2.0), big_h - win_h)
    return (x0, y0, x0 + win_w, y0 + win_h)


def _on_screen_stats(big: Image.Image, motion: contract.Motion,
                     width: int, height: int) -> tuple:
    """Black / mid / white of the crop the camera actually shows.

    Measuring the whole plate instead would mis-set the curve whenever the
    camera is pushed into a bright or dark corner — the screen would then not
    land on the grade's tonal target.
    """
    box = _window_box(motion, big.size, 0.5)
    crop = big.resize((width, height), Image.BILINEAR, box=box)
    return grade_module.source_stats(np.asarray(crop, dtype=np.uint8))


def _defocus_mask(width: int, height: int) -> np.ndarray:
    """1.0 at the focus point, falling to 0.0 in the corners. Shape (H, W, 1)."""
    ys = (np.arange(height, dtype=np.float32) + 0.5) / height
    xs = (np.arange(width, dtype=np.float32) + 0.5) / width
    fx, fy = contract.FOCUS_POINT
    radius = np.sqrt((ys[:, None] - fy) ** 2 + ((xs[None, :] - fx) * 0.85) ** 2)
    sharp = np.clip(1.0 - radius * contract.DOF_FALLOFF / 0.72, 0.0, 1.0)
    smooth = sharp * sharp * (3.0 - 2.0 * sharp)
    return smooth[:, :, None].astype(np.float32)


def _depth_of_field(arr: np.ndarray, blurred: np.ndarray,
                    mask: np.ndarray | None = None) -> np.ndarray:
    """Composite the sharp frame over a blurred copy using a radial mask.

    The mask is constant for a given frame size, so callers pass a cached one;
    rebuilding a radial falloff per frame cost more than the rest of the render.
    A real defocus also blooms the out-of-focus highlights, but the bloom pass
    already runs before this.
    """
    if mask is None:
        mask = _defocus_mask(arr.shape[1], arr.shape[0])
    mix = 1.0 - mask * (1.0 - contract.DEPTH_OF_FIELD)
    return arr * mix + blurred * (1.0 - mix)


def _bloom(arr: np.ndarray, strength: float, threshold: float = 0.62) -> np.ndarray:
    """Additive highlight glow.

    Bright areas are isolated, blurred on a 1/8-scale buffer and screened back
    in. The downscale is what makes it affordable per frame, and it also
    produces the wide, soft falloff that reads as halation rather than as a
    blur filter.

    Screen rather than add: adding glow on top of highlights that already sit
    near white clipped 14% of a bright beat to flat white. A screen blend
    asymptotes towards white instead, so the glow stays a glow.
    """
    luma = arr @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    weight = np.clip((luma - threshold * 255.0) / max(1.0, (1.0 - threshold) * 255.0),
                     0.0, 1.0)
    if not weight.any():
        return arr

    bright = (arr * weight[..., None]).astype(np.uint8)
    height, width = bright.shape[:2]
    small_w, small_h = max(1, width // 8), max(1, height // 8)
    small = Image.fromarray(bright, "RGB").resize((small_w, small_h), Image.BOX)
    small = small.filter(ImageFilter.GaussianBlur(radius=3.2))
    glow = np.asarray(small.resize((width, height), Image.BILINEAR), dtype=np.float32) * strength
    return 255.0 - (255.0 - arr) * (255.0 - glow) / 255.0


def _vignette_mask(width: int, height: int) -> np.ndarray:
    """Radial falloff, strength from the contract. Shape (H, W, 1)."""
    ys = (np.arange(height, dtype=np.float32) + 0.5) / height * 2.0 - 1.0
    xs = (np.arange(width, dtype=np.float32) + 0.5) / width * 2.0 - 1.0
    radius = np.sqrt(ys[:, None] ** 2 * 0.85 + xs[None, :] ** 2)
    falloff = np.clip(radius, 0.0, 1.0) ** 2.2
    gain = 1.0 - falloff * contract.VIGNETTE_STRENGTH
    return gain[:, :, None].astype(np.float32)


def _grain_tiles(width: int, height: int) -> list:
    tiles = []
    rng = np.random.default_rng(20260930)
    amplitude = contract.GRAIN_STRENGTH * 255.0
    for _ in range(_GRAIN_TILES):
        tile = rng.normal(0.0, amplitude, size=(height, width, 1)).astype(np.float32)
        tiles.append(tile)
    return tiles
