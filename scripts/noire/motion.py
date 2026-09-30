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
from PIL import Image

from . import contract

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
        )

    def window(self, t: float) -> Tuple[float, float, float, float]:
        """Source box for eased progress ``t`` in 0..1."""
        motion = self.motion
        e = contract.ease_value(motion.ease, t)
        scale = motion.scale_from + (motion.scale_to - motion.scale_from) * e
        cx = motion.centre_from[0] + (motion.centre_to[0] - motion.centre_from[0]) * e
        cy = motion.centre_from[1] + (motion.centre_to[1] - motion.centre_from[1]) * e

        big_w, big_h = self.big.size
        win_w = big_w / max(1e-6, scale)
        win_h = big_h / max(1e-6, scale)
        x0 = cx * big_w - win_w / 2.0
        y0 = cy * big_h - win_h / 2.0
        x0 = min(max(0.0, x0), big_w - win_w)
        y0 = min(max(0.0, y0), big_h - win_h)
        return (x0, y0, x0 + win_w, y0 + win_h)

    def frame(self, t: float, frame_index: int) -> np.ndarray:
        """uint8 RGB frame for eased progress ``t``."""
        box = self.window(t)
        cropped = self.big.resize((self.width, self.height), Image.BILINEAR, box=box)
        arr = np.asarray(cropped, dtype=np.float32)
        arr *= self._vignette
        arr += self._grain[frame_index % _GRAIN_TILES]
        return np.clip(arr, 0.0, 255.0).astype(np.uint8)


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
