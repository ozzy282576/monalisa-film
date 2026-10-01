"""Rasteriser primitives: CSS filter emulation, contain fitting, BW derivation.

The browser applies CSS filters to non-linear sRGB values, so every kernel here
works on 0..1 sRGB floats rather than linear light.  That keeps the ported look
identical to what the Remotion renderer produced in Chrome.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence, Tuple

import numpy as np
from PIL import Image, ImageFilter

RGB = np.ndarray  # float32, shape (H, W, 3), range 0..1
RGBA = np.ndarray  # float32, shape (H, W, 4), range 0..1

WHITE = np.array([1.0, 1.0, 1.0], dtype=np.float32)

# CSS filter grayscale() matrix (non-linear sRGB, per Filter Effects Level 1)
_GRAY = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
# ffmpeg swscale RGB -> gray (format=gray) uses BT.601 luma
_BT601 = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def to_float(image: Image.Image) -> RGB:
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def to_image(array: RGB) -> Image.Image:
    return Image.fromarray(np.clip(array * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGB")


def to_image_rgba(array: RGBA) -> Image.Image:
    return Image.fromarray(np.clip(array * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGBA")


def load_rgb(path: Path | str) -> RGB:
    with Image.open(path) as handle:
        return to_float(handle)


def apply_css_filters(image: RGB, filters: Iterable[Tuple[str, float]]) -> RGB:
    """Apply a CSS ``filter`` chain left to right."""
    out = image
    for name, amount in filters:
        if name == "grayscale":
            if amount >= 1.0:
                gray = out @ _GRAY
                out = np.repeat(gray[..., None], 3, axis=2)
            elif amount > 0.0:
                gray = out @ _GRAY
                out = out + (np.repeat(gray[..., None], 3, axis=2) - out) * amount
        elif name == "contrast":
            out = (out - 0.5) * amount + 0.5
        elif name == "brightness":
            out = out * amount
        elif name == "saturate":
            gray = out @ _GRAY
            out = gray[..., None] + (out - gray[..., None]) * amount
        else:  # pragma: no cover - defensive
            raise ValueError(f"unsupported CSS filter: {name}")
        out = np.clip(out, 0.0, 1.0)
    return out


def contains_box(box: Sequence[float], width: int, height: int) -> Tuple[int, int, int, int]:
    """Return integer (left, top, width, height) for a fractional box."""
    left = int(round(box[0]))
    top = int(round(box[1]))
    right = int(round(box[2]))
    bottom = int(round(box[3]))
    left = max(0, min(width, left))
    top = max(0, min(height, top))
    right = max(left, min(width, right))
    bottom = max(top, min(height, bottom))
    return left, top, right - left, bottom - top


def contain_fit(image: Image.Image, width: int, height: int, background=(255, 255, 255)) -> Image.Image:
    """CSS ``object-fit: contain`` into a (width, height) box, centred."""
    if width <= 0 or height <= 0:
        raise ValueError("contain_fit needs a positive box")
    source_w, source_h = image.size
    scale = min(width / source_w, height / source_h)
    target_w = max(1, int(round(source_w * scale)))
    target_h = max(1, int(round(source_h * scale)))
    resized = image.resize((target_w, target_h), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), background)
    canvas.paste(resized, ((width - target_w) // 2, (height - target_h) // 2))
    return canvas


def fit_page(image: Image.Image, width: int, height: int) -> Image.Image:
    """Full-canvas ``object-fit: contain`` (used by page-flip and full pages)."""
    return contain_fit(image, width, height).convert("RGB")


def crop_cover(image: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
    return image.crop(box)


def derive_bw(color: Image.Image, contrast: float, brightness: float,
              unsharp_radius: float, unsharp_percent: float) -> Image.Image:
    """Port of the local BW derivation in scripts/page-assets.mjs.

    ``format=gray, eq=contrast=1.18:brightness=0.035, unsharp=5:5:0.55``.
    """
    gray = np.asarray(color.convert("L"), dtype=np.float32) / 255.0
    gray = (gray - 0.5) * contrast + 0.5 + brightness
    plate = Image.fromarray(np.clip(gray * 255.0 + 0.5, 0, 255).astype(np.uint8), "L")
    plate = plate.filter(ImageFilter.UnsharpMask(
        radius=unsharp_radius, percent=int(unsharp_percent), threshold=0))
    return plate.convert("RGB")


def place_in_box(
    plate: Image.Image,
    canvas_width: int,
    canvas_height: int,
    box: dict,
) -> RGB:
    """Place a plate into the illustration box the way ``object-fit`` would."""
    left = int(round(box["left"]))
    top = int(round(box["top"]))
    width = int(round(box["right"])) - left
    height = int(round(box["bottom"])) - top
    layer = np.ones((canvas_height, canvas_width, 3), dtype=np.float32)
    if width <= 0 or height <= 0:
        return layer
    fitted = contain_fit(plate, width, height)
    layer[top:top + height, left:left + width] = to_float(fitted)
    return layer


def blend(base: RGB, top: RGB, mask: np.ndarray) -> RGB:
    """Alpha-composite ``top`` over ``base`` with a float mask."""
    return base * (1.0 - mask) + top * mask


def alpha_blend(base: RGB, top_rgba: RGBA) -> RGB:
    alpha = top_rgba[..., 3:4]
    return base * (1.0 - alpha) + top_rgba[..., :3] * alpha


def gaussian_blur(mask: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return mask
    image = Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), "L")
    blurred = image.filter(ImageFilter.GaussianBlur(radius=sigma))
    return np.asarray(blurred, dtype=np.float32) / 255.0


def shift(mask: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Translate a mask, filling the exposed area with zeros."""
    out = np.zeros_like(mask)
    height, width = mask.shape
    sx = int(round(dx))
    sy = int(round(dy))
    x0, x1 = max(0, sx), min(width, width + sx)
    y0, y1 = max(0, sy), min(height, height + sy)
    if x0 >= x1 or y0 >= y1:
        return out
    out[y0:y1, x0:x1] = mask[y0 - sy:y1 - sy, x0 - sx:x1 - sx]
    return out


def tint(color: Sequence[float], mask: np.ndarray) -> RGB:
    return np.broadcast_to(
        np.array(color, dtype=np.float32), mask.shape + (3,)
    ).copy()
