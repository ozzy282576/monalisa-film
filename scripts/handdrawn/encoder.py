"""ffmpeg discovery and the silent H.264 encoder.

The upstream project renders through Remotion, which ships its own ffmpeg.  This
port streams raw RGB frames into an ffmpeg process over a pipe, which keeps the
same codec settings (``libx264``, ``yuv420p``, CRF 18 final / 23 preview,
``--muted``) without needing a browser.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np

_ENV_OVERRIDE = "FFMPEG"
_NODE_LOCATIONS = (
    Path("node_modules/@ffmpeg-installer/linux-x64/ffmpeg"),
    Path("node_modules/@remotion/compositor-linux-x64-gnu/ffmpeg"),
    Path("node_modules/ffmpeg-static/ffmpeg"),
)
_NODE_PROBE_LOCATIONS = (
    Path("node_modules/@ffprobe-installer/linux-x64/ffprobe"),
    Path("node_modules/@remotion/compositor-linux-x64-gnu/ffprobe"),
)


def find_ffprobe(project_dir: Optional[Path] = None) -> Optional[str]:
    override = os.environ.get("FFPROBE")
    if override and Path(override).exists():
        return override
    roots = [Path.cwd()]
    if project_dir:
        roots.insert(0, project_dir)
    for root in roots:
        for relative in _NODE_PROBE_LOCATIONS:
            candidate = root / relative
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)
    return shutil.which("ffprobe")


def find_ffmpeg(project_dir: Optional[Path] = None) -> str:
    override = os.environ.get(_ENV_OVERRIDE)
    if override and Path(override).exists():
        return override
    roots = [Path.cwd()]
    if project_dir:
        roots.insert(0, project_dir)
    for root in roots:
        for relative in _NODE_LOCATIONS:
            candidate = root / relative
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError(
        "ffmpeg not found. Run tools/bootstrap.sh (npm install) or set $FFMPEG."
    )


class Encoder:
    """Write RGB frames to a silent H.264 MP4."""

    def __init__(
        self,
        output: Path,
        width: int,
        height: int,
        fps: int,
        ffmpeg: Optional[str] = None,
        crf: int = 18,
        preset: str = "medium",
        project_dir: Optional[Path] = None,
    ) -> None:
        self.output = Path(output)
        self.width = width
        self.height = height
        self.fps = fps
        self.frames_written = 0
        self.output.parent.mkdir(parents=True, exist_ok=True)
        binary = ffmpeg or find_ffmpeg(project_dir)
        self.binary = binary
        self.process = subprocess.Popen(
            [
                binary,
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "-s", f"{width}x{height}",
                "-r", str(fps),
                "-i", "-",
                "-an",
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(self.output),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write(self, frame: np.ndarray) -> None:
        if self.process.stdin is None:  # pragma: no cover - defensive
            raise RuntimeError("encoder pipe is closed")
        flat = np.clip(frame * 255.0 + 0.5, 0, 255).astype(np.uint8)
        self.process.stdin.write(flat.tobytes())
        self.frames_written += 1

    def close(self) -> int:
        if self.process.stdin is not None:
            self.process.stdin.close()
        stderr = self.process.stderr.read().decode("utf-8", "replace") if self.process.stderr else ""
        code = self.process.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg failed ({code}): {stderr.strip()}")
        return code

    def __enter__(self) -> "Encoder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()
        else:  # pragma: no cover - cleanup path
            if self.process.stdin:
                self.process.stdin.close()
            self.process.kill()


def probe(path: Path, ffprobe: Optional[str] = None) -> Tuple[int, int, float]:
    """Return (width, height, duration_seconds) for a media file."""
    binary = ffprobe or find_ffprobe(path.parent)
    if not binary:
        return (0, 0, 0.0)
    out = subprocess.run(
        [binary, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    width = int(out[0]) if len(out) > 0 else 0
    height = int(out[1]) if len(out) > 1 else 0
    try:
        duration = float(out[2]) if len(out) > 2 else 0.0
    except ValueError:
        duration = 0.0
    return width, height, duration
