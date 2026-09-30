"""ffmpeg discovery shared by the noire renderer.

Kept separate from ``handdrawn/encoder.py`` so the two pipelines can evolve
independently; the lookup order is identical.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

_ENV_OVERRIDE = "FFMPEG"

_FFMPEG_LOCATIONS = (
    Path("node_modules/@ffmpeg-installer/linux-x64/ffmpeg"),
    Path("node_modules/ffmpeg-static/ffmpeg"),
)
_FFPROBE_LOCATIONS = (
    Path("node_modules/@ffprobe-installer/linux-x64/ffprobe"),
)


def _search(roots, locations) -> Optional[str]:
    for root in roots:
        for relative in locations:
            candidate = root / relative
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def _roots(project_dir: Optional[Path]):
    roots = [Path.cwd()]
    if project_dir:
        roots.insert(0, Path(project_dir))
    return roots


def find_ffmpeg(project_dir: Optional[Path] = None) -> str:
    override = os.environ.get(_ENV_OVERRIDE)
    if override and Path(override).exists():
        return override
    found = _search(_roots(project_dir), _FFMPEG_LOCATIONS) or shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError(
            "ffmpeg not found. Run tools/bootstrap.sh (npm install) or set $FFMPEG."
        )
    return found


def find_ffprobe(project_dir: Optional[Path] = None) -> Optional[str]:
    override = os.environ.get("FFPROBE")
    if override and Path(override).exists():
        return override
    return _search(_roots(project_dir), _FFPROBE_LOCATIONS) or shutil.which("ffprobe")


class Encoder:
    """Stream raw RGB frames into a silent H.264 MP4."""

    def __init__(
        self,
        output: Path,
        width: int,
        height: int,
        fps: int,
        crf: int = 22,
        preset: str = "medium",
        max_bitrate: str = "14M",
        project_dir: Optional[Path] = None,
    ) -> None:
        self.output = Path(output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.frames_written = 0
        self.process = subprocess.Popen(
            [
                find_ffmpeg(project_dir),
                "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
                # The renderer adds per-frame film grain, and grain is noise:
                # x264 cannot predict it, so a low CRF explodes the file. CRF 19
                # at 1080x1920 produced 809 MB / 55 Mbps for 123 seconds, which
                # nothing will accept as an upload. The cap keeps the ceiling
                # sane while CRF still decides how the cheap frames are spent.
                "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-maxrate", max_bitrate, "-bufsize", "28M",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(self.output),
            ],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    def write(self, frame: np.ndarray) -> None:
        if self.process.stdin is None:  # pragma: no cover - defensive
            raise RuntimeError("encoder pipe closed")
        flat = np.clip(frame * 255.0 + 0.5, 0, 255).astype(np.uint8)
        self.process.stdin.write(flat.tobytes())
        self.frames_written += 1

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        stderr = self.process.stderr.read().decode("utf-8", "replace") if self.process.stderr else ""
        code = self.process.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg failed ({code}): {stderr.strip()}")

    def __enter__(self) -> "Encoder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()
        else:  # pragma: no cover - cleanup path
            if self.process.stdin:
                self.process.stdin.close()
            self.process.kill()


def probe(path, ffprobe=None):
    """Return (width, height, duration_seconds) for a media file."""
    import subprocess as _sp

    binary = ffprobe or find_ffprobe(Path(path).parent)
    if not binary:
        return (0, 0, 0.0)
    out = _sp.run(
        [binary, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    ).stdout.split()
    width = int(out[0]) if len(out) > 0 else 0
    height = int(out[1]) if len(out) > 1 else 0
    try:
        duration = float(out[2]) if len(out) > 2 else 0.0
    except ValueError:
        duration = 0.0
    return width, height, duration
