#!/usr/bin/env python3
"""成片审片工具：把"逐帧审片"里能自动化的部分做掉，并独立复测音频电平。

用法::

    python3 production/review_film.py --film 交付/黑色大丽花_三分钟_带声音.mp4 \
        --project production/dahlia --work work/dahlia/review

产出：

* ``film-review.json`` —— 容器信息、逐帧亮度、冻结帧/黑帧、静音窗口、逐章电平；
* ``frames/*.jpg`` —— 每 ``--every`` 秒一帧，供人工看片；
* ``contact-sheet-*.png`` —— 抽样帧拼成的对照表，一屏看完。

冻结帧报警分两步：先用 16x16 签名把"1 秒内几乎没变"的片段全部抓出来（宁可多报），
再用 64x64 签名复核，给每段打上 ``verdict``：``static`` 是真静止（信息卡、档案照、
片尾卡，本来就该静止），``micro_motion`` 是慢速运镜被严阈值误判。参考片一审报的
35 处里，22 处属于后者——所以别看见"35 处冻结"就以为片子坏了。

它只做**能机器判定**的部分：黑帧、冻结帧、静音、电平。构图好不好、
字幕有没有错字、AI 画面有没有畸变，仍然要人看抽样帧——这个工具的作用
是把该看的东西摆到你面前，并且把"看起来没问题"变成可复查的数字。

音频复测刻意**不复用** ``production/dahlia/build_audio.py``：独立实现同一套
阈值（1 秒窗、静音 -50 dBFS、逐章 -40 dBFS 下限），这样它是对成片的第二双眼睛，
而不是把同一段代码再跑一遍。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image

RATE = 48000
# 与 production/dahlia/build_audio.py 相同的判定口径（独立实现，见模块说明）
SILENCE_THRESHOLD_DBFS = -50.0
MIN_CHAPTER_RMS_DBFS = -40.0
BLACK_FRAME_LUMA = 12.0
FROZEN_SIGNATURE_SIZE = 16
FROZEN_TOLERANCE = 0.6          # 16x16 灰度签名的平均绝对差（0-255 尺度）
FROZEN_RUN_SECONDS = 1.0        # 连续相同画面超过这个秒数才算冻结

# 复核口径。16x16 的阈值只有 0.6/255 灰阶，慢速推拉的 AI 素材也会被判成"冻结"
# ——参考片一审报了 35 处，复核后 22 处其实是微动画面。所以检出之后再用 64x64
# 量一次，取窗口内**逐帧差的中位数**（不是最大值：一段静止画面里只要夹一次硬切，
# 最大值就会飙到 100+，反而把信息卡误判成微动）。
#
# 阈值是在参考片的 35 个窗口上实测标定的（delivery/frozen-triage-calibration.json）：
# 13 个真静止窗口的中位数 ≤ 0.08，22 个微动窗口的中位数 ≥ 0.21，0.15 落在中间的
# 空档里。改这个数之前先跑一遍标定，别凭感觉调。
TRIAGE_SIGNATURE_SIZE = 64
TRIAGE_STATIC_DELTA = 0.15      # 窗口内逐帧 64x64 灰度差的中位数，低于此判为"真静止"


def dbfs(level: float) -> float:
    return -120.0 if level <= 1e-12 else round(20.0 * np.log10(float(level)), 2)


def rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(block)))) if block.size else 0.0


def decode_audio(path: Path) -> np.ndarray:
    """解码成 48 kHz 单声道 float，区间 [-1, 1]。"""
    container = av.open(str(path))
    try:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        chunks = []
        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                chunks.append(resampled.to_ndarray().reshape(-1))
        for resampled in resampler.resample(None):     # flush
            chunks.append(resampled.to_ndarray().reshape(-1))
    finally:
        container.close()
    audio = np.concatenate(chunks).astype(np.float64) / 32768.0 if chunks else np.zeros(0)
    return audio


def measure_audio(path: Path, chapters: list[dict] | None) -> dict:
    samples = decode_audio(path)
    step = RATE
    windows = [rms(samples[i:i + step]) for i in range(0, len(samples), step)
               if samples[i:i + step].size]
    silent = sum(1 for value in windows if dbfs(value) < SILENCE_THRESHOLD_DBFS)
    report = {
        "file": path.name,
        "duration_seconds": round(len(samples) / RATE, 3),
        "sample_rate": RATE,
        "channels": 1,
        "rms_dbfs": dbfs(rms(samples)),
        "peak_dbfs": dbfs(float(np.abs(samples).max())) if samples.size else -120.0,
        "window_seconds": 1.0,
        "window_count": len(windows),
        "silent_windows": silent,
        "silent_fraction": round(silent / max(1, len(windows)), 4),
        "quietest_window_dbfs": min((dbfs(v) for v in windows), default=-120.0),
        "chapters": [],
    }
    for row in chapters or []:
        start, end = int(float(row["start"]) * RATE), int(float(row["end"]) * RATE)
        report["chapters"].append({
            "id": row.get("id", "?"),
            "start": round(float(row["start"]), 3),
            "end": round(float(row["end"]), 3),
            "rms_dbfs": dbfs(rms(samples[start:end])),
            "peak_dbfs": dbfs(float(np.abs(samples[start:end]).max())) if end > start else -120.0,
        })
    return report


def signature(image: Image.Image) -> np.ndarray:
    small = image.convert("L").resize((FROZEN_SIGNATURE_SIZE, FROZEN_SIGNATURE_SIZE),
                                      Image.Resampling.BILINEAR)
    return np.asarray(small, dtype=np.float32)


def frame_delta(before: Image.Image, after: Image.Image) -> float:
    """64x64 灰度签名的平均绝对差（0-255）：给"冻结"报警做复核。

    16x16 的签名太粗，慢速运镜会被判成静止；放大到 64x64 再量一次，
    就能把"真静止"（信息卡、档案照、片尾卡）和"微动"（慢速 AI 素材）分开。
    """
    size = (TRIAGE_SIGNATURE_SIZE, TRIAGE_SIGNATURE_SIZE)
    left = np.asarray(before.convert("L").resize(size, Image.Resampling.BILINEAR), dtype=np.float32)
    right = np.asarray(after.convert("L").resize(size, Image.Resampling.BILINEAR), dtype=np.float32)
    return float(np.abs(left - right).mean())


def triage_score(deltas: list[float]) -> float:
    """窗口内逐帧差的中位数。

    用中位数而不是最大值：静止画面里夹一次硬切，最大值能到 100+，会把信息卡
    误判成"有微动"。中位数不受单点影响。
    """
    return float(np.median(deltas)) if deltas else 0.0


def frozen_verdict(score: float) -> str:
    """把复核量到的帧间差翻译成结论：真静止 / 微动。"""
    return "static" if score < TRIAGE_STATIC_DELTA else "micro_motion"


def review_video(path: Path, work: Path, every: float, sheet_every: float) -> dict:
    frames_dir = work / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    container = av.open(str(path))
    try:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 30)
        width, height = stream.width, stream.height
        codec = stream.codec_context.name

        sampled, sheets = [], []
        previous: np.ndarray | None = None
        previous_frame: Image.Image | None = None
        run = 0
        run_max = 0.0
        run_triage: list[float] = []
        frozen_runs: list[dict] = []
        black_frames: list[dict] = []
        luma_by_second: dict[int, float] = {}
        decoded = 0
        current_sheet: list[Image.Image] = []

        for frame in container.decode(stream):
            image = frame.to_image()
            decoded += 1
            seconds = frame.time if frame.time is not None else decoded / fps
            gray = np.asarray(image.convert("L"), dtype=np.float32)
            luma = float(gray.mean())
            luma_by_second.setdefault(int(seconds), luma)
            if luma < BLACK_FRAME_LUMA:
                black_frames.append({"second": round(seconds, 2), "luma": round(luma, 2)})

            sign = signature(image)
            delta = None if previous is None else float(np.abs(sign - previous).mean())
            triage = None if previous_frame is None else frame_delta(previous_frame, image)
            if delta is not None and delta < FROZEN_TOLERANCE:
                run += 1
                run_max = max(run_max, delta)
                if triage is not None:
                    run_triage.append(triage)
                if run == int(FROZEN_RUN_SECONDS * fps):
                    score = triage_score(run_triage)
                    frozen_runs.append({"start_second": round(seconds - run / fps, 2),
                                        "end_second": round(seconds, 2),
                                        "max_frame_delta": round(run_max, 3),
                                        "triage_median_delta": round(score, 3),
                                        "verdict": frozen_verdict(score)})
            else:
                run, run_max, run_triage = 0, 0.0, []
            previous = sign
            previous_frame = image

            if abs(seconds - round(seconds / every) * every) < 1.0 / (2 * fps):
                name = f"t{seconds:07.2f}s.jpg"
                image.save(frames_dir / name, quality=88)
                sampled.append(name)
            if abs(seconds - round(seconds / sheet_every) * sheet_every) < 1.0 / (2 * fps):
                thumb = image.copy()
                thumb.thumbnail((480, 270))
                current_sheet.append(thumb)
                if len(current_sheet) == 12:
                    sheets.append(_compose_sheet(current_sheet, work, len(sheets) + 1))
                    current_sheet = []
        if current_sheet:
            sheets.append(_compose_sheet(current_sheet, work, len(sheets) + 1))
    finally:
        container.close()

    return {
        "file": path.name,
        "video_codec": codec,
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "decoded_frames": decoded,
        "duration_seconds": round(decoded / fps, 3),
        "black_frame_luma_threshold": BLACK_FRAME_LUMA,
        "black_frames": black_frames,
        "frozen_tolerance": FROZEN_TOLERANCE,
        "frozen_runs_over_one_second": frozen_runs,
        "mean_luma": round(float(np.mean(list(luma_by_second.values()))), 2),
        "min_luma": round(float(np.min(list(luma_by_second.values()))), 2),
        "max_luma": round(float(np.max(list(luma_by_second.values()))), 2),
        "sampled_frames": sampled,
        "contact_sheets": sheets,
    }


def _compose_sheet(thumbs: list[Image.Image], work: Path, index: int) -> str:
    columns = 4
    rows = int(np.ceil(len(thumbs) / columns))
    cell_w = max(t.width for t in thumbs)
    cell_h = max(t.height for t in thumbs)
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), "#111")
    for position, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((position % columns) * cell_w, (position // columns) * cell_h))
    name = f"contact-sheet-{index:02d}.png"
    sheet.save(work / name)
    return name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--film", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=None,
                        help="项目目录（读 delivery/final-audio-report.json 的章节边界）")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--every", type=float, default=5.0, help="抽样帧间隔秒数")
    parser.add_argument("--sheet-every", type=float, default=10.0, help="对照表取帧间隔秒数")
    args = parser.parse_args(argv)

    if not args.film.is_file():
        raise SystemExit(f"找不到成片：{args.film}")
    args.work.mkdir(parents=True, exist_ok=True)

    chapters: list[dict] = []
    if args.project:
        report = args.project / "delivery" / "final-audio-report.json"
        if report.is_file():
            chapters = json.loads(report.read_text()).get("chapters", [])

    audio = measure_audio(args.film, chapters)
    video = review_video(args.film, args.work, args.every, args.sheet_every)

    flags = []
    if audio["silent_fraction"] > 0.02:
        flags.append(f"静音占比 {audio['silent_fraction']} 超过 2%")
    if audio["rms_dbfs"] < MIN_CHAPTER_RMS_DBFS:
        flags.append(f"整体电平 {audio['rms_dbfs']} dBFS 过低")
    for row in audio["chapters"]:
        if row["rms_dbfs"] < MIN_CHAPTER_RMS_DBFS:
            flags.append(f"{row['id']} 电平 {row['rms_dbfs']} dBFS 低于 {MIN_CHAPTER_RMS_DBFS}")
    if video["black_frames"]:
        flags.append(f"{len(video['black_frames'])} 帧接近全黑")
    runs = video["frozen_runs_over_one_second"]
    if runs:
        static = sum(1 for row in runs if row.get("verdict") == "static")
        moving = len(runs) - static
        flags.append(
            f"{len(runs)} 处画面 1 秒内几乎无变化：{static} 处复核为真静止"
            f"（信息卡/档案照/片尾卡，设计如此），{moving} 处复核有微动"
            "（16x16 阈值过严，不是冻结帧）"
        )

    result = {"flags": flags, "video": video, "audio": audio,
              "note": "自动判定只覆盖黑帧/冻结帧/静音/电平；构图、字幕错字、AI 画面畸变需人工看抽样帧。"
                      "冻结帧报警都带 verdict：static=真静止（多为信息卡），micro_motion=复核有微动。"}
    out = args.work / "film-review.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    print(f"审片结果：{out}")
    print(f"  视频 {video['width']}x{video['height']} @{video['fps']}fps / "
          f"{video['decoded_frames']} 帧 / {video['duration_seconds']} 秒")
    print(f"  音频 {audio['duration_seconds']} 秒 / 整体 {audio['rms_dbfs']} dBFS RMS / "
          f"峰值 {audio['peak_dbfs']} dBFS / 静音占比 {audio['silent_fraction']}")
    for row in audio["chapters"]:
        print(f"    {row['id']}  {row['start']:>7.2f}-{row['end']:>7.2f}s  "
              f"{row['rms_dbfs']:>7} dBFS  峰值 {row['peak_dbfs']}")
    print(f"  抽样帧 {len(video['sampled_frames'])} 张 / 对照表 {len(video['contact_sheets'])} 张")
    print("  自动判定：" + ("；".join(flags) if flags else "无异常"))
    print("  仍需人工：看抽样帧确认构图与字幕，逐字听一遍配音。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
