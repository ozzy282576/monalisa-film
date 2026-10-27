#!/usr/bin/env python3
"""把 38 个镜头的接触表（qa/Sxx.jpg）拼成总览图，方便逐镜复审。

手册第 7 步要求对每个镜头问四个问题（画的是不是这一镜 / 7 秒内有没有换场 /
有没有脸或可读文字 / 运镜对不对）。38 张 14 帧接触表一张张翻太慢，这里
每 6 张拼成一张总览（每张抽 6 帧），一次看 6 镜。

用法::

    python3 production/lamkorwan/qa_overview.py                 # 全部
    python3 production/lamkorwan/qa_overview.py --shots S01,S02  # 只看指定镜头
    python3 production/lamkorwan/qa_overview.py --frames 4       # 每镜抽 4 帧
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
QA = HERE / "qa"
OUT = HERE / "qa" / "overview"


def load_sheet(sid: str, frames: int) -> Image.Image | None:
    path = QA / f"{sid}.jpg"
    if not path.is_file():
        return None
    sheet = Image.open(path).convert("RGB")
    # 接触表是 4 列 × 4 行（最后一格可能是空的），按行优先取帧
    cols, rows = 4, 4
    tw, th = sheet.width // cols, sheet.height // rows
    tiles = []
    for index in range(min(frames, cols * rows)):
        r, c = divmod(index, cols)
        tiles.append(sheet.crop((c * tw, r * th, (c + 1) * tw, (r + 1) * th)))
    strip = Image.new("RGB", (tw, th * len(tiles)), "black")
    for i, tile in enumerate(tiles):
        strip.paste(tile, (0, i * th))
    return strip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", default="")
    parser.add_argument("--frames", type=int, default=5, help="每个镜头抽几帧")
    parser.add_argument("--per-sheet", type=int, default=4, help="总览图里放几个镜头")
    parser.add_argument("--width", type=int, default=520, help="每个镜头列的宽度")
    args = parser.parse_args()
    only = [s.strip() for s in args.shots.split(",") if s.strip()]
    shots = only or [f"S{i:02d}" for i in range(1, 46)]
    available = [s for s in shots if (QA / f"{s}.jpg").is_file()]
    if not available:
        raise SystemExit("qa/ 里没有接触表")
    OUT.mkdir(parents=True, exist_ok=True)
    per = max(1, args.per_sheet)
    for start in range(0, len(available), per):
        batch = available[start:start + per]
        strips = [(sid, load_sheet(sid, args.frames)) for sid in batch]
        strips = [(sid, s) for sid, s in strips if s is not None]
        if not strips:
            continue
        scale = args.width / strips[0][1].width
        cell_h = round(strips[0][1].height * scale)
        sheet = Image.new("RGB", (args.width * len(strips), cell_h + 26), "#101010")
        for i, (sid, strip) in enumerate(strips):
            sheet.paste(strip.resize((args.width, cell_h)), (i * args.width, 26))
            from PIL import ImageDraw
            ImageDraw.Draw(sheet).text((i * args.width + 8, 6), sid, fill="#7fe0a0")
        name = OUT / f"overview-{strips[0][0]}-{strips[-1][0]}.jpg"
        sheet.save(name, quality=88)
        print(f"{name}  {len(strips)} 镜 × {args.frames} 帧")
    print(f"共 {len(available)} 镜有接触表，总览图在 {OUT}")


if __name__ == "__main__":
    main()
