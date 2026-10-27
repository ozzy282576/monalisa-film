#!/usr/bin/env python3
"""调整 TTS 语速、收紧过长停顿，并按台词对齐指定的半秒叙事停顿。

TTS 原始片段保留在 ``audio/raw/``。本片试听声线的自然语速快于目标约每秒3.7个汉字，
先用保音高的 ``atempo=0.80`` 放慢，再收紧句内过长静音；只改变时间，不增删台词。
render.py 将对齐后总时长微调至 168 秒可用旁白窗口，闸门范围为 0.86–1.10。

- 静音判定：48 kHz 单声道，10 ms 块 RMS < 0.01；
- 片头静音留 ``LEAD``，片尾留 ``TRAIL``；普通句间静音上限为 ``CAP``；
- 指定短语后的停顿保留或补足到约 0.5 秒；若该短语位于末句且 TTS 没有停顿，
  在片段末尾补足，不会挪动或覆盖任何口播；
- 输出 48 kHz 单声道 192 kbps MP3；原始 TTS 永远保留作来源，manifest 记录处理后文件的 SHA-256。

用法::

    python3 production/chessboard64/tighten_pauses.py            # raw/ -> audio/，并打印每段时长
    python3 production/chessboard64/tighten_pauses.py --report   # 只报告，不写文件
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
CAP = 0.35           # 普通句内停顿上限
SPECIAL_PAUSE = 0.5
PACE_FACTOR = 0.80   # 保音高减速；按已试听的约4.6字/秒声音调至目标约3.7字/秒
XFADE = 240          # 5 ms


def decode(path: Path) -> np.ndarray:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
        check=True, capture_output=True)
    return np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768


def pace(x: np.ndarray, factor: float = PACE_FACTOR) -> np.ndarray:
    """用 ffmpeg atempo 保留音高地放慢 TTS，输入/输出均为 48 kHz 单声道 PCM。"""
    if not 0.5 <= factor <= 2.0:
        raise ValueError('ffmpeg atempo factor must be between 0.5 and 2.0')
    pcm = np.int16(np.clip(x, -1, 1) * 32767).astype('<i2').tobytes()
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0",
         "-af", f"atempo={factor:.6f}", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "pipe:1"],
        input=pcm, check=True, capture_output=True)
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


def tighten(x: np.ndarray, special_pause_starts=()):
    spans = silences(x)
    keep_from = 0
    pieces = []
    cuts = []
    preserved = []
    total = len(x)
    special_applied = False
    append_end_pause = any(p >= total / RATE - 0.04 for p in special_pause_starts)
    for a, b in spans:
        length = b - a
        special = next((p for p in special_pause_starts if abs(a / RATE - p) <= 0.04), None)
        if special is not None:
            special_applied = True
        if a == 0:                                  # 片头
            allowed = int(LEAD * RATE)
        elif special is not None:                   # 指定短语后的叙事停顿
            allowed = int(SPECIAL_PAUSE * RATE)
        elif b >= total:                            # 片尾
            allowed = int(TRAIL * RATE)
        else:
            allowed = int(CAP * RATE)
        if special is not None and length < allowed:
            # 若指定句尾几乎不停顿，只在已检测静音段之后补足；绝不覆盖口播。
            padding = allowed - length
            pieces.append(x[keep_from:b])
            pieces.append(np.zeros(padding, dtype=np.float32))
            keep_from = b
            preserved.append({'start': round(a / RATE, 3), 'source_seconds': round(length / RATE, 3),
                              'kept_seconds': round(allowed / RATE, 3),
                              'inserted_seconds': round(padding / RATE, 3)})
            continue
        if length <= allowed:
            if special is not None:
                preserved.append({'start': round(a / RATE, 3), 'source_seconds': round(length / RATE, 3),
                                  'kept_seconds': round(length / RATE, 3), 'inserted_seconds': 0.0})
            continue
        excess = length - allowed
        cut_a = a + (length - excess) // 2
        cut_b = cut_a + excess
        pieces.append(x[keep_from:cut_a])
        keep_from = cut_b
        cuts.append((a / RATE, length / RATE, allowed / RATE))
        if special is not None:
            preserved.append({'start': round(a / RATE, 3), 'source_seconds': round(length / RATE, 3),
                              'kept_seconds': round(allowed / RATE, 3), 'inserted_seconds': 0.0})
    pieces.append(x[keep_from:])
    out = pieces[0].copy()
    ramp = np.linspace(0, 1, XFADE, dtype=np.float32)
    for piece in pieces[1:]:
        if len(out) >= XFADE and len(piece) >= XFADE:
            out[-XFADE:] = out[-XFADE:] * (1 - ramp) + piece[:XFADE] * ramp
            out = np.concatenate([out, piece[XFADE:]])
        else:
            out = np.concatenate([out, piece])
    if append_end_pause and not special_applied:
        pause_samples = round(SPECIAL_PAUSE * RATE)
        out = np.concatenate([out, np.zeros(pause_samples, dtype=np.float32)])
        preserved.append({'start': round(total / RATE, 3), 'source_seconds': 0.0,
                          'kept_seconds': SPECIAL_PAUSE, 'inserted_seconds': SPECIAL_PAUSE,
                          'appended_after_clip': True})
    return out, cuts, preserved


def explicit_pause_start(chapter_id: str, text: str, samples: np.ndarray, targets: dict) -> tuple[float | None, str | None]:
    """用原始 TTS 的静音窗对齐用户指定的半秒叙事停顿，不靠盲目插入固定时间码。"""
    phrase = targets.get(chapter_id) if isinstance(targets, dict) else None
    if not isinstance(phrase, str) or not phrase:
        return None, None
    try:
        import clause_times
        _duration, clauses = clause_times.align(text, samples)
        matches = [row for row in clauses if phrase in row.get('text', '')]
        if not matches:
            return None, f'{chapter_id}: 台词里找不到指定停顿词「{phrase}」'
        target = float(matches[-1]['end'])
        _lead, pauses = clause_times.pauses(samples, min_len=0.01)
        if pauses:
            start, length = min(pauses, key=lambda p: abs(p[0] - target))
            if abs(start - target) <= 0.32:
                return float(start), None
        # 若目标短语本身就是末句，宁可在片尾补足静音，也不把停顿挪到较早的句子间。
        if matches[-1].get('i') == len(clauses) - 1:
            trailing = [(start, length) for start, length in pauses
                        if start + length >= len(samples) / RATE - 0.04]
            if trailing:
                return float(trailing[-1][0]), None
            return len(samples) / RATE, None
        if not pauses:
            return None, f'{chapter_id}: 「{phrase}」后没有检测到可保留的停顿窗'
        start, _length = min(pauses, key=lambda p: abs(p[0] - target))
        return None, f'{chapter_id}: 「{phrase}」后的最近停顿偏离 {abs(start-target):.2f}s，未盲目移动停顿'
    except Exception as exc:
        return None, f'{chapter_id}: 半秒停顿对齐失败：{type(exc).__name__}: {exc}'


def encode(x: np.ndarray, path: Path):
    tmp = path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(RATE)
        f.writeframes(np.int16(np.clip(x, -1, 1) * 32767).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ac", "1", "-ar", str(RATE),
                    "-c:a", "libmp3lame", "-b:a", "192k", "-map_metadata", "-1", "-fflags", "+bitexact",
                    "-flags:a", "+bitexact", str(path)], check=True)
    tmp.unlink()


def update_manifest() -> None:
    """收紧后的 N0x.mp3 才是渲染/字幕/听检的输入，manifest 的 SHA-256 必须记它。"""
    import hashlib
    manifest_path = OUT / 'manifest.json'
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    changed = 0
    for clip in manifest.get('clips', []):
        path = OUT / clip['file']
        if not path.exists():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if clip.get('sha256') != digest:
            clip['sha256'] = digest
            changed += 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'audio/manifest.json 已更新 {changed} 条的 SHA-256（记的是收紧后的文件）')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", action="store_true", help="只报告不写文件")
    parser.add_argument("--pace-factor", type=float, default=PACE_FACTOR,
                        help="ffmpeg atempo factor; lower is slower (default: %(default)s)")
    args = parser.parse_args(argv)
    if not RAW.is_dir():
        raise SystemExit(f"缺少原始配音目录 {RAW}（把 TTS 原文件放进去再跑）")
    story = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
    chapters = {row["id"]: row["text"] for row in story.get("chapters", [])}
    targets = (story.get("presentation") or {}).get("explicit_pause_after") or {}
    summary = []
    source_total = paced_total = after = 0.0
    warnings = []
    for raw in sorted(RAW.glob("N0*.mp3")):
        source = decode(raw)
        x = pace(source, args.pace_factor)
        special_start, warning = explicit_pause_start(raw.stem, chapters.get(raw.stem, ""), x, targets)
        if warning:
            warnings.append(warning)
            print("SPECIAL_PAUSE_WARNING " + warning)
        y, cuts, preserved = tighten(x, [special_start] if special_start is not None else ())
        phrase = targets.get(raw.stem) if isinstance(targets, dict) else None
        if phrase and special_start is not None and not preserved:
            warning = f'{raw.stem}: 指定停顿「{phrase}」未找到或补足，未确认达到0.5秒'
            warnings.append(warning)
            print("SPECIAL_PAUSE_WARNING " + warning)
        source_s, paced_s, tight_s = len(source) / RATE, len(x) / RATE, len(y) / RATE
        source_total += source_s; paced_total += paced_s; after += tight_s
        row = {"id": raw.stem, "source_seconds": round(source_s, 3),
               "paced_seconds": round(paced_s, 3), "tight_seconds": round(tight_s, 3),
               "pauses_tightened": len(cuts), "seconds_removed": round(paced_s - tight_s, 3),
               "special_pause_after": phrase, "special_pause": preserved}
        summary.append(row)
        print(f"{raw.stem}: {source_s:6.2f}s -> {paced_s:6.2f}s paced -> {tight_s:6.2f}s tightened "
              f"({len(cuts)} 处停顿收紧；特殊停顿{len(preserved)}处)")
        if not args.report:
            encode(y, OUT / raw.name)
    usable = 180 - 0.6 - 6.0 - 1.08 * 5
    tempo_after = after / usable
    char_count = sum(1 for text in chapters.values() for ch in text if ch == '\u3007' or '\u3400' <= ch <= '\u9fff')
    effective_rate = char_count / after if after else 0.0
    print(f"合计原始 {source_total:.2f}s -> 调速 {paced_total:.2f}s -> 收紧 {after:.2f}s；"
          f"有效语速 {effective_rate:.2f} 汉字/秒；render.py 可用 {usable:.1f}s，后续变速比 {tempo_after:.3f}（允许 0.86–1.10）")
    if not 0.86 <= tempo_after <= 1.10:
        warning = f'收紧后时长与168秒旁白窗口不匹配：tempo={tempo_after:.3f}'
        warnings.append(warning)
        print("AUDIO_TEMPO_WARNING " + warning)
    if not args.report:
        (OUT / "tighten-report.json").write_text(json.dumps(
            {"parameters": {"rate": RATE, "hop": HOP, "threshold_rms": THRESHOLD, "lead": LEAD,
                            "trail": TRAIL, "cap": CAP, "special_pause_seconds": SPECIAL_PAUSE,
                            "pace_factor": args.pace_factor, "crossfade_samples": XFADE},
             "clips": summary, "warnings": warnings,
             "total_source_seconds": round(source_total, 3),
             "total_paced_seconds": round(paced_total, 3),
             "total_tight_seconds": round(after, 3),
             "effective_chinese_chars_per_second": round(effective_rate, 4),
             "tempo_after": round(tempo_after, 4)}, ensure_ascii=False, indent=2) + "\n")
        update_manifest()
    return 0


if __name__ == "__main__":
    sys.exit(main())
