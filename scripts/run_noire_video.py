#!/usr/bin/env python3
"""CLI for the 9:16 noire explainer.

    plan     analyse the script, beat lengths, missing artwork
    render   encode the picture track, then mux picture + sound
    grades   print the colour grades available and which beat uses which
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from noire import contract, grade as grade_module  # noqa: E402
from noire.encoder import find_ffprobe, probe  # noqa: E402
from noire.render import NoireRenderer, load_script  # noqa: E402


def default_project() -> Path:
    return Path(__file__).resolve().parents[1]


def build(args) -> NoireRenderer:
    project = args.project_dir.expanduser().resolve()
    script_path = Path(args.script)
    if not script_path.is_absolute():
        script_path = project / script_path
    script = load_script(script_path, project)
    width, height = contract.canvas_size(args.preview)
    return NoireRenderer(project, script, width, height)


def main() -> None:
    parser = argparse.ArgumentParser(description="9:16 手绘悬疑解说视频")
    parser.add_argument("--script", default="examples/douyin-physics/script.json")
    parser.add_argument("--mode", choices=("plan", "render", "grades"), default="plan")
    parser.add_argument("--preview", action="store_true", help="540x960 快速预览")
    parser.add_argument("--output")
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--art", choices=("ink", "colour"),
                        help="覆盖脚本里的画风模式（ink=双色阶，colour=彩色原图）")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--project-dir", type=Path, default=default_project())
    args = parser.parse_args()

    project = args.project_dir.expanduser().resolve()

    if args.mode == "grades":
        print("可选调色（在 script.json 的每一幕加 \"grade\": \"<名字>\" 覆盖）：")
        for name in grade_module.GRADES:
            print(f"  {name}")
        print("\n逐幕默认：")
        for beat_id, name in grade_module.DEFAULT_GRADE_BY_BEAT.items():
            print(f"  {beat_id} -> {name}")
        return

    renderer = build(args)
    if args.art:
        renderer.script.art = args.art
        for beat in renderer.script.beats:
            beat.grade = (None if args.art == "colour" and not beat.grade_name
                          else grade_module.resolve(beat.grade_name, beat.id))

    if args.mode == "plan":
        missing = [b.id for b in renderer.script.beats if b.image_path is None]
        voiced = sum(1 for b in renderer.script.beats if b.voice_path)
        print(f"标题：{renderer.script.title}")
        print(f"画布：{renderer.width}×{renderer.height} @ {renderer.fps}fps")
        print(f"幕数：{len(renderer.script.beats)}   总时长：{renderer.total_seconds:.1f}s "
              f"（{renderer.total_frames} 帧）")
        print(f"配音：{voiced}/{len(renderer.script.beats)} 幕已有音频"
              + (f"  音色：{renderer.script.voice}" if renderer.script.voice else ""))
        print(f"缺图：{len(missing)} 幕" + (f"  → {', '.join(missing)}" if missing else "  ✅ 齐全"))
        print("\n逐幕时长：")
        for beat in renderer.script.beats:
            voice = f"配音 {beat.voice_duration:.1f}s" if beat.voice_path else "无配音"
            grade = beat.grade_name or grade_module.DEFAULT_GRADE_BY_BEAT.get(beat.id, "-")
            print(f"  {beat.id}  {beat.start:6.2f}s +{beat.duration:5.2f}s  "
                  f"({voice}, 调色 {grade})  {beat.on_screen or ''}")
        return

    output = Path(args.output) if args.output else (
        project / "renders" / ("noire-preview.mp4" if args.preview else "noire.mp4")
    )
    if output.exists() and not args.force:
        raise SystemExit(f"{output} 已存在，加 --force 覆盖")
    result = renderer.render(output, crf=args.crf, with_audio=not args.no_audio)
    width, height, duration = probe(result["picture"], find_ffprobe(project))
    print(f"完成：{result['output']}")
    print(f"  {result['frames']} 帧 · {result['seconds']:.1f}s · {result['beats']} 幕 · "
          f"{result['width']}×{result['height']} · 音轨：{'有' if result['audio'] else '无'}")


if __name__ == "__main__":
    main()
