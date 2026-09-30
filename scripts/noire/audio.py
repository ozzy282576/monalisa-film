"""Procedural sound design.

No licensed audio is bundled: every effect below is synthesised from noise and
oscillators with numpy, so the finished video carries no third-party rights.
Subtitles and composition are what the look depends on; these cues only support
them, so they stay low in the mix under the narration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

SAMPLE_RATE = 44100

Cue = Tuple[str, float]  # (effect name, start seconds)


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------


def _t(duration: float) -> np.ndarray:
    return np.arange(int(duration * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE


def _noise(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.standard_normal(n).astype(np.float32)


def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """FFT brickwall-ish lowpass; cheap and clean for one-shot effects."""
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / SAMPLE_RATE)
    spectrum *= 1.0 / (1.0 + (freqs / max(1.0, cutoff)) ** 2)
    return np.fft.irfft(spectrum, n=x.size).astype(np.float32)


def _highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / SAMPLE_RATE)
    spectrum *= (freqs / max(1.0, cutoff)) ** 2 / (1.0 + (freqs / max(1.0, cutoff)) ** 2)
    return np.fft.irfft(spectrum, n=x.size).astype(np.float32)


def _bandpass(x: np.ndarray, low: float, high: float) -> np.ndarray:
    return _highpass(_lowpass(x, high), low)


def _envelope(n: int, attack: float, decay: float, curve: float = 2.0) -> np.ndarray:
    a = max(1, int(attack * SAMPLE_RATE))
    d = max(1, n - a)
    env = np.empty(n, dtype=np.float32)
    env[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32) ** 0.7
    env[a:] = (1.0 - np.linspace(0.0, 1.0, d, dtype=np.float32)) ** curve
    return env


def _decay(n: int, tau: float) -> np.ndarray:
    """Exponential decay envelope of ``n`` samples with time constant ``tau``."""
    return np.exp(-np.arange(n, dtype=np.float32) / (tau * SAMPLE_RATE)).astype(np.float32)


# --------------------------------------------------------------------------
# effects
# --------------------------------------------------------------------------


def rain(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    hiss = _highpass(_noise(rng, n), 900.0)
    body = _bandpass(_noise(rng, n), 200.0, 1800.0)
    swell = 0.75 + 0.25 * np.sin(_t(duration)[:n] * 0.7)
    out = (hiss * 0.35 + body * 0.65) * swell
    return out * 0.55


def thunder(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    rumble = _lowpass(_noise(rng, n), 90.0) * 6.0
    crack = _bandpass(_noise(rng, n), 300.0, 3500.0) * 0.45
    env = _envelope(n, 0.012, duration - 0.012, curve=1.4)
    return (rumble + crack) * env * 0.9


def siren(duration: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(duration)
    sweep = 0.5 + 0.5 * np.sin(2.0 * np.pi * 0.32 * t)
    freq = 640.0 + 420.0 * sweep
    phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    tone = np.sin(phase) + 0.35 * np.sin(2.0 * phase)
    distance = np.clip(t / max(0.001, duration * 0.7), 0.0, 1.0)
    env = _envelope(len(t), 0.35, duration - 0.35, curve=1.1)
    return tone * env * 0.32 * (0.35 + 0.65 * (1.0 - distance))


def clock_tick(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    period = int(0.85 * SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    click = _bandpass(_noise(rng, 1400), 1400.0, 5200.0) * _decay(1400, 0.010)
    for index, start in enumerate(range(0, n, period)):
        length = min(click.size, n - start)
        gain = 1.0 if index % 2 == 0 else 0.72
        out[start:start + length] += click[:length] * gain
    return out * 0.5


def shutter(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    snap = _bandpass(_noise(rng, 2200), 1200.0, 7000.0) * _decay(2200, 0.006)
    clack = _bandpass(_noise(rng, 4400), 500.0, 3000.0) * _decay(4400, 0.020)
    out[:snap.size] += snap * 0.9
    offset = int(0.055 * SAMPLE_RATE)
    if offset + clack.size <= n:
        out[offset:offset + clack.size] += clack * 0.7
    return out * 0.8


def friction(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    body = _bandpass(_noise(rng, n), 180.0, 1500.0)
    wobble = 0.6 + 0.4 * np.sin(_t(duration)[:n] * 12.0)
    env = _envelope(n, 0.05, duration - 0.05, curve=1.2)
    return body * wobble * env * 0.4


def heartbeat(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    thump_len = int(0.28 * SAMPLE_RATE)
    t = _t(thump_len / SAMPLE_RATE)
    thump = np.sin(2.0 * np.pi * 52.0 * t) * np.exp(-t * 17.0)
    for start in range(0, n, int(0.86 * SAMPLE_RATE)):
        for offset, gain in ((0, 1.0), (int(0.17 * SAMPLE_RATE), 0.66)):
            begin = start + offset
            if begin + thump_len > n:
                continue
            out[begin:begin + thump_len] += thump * gain
    return out * 0.85


def thud(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    t = _t(duration)[:n]
    body = np.sin(2.0 * np.pi * 62.0 * t) * np.exp(-t * 12.0)
    dirt = _lowpass(_noise(rng, n), 500.0) * np.exp(-t * 26.0) * 0.5
    return (body + dirt) * 0.9


def strings_swell(duration: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(duration)
    out = np.zeros_like(t)
    for detune, gain in ((0.0, 1.0), (0.7, 0.55), (-0.9, 0.5), (1.6, 0.3)):
        freq = 196.0 + detune
        vibrato = 1.0 + 0.004 * np.sin(2.0 * np.pi * 5.1 * t)
        phase = 2.0 * np.pi * np.cumsum(freq * vibrato) / SAMPLE_RATE
        out += gain * (np.sin(phase) + 0.4 * np.sin(2.0 * phase) + 0.18 * np.sin(3.0 * phase))
    env = _envelope(len(t), duration * 0.45, duration * 0.55, curve=1.0)
    return out * env * 0.10


def ding(duration: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(duration)
    out = np.zeros_like(t)
    for harmonic, gain, tau in ((1.0, 1.0, 0.9), (2.76, 0.5, 0.55), (5.4, 0.22, 0.3)):
        out += gain * np.sin(2.0 * np.pi * 880.0 * harmonic * t) * np.exp(-t / tau)
    return out * 0.4


def glass_break(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    t = _t(duration)[:n]
    shards = _bandpass(_noise(rng, n), 2500.0, 9000.0) * np.exp(-t * 9.0)
    ring = np.zeros_like(t)
    for freq, gain in ((3100.0, 0.5), (4700.0, 0.35), (6300.0, 0.22)):
        ring += gain * np.sin(2.0 * np.pi * freq * t) * np.exp(-t * 7.0)
    return (shards * 0.8 + ring) * 0.55


def rumble(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    body = _lowpass(_noise(rng, n), 70.0) * 5.0
    env = _envelope(n, duration * 0.25, duration * 0.75, curve=1.3)
    return body * env * 0.5


def piano(duration: float, rng: np.random.Generator) -> np.ndarray:
    """Soft repeated piano-ish figure for the closing beat."""
    n = int(duration * SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    notes = (261.63, 329.63, 392.00, 523.25)
    step = int(0.62 * SAMPLE_RATE)
    voice_len = int(1.7 * SAMPLE_RATE)
    t = _t(voice_len / SAMPLE_RATE)
    for index, start in enumerate(range(0, n, step)):
        freq = notes[index % len(notes)]
        partials = (
            np.sin(2.0 * np.pi * freq * t) * 1.0
            + 0.34 * np.sin(2.0 * np.pi * 2 * freq * t)
            + 0.14 * np.sin(2.0 * np.pi * 3 * freq * t)
        )
        voice = partials * np.exp(-t * 2.1)
        length = min(voice_len, n - start)
        out[start:start + length] += voice[:length] * 0.18
    return out


def gavel(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    for offset in (0.0, 0.19):
        start = int(offset * SAMPLE_RATE)
        length = min(int(0.5 * SAMPLE_RATE), n - start)
        if length <= 0:
            continue
        t = np.arange(length, dtype=np.float32) / SAMPLE_RATE
        knock = (
            np.sin(2.0 * np.pi * 185.0 * t) * np.exp(-t * 30.0)
            + 0.5 * np.sin(2.0 * np.pi * 430.0 * t) * np.exp(-t * 45.0)
            + _lowpass(_noise(rng, length), 2500.0) * np.exp(-t * 55.0) * 0.6
        )
        out[start:start + length] += knock.astype(np.float32)
    return out * 0.85


def impact(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    t = _t(duration)[:n]
    hit = np.sin(2.0 * np.pi * 44.0 * t) * np.exp(-t * 16.0)
    snap = _bandpass(_noise(rng, n), 200.0, 4000.0) * np.exp(-t * 30.0)
    return (hit + snap * 0.5) * 0.85


def whoosh(duration: float, rng: np.random.Generator) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    t = _t(duration)[:n]
    swept = _bandpass(_noise(rng, n), 150.0, 900.0)
    env = np.sin(np.pi * np.clip(t / max(0.001, duration), 0.0, 1.0)) ** 2
    return swept * env * 0.45


GENERATORS = {
    "rain": rain,
    "thunder": thunder,
    "siren": siren,
    "clock": clock_tick,
    "shutter": shutter,
    "friction": friction,
    "heartbeat": heartbeat,
    "thud": thud,
    "strings": strings_swell,
    "ding": ding,
    "glass": glass_break,
    "rumble": rumble,
    "piano": piano,
    "gavel": gavel,
    "impact": impact,
    "whoosh": whoosh,
}

TYPICAL_LENGTH = {
    "rain": 6.0, "thunder": 3.4, "siren": 5.0, "clock": 6.0, "shutter": 0.6,
    "friction": 0.9, "heartbeat": 4.0, "thud": 1.1, "strings": 4.5, "ding": 1.6,
    "glass": 2.0, "rumble": 4.0, "piano": 7.0, "gavel": 1.6, "impact": 1.0,
    "whoosh": 0.9,
}

SFX_GAIN = {
    "rain": 0.30, "thunder": 0.42, "siren": 0.30, "clock": 0.22, "shutter": 0.30,
    "friction": 0.26, "heartbeat": 0.34, "thud": 0.40, "strings": 0.30,
    "ding": 0.26, "glass": 0.34, "rumble": 0.28, "piano": 0.24, "gavel": 0.36,
    "impact": 0.40, "whoosh": 0.28,
}


# --------------------------------------------------------------------------
# timeline
# --------------------------------------------------------------------------


@dataclass
class AudioPlan:
    total_seconds: float
    voice: List[Tuple[Path, float]] = field(default_factory=list)
    cues: List[Cue] = field(default_factory=list)
    bgm: List[Tuple[str, float, float]] = field(default_factory=list)


def _place(track: np.ndarray, clip: np.ndarray, start_seconds: float, gain: float) -> None:
    start = int(start_seconds * SAMPLE_RATE)
    if start >= track.size:
        return
    length = min(clip.size, track.size - start)
    if length <= 0:
        return
    track[start:start + length] += clip[:length] * gain


def load_audio(path: Path) -> np.ndarray:
    """Load any ffmpeg-readable file as mono float32 at SAMPLE_RATE."""
    import subprocess

    from .encoder import find_ffmpeg

    result = subprocess.run(
        [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1",
         "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True,
    )
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def build(plan: AudioPlan, seed: int = 7) -> np.ndarray:
    """Render the full mix as mono float32 in -1..1."""
    total = int(plan.total_seconds * SAMPLE_RATE)
    mix = np.zeros(total, dtype=np.float32)
    rng = np.random.default_rng(seed)

    for name, start, duration in plan.bgm:
        generator = GENERATORS.get(name)
        if generator:
            _place(mix, generator(duration, rng), start, SFX_GAIN.get(name, 0.25))

    for name, start in plan.cues:
        generator = GENERATORS.get(name)
        if not generator:
            continue
        if name == "rain":
            continue  # handled as a bed
        clip = generator(TYPICAL_LENGTH.get(name, 2.0), rng)
        _place(mix, clip, start, SFX_GAIN.get(name, 0.3))

    for path, start in plan.voice:
        if not Path(path).exists():
            continue
        clip = load_audio(Path(path))
        peak = float(np.max(np.abs(clip))) or 1.0
        _place(mix, clip / peak * 0.92, start, 1.0)

    peak = float(np.max(np.abs(mix)))
    if peak > 0.99:
        mix *= 0.99 / peak
    return mix


def write_wav(path: Path, samples: np.ndarray) -> None:
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(samples, -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
