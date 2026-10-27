#!/usr/bin/env python3
"""Deterministic soundtrack build for the 雨夜屠夫林过云：一卷菲林里的四条人命 short.

Why this module exists
----------------------
The first cut mixed narration, score and effects entirely inside one long
``ffmpeg`` filter graph (``adelay`` -> ``amix`` -> ``sidechaincompress`` ->
``amix`` -> ``loudnorm``).  That graph was never verified by measurement: the
delivery check only asserted that the MP4 *container* reported an AAC stereo
track, so an inaudible or near-silent result could pass every gate and ship.

This module builds the same three elements in numpy instead, and refuses to
hand back a soundtrack that it cannot measure as audible:

* narration is decoded once, retimed with the well-tested ``atempo`` filter and
  placed on the timeline at exact sample offsets (no ``adelay``);
* the score is ducked under the narration with an attack/release envelope
  computed here (no ``sidechaincompress``);
* loudness is normalised to an explicit RMS target with an explicit peak
  ceiling (no single-pass ``loudnorm`` whose result depends on ffmpeg's
  internal measurement);
* every narration chapter and the whole timeline are measured, and a silent
  or too-quiet mix raises instead of being written.

The output is bit-for-bit reproducible: same inputs, same numbers, anywhere.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RATE = 48000

# Editorial targets. -20 dBFS RMS / -1.5 dBTP is the level the measured
# commentary mixes land on; it is loud enough to hear on phone speakers.
TARGET_RMS_DBFS = -20.0
PEAK_CEILING_DBFS = -1.5
VOICE_LEVEL = 1.0
BGM_LEVEL = 0.30
SFX_LEVEL = 0.85
DUCK_DEPTH = 0.55
DUCK_ATTACK = 0.03
DUCK_RELEASE = 0.35

# Gates. A mix that violates these is broken, not "a stylistic choice".
MIN_MIX_RMS_DBFS = -34.0
MIN_CHAPTER_RMS_DBFS = -40.0
MAX_SILENT_FRACTION = 0.02
MIN_CREST_DB = 2.0
SILENCE_THRESHOLD_DBFS = -50.0


class AudioBuildError(RuntimeError):
    """Raised when a soundtrack cannot be measured as audible."""


def run(command) -> None:
    subprocess.run([str(part) for part in command], check=True)


def decode(path: Path, rate: int = RATE, channels: int = 1, extra=()) -> np.ndarray:
    """Decode any media file to float32 samples shaped ``(samples, channels)``."""
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.close()
    temporary = Path(handle.name)
    try:
        filters = list(extra) + [f"aresample={rate}"]
        run([
            "ffmpeg", "-v", "error", "-hide_banner", "-y", "-i", str(path),
            "-af", ",".join(filters), "-ar", str(rate), "-ac", str(channels),
            "-c:a", "pcm_s16le", "-f", "wav", str(temporary),
        ])
        with wave.open(str(temporary), "rb") as reader:
            data = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2")
            data = data.astype(np.float32) / 32768.0
            return data.reshape(-1, reader.getnchannels())
    finally:
        temporary.unlink(missing_ok=True)


def dbfs(value: float) -> float:
    if value <= 1e-9:
        return -120.0
    return round(20 * math.log10(value), 2)


def rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))


def envelope(samples: np.ndarray, rate: int = RATE, attack: float = DUCK_ATTACK,
             release: float = DUCK_RELEASE) -> np.ndarray:
    """One-pole attack/release follower over a downsampled RMS envelope."""
    hop = max(1, rate // 100)  # 100 Hz control rate is plenty for ducking
    mono = samples.mean(axis=1) if samples.ndim > 1 else samples
    count = len(mono) // hop
    if count < 2:
        return np.zeros(len(mono), dtype=np.float32)
    blocks = mono[: count * hop].reshape(count, hop)
    level = np.sqrt(np.mean(np.square(blocks, dtype=np.float64), axis=1))
    peak = max(1e-6, float(level.max()))
    level = level / peak
    coefficient_a = math.exp(-1.0 / (100.0 * attack))
    coefficient_r = math.exp(-1.0 / (100.0 * release))
    smoothed = np.empty(count, dtype=np.float64)
    state = 0.0
    for index, value in enumerate(level):
        weight = coefficient_a if value > state else coefficient_r
        state = weight * state + (1.0 - weight) * value
        smoothed[index] = state
    grid = np.arange(len(mono), dtype=np.float64) / hop
    return np.interp(grid, np.arange(count, dtype=np.float64), smoothed).astype(np.float32)


def fade_edges(samples: np.ndarray, rate: int = RATE, fade_in: float = 0.02,
               fade_out: float = 0.06) -> np.ndarray:
    count = len(samples)
    head = min(count, int(fade_in * rate))
    tail = min(count - head, int(fade_out * rate))
    if head:
        samples[:head] *= np.linspace(0.0, 1.0, head, dtype=np.float32)
    if tail > 0:
        samples[-tail:] *= np.linspace(1.0, 0.0, tail, dtype=np.float32)
    return samples


def build_soundtrack(narration, music: Path, effects: Path, output: Path,
                     duration: float = 180.0, rate: int = RATE,
                     report_path: Path | None = None) -> dict:
    """Mix narration + score + effects into one measured stereo WAV."""
    total = int(round(duration * rate))
    voice = np.zeros((total, 2), dtype=np.float32)

    for row in narration:
        samples = decode(
            Path(row["path"]), rate, 1,
            extra=[f"atempo={row['tempo']:.9f}", "highpass=f=70", "lowpass=f=11000"],
        )[:, 0]
        planned = int(round((row["end"] - row["start"]) * rate))
        if len(samples) < planned:
            samples = np.pad(samples, (0, planned - len(samples)))
        samples = fade_edges(samples[:planned], rate)
        start = int(round(row["start"] * rate))
        room = total - start
        if room <= 0:
            continue
        usable = min(len(samples), room)
        voice[start:start + usable, 0] += samples[:usable]
        voice[start:start + usable, 1] += samples[:usable]

    score = decode(music, rate, 2)
    effects_track = decode(effects, rate, 2)

    def fit(track: np.ndarray) -> np.ndarray:
        if len(track) >= total:
            return track[:total]
        repeats = int(math.ceil(total / max(1, len(track))))
        return np.tile(track, (repeats, 1))[:total]

    score, effects_track = fit(score), fit(effects_track)

    duck = 1.0 - DUCK_DEPTH * envelope(np.abs(voice).max(axis=1), rate)
    mix = (voice * VOICE_LEVEL
           + score * (BGM_LEVEL * duck)[:, None]
           + effects_track * SFX_LEVEL)

    # Loudness normalisation: explicit RMS target, then an explicit ceiling.
    level = rms(mix)
    if level > 1e-9:
        gain = 10 ** ((TARGET_RMS_DBFS - dbfs(level)) / 20.0)
        gain = min(gain, 10 ** ((PEAK_CEILING_DBFS - dbfs(float(np.abs(mix).max()))) / 20.0))
        gain = min(gain, 20.0)  # never amplify noise into a wall of hiss
        mix = mix * gain
    peak = float(np.abs(mix).max())
    if peak > 10 ** (PEAK_CEILING_DBFS / 20.0):
        mix = mix * (10 ** (PEAK_CEILING_DBFS / 20.0) / peak)

    tail = int(1.5 * rate)  # the film ends on a card; let the sound breathe out
    mix[-tail:] *= np.linspace(1.0, 0.0, tail, dtype=np.float32)[:, None]
    mix[: int(0.05 * rate)] *= np.linspace(0.0, 1.0, int(0.05 * rate), dtype=np.float32)[:, None]

    output.parent.mkdir(parents=True, exist_ok=True)
    interleaved = np.clip(mix, -1.0, 1.0)
    with wave.open(str(output), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(np.int16(interleaved * 32767.0).tobytes())

    report = measure(output, rate=rate, chapters=narration)
    report.update({
        "target_rms_dbfs": TARGET_RMS_DBFS,
        "peak_ceiling_dbfs": PEAK_CEILING_DBFS,
        "voice_level": VOICE_LEVEL,
        "bgm_level": BGM_LEVEL,
        "sfx_level": SFX_LEVEL,
        "duck_depth": DUCK_DEPTH,
        "applied_rms_dbfs": dbfs(rms(mix)),
        "output": output.name,
    })
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    assert_audible(report)
    return report


def measure(path: Path, rate: int = RATE, chapters=None,
            window: float = 1.0) -> dict:
    """Measure a media file's real audio: overall level, per-chapter level, silence."""
    samples = decode(path, rate, 1)[:, 0]
    step = int(window * rate)
    windows = [rms(samples[i:i + step]) for i in range(0, len(samples), step) if len(samples[i:i + step])]
    overall = rms(samples)
    silent = sum(1 for value in windows if dbfs(value) < SILENCE_THRESHOLD_DBFS)
    report = {
        "file": Path(path).name,
        "duration_seconds": round(len(samples) / rate, 3),
        "sample_rate": rate,
        "channels": 1,
        "rms_dbfs": dbfs(overall),
        "peak_dbfs": dbfs(float(np.abs(samples).max())),
        "window_seconds": window,
        "silent_windows": silent,
        "window_count": len(windows),
        "silent_fraction": round(silent / max(1, len(windows)), 4),
        "quietest_window_dbfs": min((dbfs(value) for value in windows), default=-120.0),
        "chapters": [],
    }
    for row in chapters or []:
        start = int(float(row["start"]) * rate)
        end = int(float(row["end"]) * rate)
        block = samples[start:end]
        report["chapters"].append({
            "id": row.get("id", "?"),
            "start": round(float(row["start"]), 3),
            "end": round(float(row["end"]), 3),
            "rms_dbfs": dbfs(rms(block)),
            "peak_dbfs": dbfs(float(np.abs(block).max())) if block.size else -120.0,
        })
    return report


