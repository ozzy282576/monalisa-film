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


def resolve_script_path(args) -> Path:
    project = args.project_dir.expanduser().resolve()
    path = Path(args.script)
    if not path.is_absolute():
        path = project / path
    return path


def build(args) -> NoireRenderer:
    project = args.project_dir.expanduser().resolve()
    script = load_script(resolve_script_path(args), project)
    width, height = contract.canvas_size(args.preview)
    return NoireRenderer(project, script, width, height)


def main() -> None:
    parser = argparse.ArgumentParser(description="9:16 手绘悬疑解说视频")
    parser.add_argument("--script", default="examples/douyin-physics/script.json")
    parser.add_argument("--mode", choices=("plan", "render", "grades"), default="plan")
    parser.add_argument("--preview", action="store_true", help="540x960 快速预览")
    parser.add_argument("--output")
    parser.add_argument("--crf", type=int, default=22)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-dialogue-check", action="store_true",
                        help="不检查字幕与旁白是否一致（默认检查）")
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

    if args.mode == "plan":
        missing = [b.id for b in renderer.script.beats if b.image_path is None]
        voiced = sum(1 for b in renderer.script.beats if b.voice_path)
        # Beats with no narration are title cards by design, so counting them as
        # "missing audio" makes a finished film look incomplete.
        needs_voice = [b for b in renderer.script.beats if (b.narration or "").strip()]
        silent_by_design = [b.id for b in renderer.script.beats
                            if not (b.narration or "").strip()]
        print(f"标题：{renderer.script.title}")
        print(f"画布：{renderer.width}×{renderer.height} @ {renderer.fps}fps")
        print(f"幕数：{len(renderer.script.beats)}   总时长：{renderer.total_seconds:.1f}s "
              f"（{renderer.total_frames} 帧）")
        voice_line = f"配音：{voiced}/{len(needs_voice)} 幕已有音频"
        if silent_by_design:
            voice_line += f"（{'、'.join(silent_by_design)} 为标题卡，无旁白）"
        if renderer.script.voice:
            voice_line += f"  音色：{renderer.script.voice}"
        print(voice_line)
        absent = [b.id for b in needs_voice if not b.voice_path]
        if absent:
            print(f"      ⚠ 缺配音 → {', '.join(absent)}（时长会退回每幕最小值）")
        print(f"缺图：{len(missing)} 幕" + (f"  → {', '.join(missing)}" if missing else "  ✅ 齐全"))
        print("\n逐幕时长：")
        for beat in renderer.script.beats:
            voice = f"配音 {beat.voice_duration:.1f}s" if beat.voice_path else "无配音"
            grade = beat.grade_name or grade_module.DEFAULT_GRADE_BY_BEAT.get(beat.id, "-")
            print(f"  {beat.id}  {beat.start:6.2f}s +{beat.duration:5.2f}s  "
                  f"({voice}, 调色 {grade})  {beat.on_screen or ''}")
        return

    # Gate: captions are burned into the picture, so a mismatch between what the
    # audience hears and what they read is baked in permanently. Catch it before
    # spending half an hour rendering.
    from noire import check_dialogue
    if check_dialogue.main(["--script", str(resolve_script_path(args)), "--quiet"]) != 0:
        print("\n字幕与旁白不一致，已中止渲染（加 --skip-dialogue-check 可强制继续）")
        if not args.skip_dialogue_check:
            return
        print("  → 按 --skip-dialogue-check 继续")

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
