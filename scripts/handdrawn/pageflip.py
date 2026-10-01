"""The bottom-right page curl.

Ported path-for-path from ``PageFlipScene`` in
``src/StoryVideo.tsx``.  The upstream component builds two SVG paths -- the flat
part of the page and the folding band -- clips the scene to each, and paints a
gradient plus three strokes over the fold.  This module reproduces the same
Bezier geometry and the same paint order with numpy rasterisation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import contract
from .imaging import RGB, gaussian_blur, shift

FOLD_GRADIENT = (
    (0.00, (0xD5, 0xCF, 0xC4), 0.94),
    (0.28, (0xF3, 0xEF, 0xE7), 0.98),
    (0.62, (0xFF, 0xFE, 0xF9), 1.00),
    (1.00, (0xD8, 0xD0, 0xC3), 0.88),
)
SHADOW_COLOR = np.array([0x30, 0x2B, 0x25], dtype=np.float32) / 255.0
EDGE_COLOR = np.array([0xB7, 0xAD, 0xA0], dtype=np.float32) / 255.0


@dataclass(frozen=True)
class FlipGeometry:
    progress: float
    curl: float
    x_top: float
    x_bottom: float
    fold_width: float


def _bezier_x_at_y(
    x_top: float,
    x_bottom: float,
    control_top: float,
    control_bottom: float,
    height: float,
    rows: int,
) -> np.ndarray:
    """Sample the cubic Bezier and invert y(t) so x is a function of y."""
    steps = 2048
    t = np.linspace(0.0, 1.0, steps, dtype=np.float64)
    mt = 1.0 - t
    ys = (
        3.0 * mt * mt * t * (height * 0.31)
        + 3.0 * mt * t * t * (height * 0.70)
        + t * t * t * height
    )
    xs = (
        mt ** 3 * x_top
        + 3.0 * mt * mt * t * control_top
        + 3.0 * mt * t * t * control_bottom
        + t ** 3 * x_bottom
    )
    order = np.argsort(ys)
    ys = ys[order]
    xs = xs[order]
    unique, index = np.unique(ys, return_index=True)
    sample_y = np.linspace(0.0, height, rows, dtype=np.float64)
    return np.interp(sample_y, unique, xs[index]).astype(np.float32)


def geometry_for(progress: float, width: float, height: float) -> FlipGeometry:
    """Ported arithmetic from PageFlipScene."""
    bottom_progress = min(1.0, progress / 0.78)
    top_progress = max(0.0, (progress - 0.28) / 0.72)
    x_top = width * (1.0 - top_progress)
    x_bottom = width * (1.0 - bottom_progress)
    curl = float(np.sin(progress * np.pi))
    bow = width * contract.PAGE_FLIP_BOW * curl
    control_top = min(width, x_top + bow)
    control_bottom = min(width, x_bottom + bow * contract.PAGE_FLIP_BOW_BOTTOM)
    fold_width = contract.PAGE_FLIP_FOLD_BASE + width * contract.PAGE_FLIP_FOLD_SPAN * curl
    return FlipGeometry(progress, curl, x_top, x_bottom, fold_width)


def _gradient_columns(bbox_width: int) -> np.ndarray:
    """RGBA gradient rasterised across the fold's own bounding box."""
    u = (np.arange(bbox_width, dtype=np.float32) + 0.5) / max(1, bbox_width)
    out = np.zeros((bbox_width, 4), dtype=np.float32)
    stops = np.array([stop[0] for stop in FOLD_GRADIENT], dtype=np.float32)
    for channel in range(3):
        values = np.array([stop[1][channel] for stop in FOLD_GRADIENT], dtype=np.float32) / 255.0
        out[:, channel] = np.interp(u, stops, values)
    alphas = np.array([stop[2] for stop in FOLD_GRADIENT], dtype=np.float32)
    out[:, 3] = np.interp(u, stops, alphas)
    return out


def _transform_fold_source(
    scene_frame: RGB,
    origin_x: float,
    translate_x: float,
    scale_x: float,
) -> RGB:
    """Apply ``translateX() scaleX()`` about ``transform-origin`` to the frame."""
    height, width = scene_frame.shape[:2]
    scale_x = max(0.2, scale_x)
    columns = np.arange(width, dtype=np.float32)
    source = origin_x + (columns - translate_x - origin_x) / scale_x
    index = np.clip(np.rint(source), 0, width - 1).astype(np.int32)
    return scene_frame[:, index]