def assert_audible(report: dict) -> None:
    """Fail loudly instead of shipping a silent film."""
    problems = []
    if report["rms_dbfs"] < MIN_MIX_RMS_DBFS:
        problems.append(f"overall mix is {report['rms_dbfs']} dBFS RMS "
                        f"(minimum {MIN_MIX_RMS_DBFS})")
    # Crest factor separates real audio from a constant/DC-ish signal. Real
    # speech sits near 10 dB; a pure tone is 3 dB; silence or DC is 0 dB.
    crest = report["peak_dbfs"] - report["rms_dbfs"]
    if crest < MIN_CREST_DB:
        problems.append(f"crest factor is only {crest:.1f} dB (minimum {MIN_CREST_DB})")
    if report["silent_fraction"] > MAX_SILENT_FRACTION:
        problems.append(f"{report['silent_fraction']:.1%} of the timeline is silent")
    for chapter in report["chapters"]:
        if chapter["rms_dbfs"] < MIN_CHAPTER_RMS_DBFS:
            problems.append(f"chapter {chapter['id']} is {chapter['rms_dbfs']} dBFS RMS "
                            f"(minimum {MIN_CHAPTER_RMS_DBFS})")
    if problems:
        raise AudioBuildError("Soundtrack is not audibly mixed: " + "; ".join(problems))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the measured soundtrack")
    parser.add_argument("--project", type=Path, default=HERE / "story.json")
    parser.add_argument("--audio", type=Path, default=HERE / "audio")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--duration", type=float, default=180.0)
    args = parser.parse_args()

    sys.path.insert(0, str(HERE))
    import render  # noqa: WPS433 (local import: heavy optional dependencies)

    project = json.loads(args.project.read_text(encoding="utf-8"))
    manifest = json.loads((args.audio / "manifest.json").read_text(encoding="utf-8"))
    args.work.mkdir(parents=True, exist_ok=True)
    narration, _ = render.audio_layout(project["chapters"], args.audio, args.work, manifest)
    edl = render.make_edl(project, narration)

    sys.path.insert(0, str(HERE.parents[1] / "电影解说工具包"))
    from generate_horror_bgm import generate_horror_bgm

    music = args.work / "score.wav"
    generate_horror_bgm(music, args.duration)
    effects = args.work / "effects.wav"
    render.write_sfx(effects, edl)

    report = build_soundtrack(narration, music, effects, args.output,
                              duration=args.duration,
                              report_path=args.report or args.work / "audio-report.json")
    print("SOUNDTRACK_OK " + json.dumps({
        "rms_dbfs": report["rms_dbfs"], "peak_dbfs": report["peak_dbfs"],
        "silent_fraction": report["silent_fraction"],
        "chapters": {c["id"]: c["rms_dbfs"] for c in report["chapters"]},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
