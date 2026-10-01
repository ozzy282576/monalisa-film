"""Story-level renderer: schedules beats, drives the encoder, writes the MP4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from . import contract
from . import layout as layout_module
from .caption import default_font_path, render_caption_plate
from .encoder import Encoder
from .imaging import (
    RGB,
    RGBA,
    contain_fit,
    derive_bw,
    fit_page,
    place_in_box,
    to_float,
)
from .pageflip import composite_flip
from .scene import ScenePlates, SceneRenderer, scene_is_full_page


def resolve_asset(project_dir: Path, value: Optional[str]) -> Optional[Path]:
    """Storyboard asset paths are ``staticFile``-relative, i.e. under ``public/``."""
    if not value:
        return None
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [
        project_dir / "public" / raw,
        project_dir / raw,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"asset not found: {value}")


def _square(image: Image.Image, size: int = contract.PLATE_SQUARE) -> Image.Image:
    """Contain-fit into the white padded square both plates share."""
    return contain_fit(image, size, size)


def _caption_plate_from_image(
    path: Path,
    canvas_width: int,
    canvas_height: int,
) -> RGBA:
    """Turn a generated caption crop into a transparent ink plate."""
    box = contract.caption_box(canvas_width)
    width = int(round(box["width"]))
    height = int(round(box["height"]))
    with Image.open(path) as handle:
        caption = handle.convert("RGB")
    plate = contain_fit(caption, width, height)

    luminance = np.asarray(plate.convert("L"), dtype=np.float32) / 255.0
    ink = np.clip((1.0 - luminance - 0.06) * 3.4, 0.0, 1.0)

    rgba = np.zeros((canvas_height, canvas_width, 4), dtype=np.float32)
    top = int(round(box["top"]))
    left = int(round(box["left"]))
    rgba[top:top + height, left:left + width, :3] = to_float(plate)
    rgba[top:top + height, left:left + width, 3] = ink
    return rgba


def load_plates(
    scene: dict,
    project: dict,
    project_dir: Path,
    canvas_width: int,
    canvas_height: int,
    font_path: Optional[Path],
    split_override: Optional[int] = None,
) -> ScenePlates:
    """Build the layer plates for one beat from its master page."""
    assets = scene.get("assets", {}) or {}
    plates = ScenePlates()

    master_path = resolve_asset(project_dir, assets.get("color"))
    if master_path is None:
        return plates
    with Image.open(master_path) as handle:
        master = handle.convert("RGB")

    # Page-flip keeps the complete, untouched master (DESIGN.md "Page flip").
    if scene_is_full_page(scene) or project.get("transition") == "page-flip":
        plates.full = to_float(fit_page(master, canvas_width, canvas_height))
        return plates

    layout = project.get("layout") or "auto"
    if layout == "auto":
        layout = "composite" if assets.get("text_image") else "full"

    # ``full``: the master is illustration-only, so it fills the whole panel and
    # the caption is drawn by the renderer.  This is the mode our `font`
    # lettering uses -- the image tool never gets a chance to draw a wrong glyph.
    if layout == "full":
        illustration = master
    else:
        detection = layout_module.analyze_composite(master)
        split_y = split_override if split_override is not None else detection.split_y
        illustration = master.crop((0, split_y, master.width, master.height))

    box = contract.illustration_box(canvas_width, canvas_height)
    square = _square(illustration)
    plates.color = place_in_box(square, canvas_width, canvas_height, box)
    plates.bw = place_in_box(
        derive_bw(square, **contract.BW_DERIVE), canvas_width, canvas_height, box
    )

    text_path = resolve_asset(project_dir, assets.get("text_image")) if layout != "full" else None
    if text_path is not None:
        plates.text = _caption_plate_from_image(text_path, canvas_width, canvas_height)
    elif font_path is not None and (scene.get("text") or "").strip():
        plates.text = render_caption_plate(
            scene["text"], canvas_width, canvas_height, font_path,
            jitter=float(project.get("lettering_jitter") or 0.0),
        )
    return plates


@dataclass
class RenderResult:
    output: Path
    frames: int
    width: int
    height: int
    fps: int
    duration_seconds: float
    scenes: int
    transition: str


class StoryRenderer:
    def __init__(
        self,
        project_dir: Path,
        storyboard: dict,
        canvas_width: int,
        canvas_height: int,
        wobble: float = 0.0,
        split_overrides: Optional[Dict[str, int]] = None,
        resources_dir: Optional[Path] = None,
    ) -> None:
        self.project_dir = project_dir
        self.resources_dir = resources_dir or project_dir
        self.project = storyboard["project"]
        self.scenes = storyboard["scenes"]
        self.width = canvas_width
        self.height = canvas_height
        self.fps = int(self.project.get("fps", contract.DESIGN_FPS))
        self.transition = self.project.get("transition", "cut")
        self.transition_frames = contract.transition_frames(storyboard)
        self.total = contract.total_frames(storyboard)
        self.split_overrides = split_overrides or {}

        try:
            font_path: Optional[Path] = default_font_path(self.resources_dir)
        except FileNotFoundError:
            font_path = None
        if self.project.get("text_mode", "font") != "font":
            font_path = None

        self.renderers: List[SceneRenderer] = []
        for index, scene in enumerate(self.scenes):
            plates = load_plates(
                scene, self.project, project_dir, canvas_width, canvas_height,
                font_path, self.split_overrides.get(str(scene.get("id"))),
            )
            self.renderers.append(SceneRenderer(
                scene, self.project, plates, canvas_width, canvas_height,
                wobble=wobble, seed=101 + index,
            ))

        self.starts: List[int] = []
        cursor = 0
        for index, renderer in enumerate(self.renderers):
            self.starts.append(cursor)
            overlap = self.transition_frames if index < len(self.renderers) - 1 else 0
            cursor += renderer.duration_frames - overlap

    # -- frame ---------------------------------------------------------------

    def render_frame(self, frame: int) -> RGB:
        if self.transition == "page-flip" and len(self.renderers) > 1:
            canvas = np.ones((self.height, self.width, 3), dtype=np.float32)
            for index in range(len(self.renderers) - 1, -1, -1):
                renderer = self.renderers[index]
                local = frame - self.starts[index]
                if local < 0 or local >= renderer.duration_frames:
                    continue
                scene_frame = renderer.frame(local)
                is_last = index == len(self.renderers) - 1
                if is_last or self.transition_frames <= 0:
                    progress = 0.0
                else:
                    flip_start = renderer.duration_frames - self.transition_frames
                    linear = min(1.0, max(0.0, (local - flip_start) / self.transition_frames))
                    progress = linear * linear * (3.0 - 2.0 * linear)
                canvas = composite_flip(
                    canvas, scene_frame, progress, self.width, self.height
                )
            return canvas

        index = 0
        for candidate, renderer in enumerate(self.renderers):
            if frame >= self.starts[candidate]:
                index = candidate
        return self.renderers[index].frame(frame - self.starts[index])

    # -- render --------------------------------------------------------------

    def render(self, output: Path, crf: int = 18, progress: bool = True) -> RenderResult:
        output = Path(output)
        with Encoder(
            output, self.width, self.height, self.fps,
            crf=crf, project_dir=self.project_dir,
        ) as encoder:
            for frame in range(self.total):
                encoder.write(self.render_frame(frame))
                if progress and (frame + 1) % 90 == 0:
                    print(f"  帧 {frame + 1}/{self.total}", flush=True)
        return RenderResult(
            output=output,
            frames=self.total,
            width=self.width,
            height=self.height,
            fps=self.fps,
            duration_seconds=self.total / self.fps,
            scenes=len(self.scenes),
            transition=self.transition,
        )


def preview_size() -> Tuple[int, int]:
    return (
        int(round(contract.DESIGN_WIDTH * contract.PREVIEW_SCALE / 2) * 2),
        int(round(contract.DESIGN_HEIGHT * contract.PREVIEW_SCALE / 2) * 2),
    )