def composite_flip(
    base: RGB,
    scene_frame: RGB,
    progress: float,
    width: int,
    height: int,
) -> RGB:
    """Composite one flipping page on top of ``base``."""
    if progress <= 0.0:
        return scene_frame.copy()

    geo = geometry_for(progress, width, height)
    rows = height
    edge = _bezier_x_at_y(geo.x_top, geo.x_bottom, min(width, geo.x_top + width * contract.PAGE_FLIP_BOW * geo.curl),
                          min(width, geo.x_bottom + width * contract.PAGE_FLIP_BOW * geo.curl * contract.PAGE_FLIP_BOW_BOTTOM),
                          float(height), rows)
    outer = _bezier_x_at_y(
        min(width, geo.x_top + geo.fold_width),
        min(width, geo.x_bottom + geo.fold_width * 0.72),
        min(width, min(width, geo.x_top + width * contract.PAGE_FLIP_BOW * geo.curl) + geo.fold_width * 0.78),
        min(width, min(width, geo.x_bottom + width * contract.PAGE_FLIP_BOW * geo.curl * contract.PAGE_FLIP_BOW_BOTTOM) + geo.fold_width * 0.58),
        float(height),
        rows,
    )

    xs = np.arange(width, dtype=np.float32)[None, :]
    front = (xs <= edge[:, None]).astype(np.float32)
    fold = ((xs > edge[:, None]) & (xs <= outer[:, None])).astype(np.float32)

    out = base * (1.0 - front[..., None]) + scene_frame * front[..., None]

    if geo.curl <= 0.001:
        return out

    origin = (geo.x_top + geo.x_bottom) / 2.0
    translated = _transform_fold_source(
        scene_frame,
        origin,
        geo.fold_width * 0.12,
        1.0 - geo.curl * 0.04,
    )
    fade = 0.3 + geo.curl * 0.32
    brightness = 1.07 + geo.curl * 0.08
    saturation = 0.62 - geo.curl * 0.12

    gray = translated @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    translated = gray[..., None] + (translated - gray[..., None]) * saturation
    translated = np.clip(translated * brightness, 0.0, 1.0)

    # feDropShadow: the fold silhouette, offset and blurred, under the fold.
    silhouette = gaussian_blur(fold, 10.0 + geo.curl * 15.0)
    silhouette = shift(silhouette, 12.0 + geo.curl * 20.0, 3.0)
    flood = (0.2 + geo.curl * 0.18)
    shadow_alpha = np.clip(silhouette * flood, 0.0, 1.0)[..., None]
    out = out * (1.0 - shadow_alpha) + SHADOW_COLOR * shadow_alpha

    # The folded sheet itself.
    fold_alpha = (fold * fade)[..., None]
    out = out * (1.0 - fold_alpha) + translated * fold_alpha

    # The gradient painted over the fold path.
    x0 = int(max(0, np.floor(edge.min())))
    x1 = int(min(width, np.ceil(outer.max()) + 1))
    if x1 > x0:
        gradient = _gradient_columns(x1 - x0)
        patch = out[:, x0:x1]
        local_fold = fold[:, x0:x1][..., None]
        alpha = (gradient[None, :, 3:4] * local_fold * fade)
        out[:, x0:x1] = patch * (1.0 - alpha) + gradient[None, :, :3] * alpha

    # stroke #b7ada0 and the white highlight along the fold line
    for color, stroke_width, opacity, offset in (
        (EDGE_COLOR, 2.0 + geo.curl * 2.5, 0.55 + geo.curl * 0.28, 0.0),
        (np.array([1.0, 1.0, 1.0], dtype=np.float32), 1.2 + geo.curl * 1.4, 0.7,
         max(1.0, geo.fold_width * 0.1)),
    ):
        line = np.abs(xs - (edge[:, None] + offset)) <= stroke_width * 0.5
        mask = (line * opacity)[..., None].astype(np.float32)
        out = out * (1.0 - mask) + color * mask

    # wide soft dark band hugging the fold (the shadow-filtered stroke)
    soft_width = 18.0 + geo.curl * 34.0
    soft = np.abs(xs - edge[:, None]) <= soft_width * 0.5
    soft = gaussian_blur(soft.astype(np.float32), 10.0 + geo.curl * 15.0)
    soft_alpha = (soft * (0.04 + geo.curl * 0.08))[..., None]
    out = out * (1.0 - soft_alpha) + SHADOW_COLOR * soft_alpha

    return out
