#!/usr/bin/env python3
"""Generate one original, low-volume crime-thriller music loop."""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44_100


def generate_horror_bgm(output: Path, duration: float) -> None:
    """Write one stereo PCM loop with drone, pulse, texture, and impacts."""
    output.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260829)
    total_samples = int(math.ceil(duration * SAMPLE_RATE))
    chunk_samples = SAMPLE_RATE
    noise_state = 0.0
    impact_times = [
        duration * ratio
        for ratio in (0.00, 0.10, 0.22, 0.36, 0.50, 0.64, 0.77, 0.88, 0.95)
    ]

    with wave.open(str(output), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)

        written = 0
        while written < total_samples:
            count = min(chunk_samples, total_samples - written)
            t = (written + np.arange(count, dtype=np.float64)) / SAMPLE_RATE

            # Slow dissonant drone and subtle high tension layer.
            lfo = 0.62 + 0.24 * np.sin(2 * np.pi * 0.031 * t)
            drone = (
                0.23 * np.sin(2 * np.pi * 41.20 * t)
                + 0.14 * np.sin(2 * np.pi * 55.00 * t + 0.7)
                + 0.07 * np.sin(2 * np.pi * 82.41 * t + 1.3)
            ) * lfo
            tension = (
                0.035 * np.sin(2 * np.pi * 220.0 * t)
                + 0.032 * np.sin(2 * np.pi * 233.08 * t + 0.4)
            ) * (0.45 + 0.35 * np.sin(2 * np.pi * 0.017 * t))

            # A restrained heartbeat-like pulse for crime-thriller momentum.
            beat = np.mod(t, 0.78)
            pulse = 0.18 * np.sin(2 * np.pi * 47.0 * t) * np.exp(-beat * 8.5)

            # Low-passed noise texture, generated continuously across chunks.
            raw_noise = rng.normal(0.0, 1.0, count)
            texture = np.empty(count, dtype=np.float64)
            state = noise_state
            for index, sample in enumerate(raw_noise):
                state = 0.992 * state + 0.008 * sample
                texture[index] = state
            noise_state = state
            texture *= 0.12

            impacts = np.zeros(count, dtype=np.float64)
            for impact in impact_times:
                delta = t - impact
                mask = (delta >= 0) & (delta < 2.2)
                if np.any(mask):
                    impacts[mask] += (
                        0.28
                        * np.sin(2 * np.pi * (52.0 - 10.0 * delta[mask]) * delta[mask])
                        * np.exp(-delta[mask] * 2.2)
                    )

            # Let the single loop rise gently before returning to its seam.
            progress = t / max(duration, 1.0)
            intensity = 0.62 + 0.16 * np.sin(np.pi * progress) ** 2
            signal = (drone + pulse + tension + texture + impacts) * intensity

            # Gentle fades prevent clicks at the beginning and end.
            fade_in = np.clip(t / 1.5, 0, 1)
            fade_out = np.clip((duration - t) / 1.5, 0, 1)
            signal *= np.minimum(fade_in, fade_out)
            signal = np.tanh(signal * 1.25) * 0.72

            # Slight stereo movement while keeping the center clear for narration.
            pan = 0.08 * np.sin(2 * np.pi * 0.023 * t)
            left = signal * (1.0 - pan)
            right = signal * (1.0 + pan)
            stereo = np.column_stack((left, right))
            pcm = np.clip(stereo * 32767.0, -32768, 32767).astype("<i2")
            handle.writeframes(pcm.tobytes())
            written += count

    print(f"Generated original thriller music loop: {output} ({duration:.2f}s)", flush=True)
