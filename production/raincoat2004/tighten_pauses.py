#!/usr/bin/env python3
"""把 TTS 原始配音里过长的停顿收紧，得到抖音节奏的解说轨（逐字不动）。

背景（2026-09-21 实测）：voice-00 念这六段一共 201.7 秒，其中 ≥0.35 秒的句间停顿
就占了 51 秒——它在逗号、破折号后动辄停 0.8～1.2 秒。render.py 允许的整体变速只有
±10%（`audio_layout` 的 0.86–1.10 闸门），光靠变速塞不进 168 秒的可用时长，
硬变速 1.2 倍又会把人声压得发飘。抖音口播本来就不该有一秒多的空拍，
所以这里**只剪静音、不动一个字**：

- 静音判定：48 kHz 单声道，10 ms 块 RMS < 0.01；
- 片头静音留 `LEAD`，片尾留 `TRAIL`；
- 句内任何 ≥ `CAP` 的静音，从中间剪掉多出来的部分，只留 `CAP`；
  剪口都在静音里，再加 5 ms 交叉淡化，不会有咔哒声；
- 输出 48 kHz 单声道 192 kbps mp3，同样的输入永远得到同样的字节。

原始 TTS 文件保留在 `audio/raw/`，`audio/N0x.mp3` 是收紧后的版本，
`audio/manifest.json` 里的 SHA-256 记的是收紧后的文件——渲染、字幕对轨、
逐字听检全部以它为准。

用法::

    python3 production/raincoat2004/tighten_pauses.py            # raw/ -> audio/，并打印每段前后时长
    python3 production/raincoat2004/tighten_pauses.py --report   # 只报告，不写文件
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RAW = HERE / "audio" / "raw"
OUT = HERE / "audio"
RATE = 48000
HOP = 480            # 10 ms
THRESHOLD = 0.01     # RMS
LEAD = 0.15
TRAIL = 0.25
CAP = 0.35           # 句内停顿上限
XFADE = 240          # 5 ms


def decode(path: Path) -> np.ndarray:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
        check=True, capture_output=True)
    return np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768


def silences(x: np.ndarray):
    """返回 [(start_sample, end_sample)]，只含 ≥ CAP 的静音段（含首尾）。"""
    n = len(x) // HOP * HOP
    rms = np.sqrt((x[:n].reshape(-1, HOP) ** 2).mean(axis=1))
    quiet = rms < THRESHOLD
    spans = []
    start = None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        if not q and start is not None:
            spans.append((start * HOP, i * HOP))
            start = None
    if start is not None:
        spans.append((start * HOP, len(x)))
    return spans


def tighten(x: np.ndarray):
    spans = silences(x)
    keep_from = 0
    pieces = []
    cuts = []
    total = len(x)
    for a, b in spans:
        length = b - a
        if a == 0:                                  # 片头
            allowed = int(LEAD * RATE)
        elif b >= total:                            # 片尾
            allowed = int(TRAIL * RATE)
        else:
            allowed = int(CAP * RATE)
        if length <= allowed:
            continue
        excess = length - allowed
        # 从静音段中间剪掉 excess 个采样
        cut_a = a + (length - excess) // 2
        cut_b = cut_a + excess
        pieces.append(x[keep_from:cut_a])
        keep_from = cut_b
        cuts.append((a / RATE, length / RATE, allowed / RATE))
    pieces.append(x[keep_from:])
    # 交叉淡化拼接
    out = pieces[0].copy()
    ramp = np.linspace(0, 1, XFADE, dtype=np.float32)
    for piece in pieces[1:]:
        if len(out) >= XFADE and len(piece) >= XFADE:
            out[-XFADE:] = out[-XFADE:] * (1 - ramp) + piece[:XFADE] * ramp
            out = np.concatenate([out, piece[XFADE:]])
        else:
            out = np.concatenate([out, piece])
    return out, cuts


def encode(x: np.ndarray, path: Path):
    tmp = path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(RATE)
        f.writeframes(np.int16(np.clip(x, -1, 1) * 32767).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ac", "1", "-ar", str(RATE),
                    "-c:a", "libmp3lame", "-b:a", "192k", "-map_metadata", "-1", "-fflags", "+bitexact",
                    "-flags:a", "+bitexact", str(path)], check=True)
    tmp.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", action="store_true", help="只报告不写文件")
    args = parser.parse_args(argv)
    if not RAW.is_dir():
        raise SystemExit(f"缺少原始配音目录 {RAW}（把 TTS 原文件放进去再跑）")
    summary = []
    before = after = 0.0
    for raw in sorted(RAW.glob("N0*.mp3")):
        x = decode(raw)
        y, cuts = tighten(x)
        before += len(x) / RATE; after += len(y) / RATE
        summary.append({"id": raw.stem, "raw_seconds": round(len(x) / RATE, 3),
                        "tight_seconds": round(len(y) / RATE, 3), "pauses_tightened": len(cuts),
                        "seconds_removed": round((len(x) - len(y)) / RATE, 3)})
        print(f"{raw.stem}: {len(x)/RATE:6.2f}s -> {len(y)/RATE:6.2f}s  ({len(cuts)} 处停顿收紧)")
        if not args.report:
            encode(y, OUT / raw.name)
    usable = 180 - 0.6 - 6.0 - 1.08 * 5
    print(f"合计 {before:.2f}s -> {after:.2f}s；render.py 可用 {usable:.1f}s，变速比 {after/usable:.3f}（允许 0.86–1.10）")
    if not args.report:
        (OUT / "tighten-report.json").write_text(json.dumps(
            {"parameters": {"rate": RATE, "hop": HOP, "threshold_rms": THRESHOLD, "lead": LEAD,
                            "trail": TRAIL, "cap": CAP, "crossfade_samples": XFADE},
             "clips": summary, "total_raw_seconds": round(before, 3), "total_tight_seconds": round(after, 3),
             "tempo_after": round(after / usable, 4)}, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
