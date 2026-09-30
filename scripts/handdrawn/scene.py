"""Scene compositing: the ``text -> bw_full -> detail -> color`` layer reveal.

Ported from ``src/Scene.tsx`` + ``src/LayerWipe.tsx`` + ``src/TextWipe.tsx``.

The wipe is ``clip-path: inset(0 <100-p>% 0 0)`` on a box that spans the
illustration panel, i.e. a straight vertical edge travelling left to right.
That is exactly what the upstream renderer does; the hand-drawn character comes
from the artwork and the lettering, not from a wobbling mask, so this port does
not add one (``--wobble`` exists for users who want it).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from . import contract
from .imaging import RGB, RGBA, alpha_blend, apply_css_filters


# Storyboard layer ids (DESIGN.md) -> ScenePlates attribute names
PLATE_ATTRIBUTE = {
    "text": "text",
    "bw_full": "bw",
    "detail": "detail",
    "color": "color",
}


@dataclass
class ScenePlates:
    """Pre-rasterised, canvas-sized layer plates for one beat."""

    color: Optional[RGB] = None
    bw: Optional[RGB] = None
    detail: Optional[RGB] = None
    text: Optional[RGBA] = None
    full: Optional[RGB] = None  # page-flip: the untouched master page


@dataclass(frozen=True)
class SceneTiming:
    duration_frames: int
    schedule: Tuple[contract.RevealStep, ...]
    starts: Dict[str, Tuple[int, int]]


class SceneRenderer:
    def __init__(
        self,
        scene: dict,
        project: dict,
        plates: ScenePlates,
        canvas_width: int,
        canvas_height: int,
        wobble: float = 0.0,
        seed: int = 11,
    ) -> None:
        self.scene = scene
        self.project = project
        self.plates = plates
        self.width = canvas_width
        self.height = canvas_height
        self.wobble = wobble
        self.rng = np.random.default_rng(seed)

        fps = int(project.get("fps", contract.DESIGN_FPS))
        self.duration_frames = max(1, round(float(scene["duration_sec"]) * fps))
        layers = tuple(scene.get("layers") or ())
        self.schedule = contract.reveal_schedule(
            self.duration_frames, layers, bool(project.get("enable_detail"))
        )
        self.starts = {
            step.layer: contract.reveal_frames(self.duration_frames, step, layers)
            for step in self.schedule
        }

        self.illustration = contract.illustration_box(self.width, self.height)
        self.caption = contract.caption_box(self.width)

    # -- helpers ------------------------------------------------------------

    def progress(self, layer: str, local_frame: int) -> float:
        start, length = self.starts[layer]
        linear = (local_frame - start) / max(1, length)
        linear = min(1.0, max(0.0, linear))
        return linear * linear * (3.0 - 2.0 * linear)  # smoothstep

    def _edge_positions(self, progress: float, left: float, right: float) -> Tuple[float, float]:
        """Return (full_columns_edge, y_offsets) for the reveal edge."""
        edge = left + (right - left) * progress
        if self.wobble <= 0:
            return edge, 0.0
        return edge, self.wobble

    def _edge_column(self, progress: float, left: float, right: float, rows: int) -> np.ndarray:
        """Per-row reveal edge. Straight by default, hand-wobbled on request."""
        edge = left + (right - left) * progress
        if self.wobble <= 0:
            return np.full(rows, edge, dtype=np.float32)
        y = np.arange(rows, dtype=np.float32)
        amp = self.wobble * (right - left) * 0.012
        wave = (
            np.sin(y * 0.061 + 0.7)
            + 0.55 * np.sin(y * 0.0173 + 2.1)
            + 0.3 * np.sin(y * 0.211 + 4.2)
        ) / 1.85
        return edge + amp * wave

    # -- layer application --------------------------------------------------

    def _apply_rect(self, canvas: RGB, layer: RGB, progress: float,
                    left: float, right: float, top: float, bottom: float) -> None:
        if progress <= 0.0:
            return
        x0 = int(max(0, round(left)))
        x1 = int(min(self.width, round(right)))
        y0 = int(max(0, round(top)))
        y1 = int(min(self.height, round(bottom)))
        if x1 <= x0 or y1 <= y0:
            return

        if self.wobble <= 0:
            edge = x0 + (x1 - x0) * min(1.0, progress)
            cut = int(np.floor(edge))
            if cut > x0:
                canvas[y0:y1, x0:min(cut, x1)] = layer[y0:y1, x0:min(cut, x1)]
            fraction = edge - cut
            if 0.0 < fraction < 1.0 and x0 <= cut < x1:
                canvas[y0:y1, cut] = (
                    canvas[y0:y1, cut] * (1.0 - fraction) + layer[y0:y1, cut] * fraction
                )
            return

        edges = self._edge_column(progress, x0, x1, y1 - y0)
        xs = np.arange(self.width, dtype=np.float32)[None, :]
        mask = np.clip(edges[:, None] - xs + 0.5, 0.0, 1.0)
        region = canvas[y0:y1, x0:x1]
        plate = layer[y0:y1, x0:x1]
        canvas[y0:y1, x0:x1] = region * (1.0 - mask) + plate * mask

    def _apply_rect_rgba(self, canvas: RGB, layer: RGBA, progress: float,
                         left: float, right: float, top: float, bottom: float) -> None:
        if progress <= 0.0:
            return
        x0 = int(max(0, round(left)))
        x1 = int(min(self.width, round(right)))
        y0 = int(max(0, round(top)))
        y1 = int(min(self.height, round(bottom)))
        if x1 <= x0 or y1 <= y0:
            return

        if self.wobble <= 0:
            edge = x0 + (x1 - x0) * min(1.0, progress)
            cut = int(np.floor(edge))
            fraction = edge - cut

            def composite(xa: int, xb: int, scale: float) -> None:
                if xb <= xa:
                    return
                patch = layer[y0:y1, xa:xb].copy()
                patch[..., 3] *= scale
                canvas[y0:y1, xa:xb] = alpha_blend(canvas[y0:y1, xa:xb], patch)

            composite(x0, min(cut, x1), 1.0)
            if 0.0 < fraction < 1.0 and x0 <= cut < x1:
                composite(cut, cut + 1, fraction)
            return

        edges = self._edge_column(progress, x0, x1, y1 - y0)
        xs = np.arange(self.width, dtype=np.float32)[None, :]
        mask = np.clip(edges[:, None] - xs + 0.5, 0.0, 1.0)
        patch = layer[y0:y1, x0:x1].copy()
        patch[..., 3] *= mask
        canvas[y0:y1, x0:x1] = alpha_blend(canvas[y0:y1, x0:x1], patch)

    # -- frame --------------------------------------------------------------

    def frame(self, local_frame: int) -> RGB:
        if self.plates.full is not None:
            return self.plates.full.copy()

        canvas = np.ones((self.height, self.width, 3), dtype=np.float32)
        box = self.illustration
        for step in self.schedule:
            if step.layer == "text":
                continue
            plate = getattr(self.plates, PLATE_ATTRIBUTE[step.layer], None)
            if plate is None:
                continue
            treated = apply_css_filters(plate, contract.TREATMENTS[step.treatment])
            self._apply_rect(
                canvas, treated, self.progress(step.layer, local_frame),
                box["left"], box["right"], box["top"], box["bottom"],
            )

        if self.plates.text is not None:
            self._apply_rect_rgba(
                canvas, self.plates.text, self.progress("text", local_frame),
                self.caption["left"], self.caption["left"] + self.caption["width"],
                self.caption["top"], self.caption["top"] + self.caption["height"],
            )
        return canvas


def scene_is_full_page(scene: dict) -> bool:
    """``full_uploaded_page`` / ``full_generated_page`` render untouched."""
    return (
        scene.get("shot") in ("full_uploaded_page", "full_generated_page")
        and scene.get("assets", {}).get("color")
    )
