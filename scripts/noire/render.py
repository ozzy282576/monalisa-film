"""Orchestrates the 9:16 noire explainer: timing, frames, sound, muxing.

Timing is driven by the *real narration audio*, not by a character-count guess:
each beat lasts ``max(min_duration, voice_length + padding)``.  That is what makes
subtitles and cuts land on the voice instead of drifting away from it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from . import audio as audio_module
from . import contract
from . import grade as grade_module
from .encoder import Encoder
from .motion import Camera
from .text import TextPanel


def probe_duration(path: Path) -> float:
    """Duration of an audio file in seconds, via ffprobe."""
    from .encoder import find_ffprobe

    binary = find_ffprobe(path.parent)
    if not binary:
        return 0.0
    out = subprocess.run(
        [binary, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


@dataclass
class Beat:
    id: str
    narration: str
    on_screen: Optional[str]
    annotation: Optional[str]
    motion: str
    accent: Optional[str]
    sfx: List[str]
    min_duration: float
    image: Optional[str]
    annotation_pos: Optional[list] = None
    grade_name: Optional[str] = None
    image_path: Optional[Path] = None
    voice_path: Optional[Path] = None
    voice_duration: float = 0.0
    duration: float = 0.0
    start: float = 0.0
    camera: Optional[Camera] = None
    grade: object = None


@dataclass
class Script:
    title: str
    beats: List[Beat]
    style_lock: str = ""
    bgm: List[dict] = field(default_factory=list)
    voice: str = ""
    art: str = "ink"          # "ink" = duotone grade on B&W linework, "colour" = leave alone
    padding: float = 0.45
    tail: float = 1.2
    gap: float = 0.18


def load_script(path: Path, project_dir: Path) -> Script:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    beats: List[Beat] = []
    for index, item in enumerate(raw["beats"], start=1):
        beat = Beat(
            id=str(item.get("id") or f"{index:02d}"),
            narration=item.get("narration", "") or "",
            on_screen=item.get("on_screen"),
            annotation=item.get("annotation"),
            motion=item.get("motion", "push_in"),
            accent=item.get("accent"),
            sfx=list(item.get("sfx") or []),
            min_duration=float(item.get("min_duration", 2.0)),
            image=item.get("image"),
            annotation_pos=item.get("annotation_pos"),
            grade_name=item.get("grade"),
        )
        if beat.image:
            candidate = Path(beat.image)
            if not candidate.is_absolute():
                candidate = project_dir / candidate
            # A colourised plate, when it exists, always wins over the ink master.
            # That lets artwork be colourised a few beats at a time: beats with a
            # colour plate render in colour, the rest still render from the ink
            # master (graded, if the script asks for it).
            colour = candidate.parent / "colour" / candidate.name
            if colour.exists():
                candidate = colour
            beat.image_path = candidate if candidate.exists() else None
        beats.append(beat)

    media = raw.get("media", {}) or {}
    voice_map: Dict[str, str] = media.get("voice") or {}
    for beat in beats:
        name = voice_map.get(beat.id)
        if name:
            candidate = Path(name)
            if not candidate.is_absolute():
                candidate = project_dir / candidate
            if candidate.exists():
                beat.voice_path = candidate
                beat.voice_duration = probe_duration(candidate)

    return Script(
        title=raw.get("title", "未命名"),
        beats=beats,
        style_lock=raw.get("style_lock", ""),
        bgm=list(raw.get("bgm") or []),
        voice=media.get("voice_id", ""),
        art=str(raw.get("art", "ink")),
        padding=float(raw.get("padding", 0.45)),
        tail=float(raw.get("tail", 1.2)),
        gap=float(raw.get("gap", 0.18)),
    )


class NoireRenderer:
    def __init__(
        self,
        project_dir: Path,
        script: Script,
        width: int = contract.WIDTH,
        height: int = contract.HEIGHT,
        fps: int = contract.FPS,
    ) -> None:
        self.project_dir = Path(project_dir)
        self.script = script
        self.width = width
        self.height = height
        self.fps = fps
        self.panel = TextPanel(self.project_dir, width)
        self._schedule()

    # -- timing --------------------------------------------------------------

    def _schedule(self) -> None:
        cursor = 0.0
        for index, beat in enumerate(self.script.beats):
            duration = max(beat.min_duration, beat.voice_duration + self.script.padding)
            beat.duration = round(duration, 3)
            beat.start = round(cursor, 3)
            cursor += beat.duration
            if index < len(self.script.beats) - 1:
                cursor += self.script.gap
        self.total_seconds = round(cursor + self.script.tail, 3)

        for beat in self.script.beats:
            # With colour artwork there is nothing to tint; an explicit per-beat
            # "grade" still wins, so a single beat can be pushed monochrome.
            if self.script.art == "colour" and not beat.grade_name:
                beat.grade = None
            else:
                beat.grade = grade_module.resolve(beat.grade_name, beat.id)
            if beat.image_path is None:
                continue
            motion = contract.MOTIONS.get(beat.motion, contract.MOTIONS["push_in"])
            with Image.open(beat.image_path) as handle:
                beat.camera = Camera.prepare(handle, motion, self.width, self.height)

    # -- frames --------------------------------------------------------------

    @property
    def total_frames(self) -> int:
        return max(1, int(round(self.total_seconds * self.fps)))

    def beat_at(self, frame_index: int) -> Tuple[Optional[Beat], int]:
        seconds = frame_index / self.fps
        for beat in self.script.beats:
            if beat.start <= seconds < beat.start + beat.duration:
                local = int(round((seconds - beat.start) * self.fps))
                return beat, local
        return (self.script.beats[-1] if self.script.beats else None), 0

    def render_frame(self, frame_index: int) -> np.ndarray:
        beat, local = self.beat_at(frame_index)
        if beat is None or beat.camera is None:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

        frames = max(1, int(round(beat.duration * self.fps)))
        t = min(1.0, local / max(1, frames - 1))
        arr = beat.camera.frame(t, frame_index)
        if beat.grade is not None:
            arr = beat.grade.apply(arr)

        image = Image.fromarray(arr, "RGB")
        if beat.annotation:
            pos = tuple(beat.annotation_pos) if beat.annotation_pos else (0.5, 0.24)
            self.panel.annotation(image, beat.annotation, beat.accent, position=pos)
        if beat.on_screen:
            self.panel.subtitle(image, beat.on_screen)

        out = np.asarray(image, dtype=np.uint8)

        # hard cut accent: a couple of blown-out frames on the beat
        if local < contract.IMPACT_FLASH_FRAMES and beat.accent == "red":
            fade = 1.0 - local / max(1, contract.IMPACT_FLASH_FRAMES)
            out = np.clip(
                out.astype(np.float32) + (255.0 - out.astype(np.float32)) * 0.85 * fade,
                0, 255,
            ).astype(np.uint8)
        elif local < contract.IMPACT_FLASH_FRAMES:
            fade = 1.0 - local / max(1, contract.IMPACT_FLASH_FRAMES)
            out = (out.astype(np.float32) * (1.0 - 0.9 * fade)).astype(np.uint8)
        return out

    # -- audio ---------------------------------------------------------------

    def audio_plan(self) -> audio_module.AudioPlan:
        plan = audio_module.AudioPlan(total_seconds=self.total_seconds)
        plan.bgm.append(("rain", 0.0, min(40.0, self.total_seconds)))
        for start in (30.0, 78.0):
            if start + 6.0 < self.total_seconds:
                plan.bgm.append(("rain", start, 14.0))
        for entry in self.script.bgm:
            plan.bgm.append((
                entry.get("effect", "strings"),
                float(entry.get("start", 0.0)),
                float(entry.get("duration", 5.0)),
            ))
        for beat in self.script.beats:
            if beat.voice_path is not None:
                plan.voice.append((beat.voice_path, beat.start))
            for effect in beat.sfx:
                plan.cues.append((effect, beat.start))
        return plan

    def render_audio(self, path: Path) -> Path:
        samples = audio_module.build(self.audio_plan())
        audio_module.write_wav(path, samples)
        return path

    # -- render --------------------------------------------------------------

    def render(
        self,
        output: Path,
        crf: int = 20,
        with_audio: bool = True,
        progress: bool = True,
    ) -> dict:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        total = self.total_frames

        # Only write the picture to a separate file when it is actually going to
        # be muxed; otherwise encode straight to the requested output so the
        # returned path always exists.
        has_voice = any(beat.voice_path for beat in self.script.beats)
        will_mux = with_audio and has_voice
        silent = output.with_name(output.stem + "-picture.mp4") if will_mux else output

        with Encoder(silent, self.width, self.height, self.fps, crf=crf,
                     project_dir=self.project_dir) as encoder:
            for index in range(total):
                encoder.write(self.render_frame(index).astype(np.float32) / 255.0)
                if progress and (index + 1) % 180 == 0:
                    print(f"  帧 {index + 1}/{total}", flush=True)

        result = {
            "output": output,
            "picture": silent,
            "frames": total,
            "seconds": self.total_seconds,
            "beats": len(self.script.beats),
            "width": self.width,
            "height": self.height,
            "audio": False,
        }

        if will_mux:
            wav = output.with_name(output.stem + "-mix.wav")
            self.render_audio(wav)
            from .encoder import find_ffmpeg

            subprocess.run(
                [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                 "-i", str(silent), "-i", str(wav),
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                 "-shortest", "-movflags", "+faststart", str(output)],
                check=True,
            )
            result["audio"] = True
        return result
