#!/usr/bin/env python3
"""Unified CLI for the hand-drawn story video pipeline.

The flag surface mirrors the upstream ``story-to-handdrawn-video`` project so the
same Agent Skill instructions keep working:

    plan -> generate -> import -> preview -> render

``plan``/``generate`` write a storyboard plus an image-generation manifest;
``import`` turns the finished master pages into the derived plates; ``preview``
and ``render`` encode the silent H.264 picture track.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handdrawn import contract, styles as styles_module  # noqa: E402
from handdrawn.encoder import probe  # noqa: E402
from handdrawn.render import StoryRenderer, preview_size, resolve_asset  # noqa: E402
from handdrawn import story as story_module  # noqa: E402


def install_root() -> Path:
    """Where the code, catalog and fonts live (this checkout)."""
    return Path(__file__).resolve().parents[1]


def resources_root(project: Path) -> Path:
    """Assets resolve from the workspace when it is self-contained."""
    if (project / "references" / "handdrawn-style-library.json").exists():
        return project
    return install_root()


def default_project() -> Path:
    configured = os.environ.get("STORY_VIDEO_PROJECT")
    if configured:
        return Path(configured).expanduser().resolve()
    for candidate in [Path.cwd(), *Path(__file__).resolve().parents]:
        if (candidate / "references" / "handdrawn-style-library.json").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把中文故事文案或有序图片，做成 3:4 竖屏手绘故事动画（静音画面轨）。"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="UTF-8 故事文本文件")
    source.add_argument("--text", help="直接传入故事文案")
    source.add_argument("--images", type=Path, nargs="+", help="有序的整页图片（按播放顺序）")

    parser.add_argument("--title", default="手绘故事")
    parser.add_argument("--style", default=None, help="内置画风 id / 编号 / 中文名 / 别名")
    parser.add_argument("--list-styles", action="store_true", help="打印画风目录后退出")
    parser.add_argument("--all-styles", action="store_true", help="列出全部 297 条配方")
    parser.add_argument("--asset-type", choices=("style", "palette", "all"), default="style")
    parser.add_argument("--category")
    parser.add_argument("--query")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--palette", help="主题配色 C-01 … C-30")
    parser.add_argument("--character-lock", help="角色一致性设定")
    parser.add_argument("--visual-plan", type=Path, help="按分镜编号提供的视觉补充 JSON")

    parser.add_argument(
        "--mode",
        choices=("plan", "generate", "full", "import", "render", "preview"),
        default="plan",
    )
    parser.add_argument("--text-mode", choices=("font", "image2"), default="font",
                        help="font：本地手写字体渲染字幕（默认）；image2：使用母图中的手写字")
    parser.add_argument("--layout", choices=("auto", "composite", "full"), default="auto")
    parser.add_argument("--transition", choices=("cut", "page-flip"), default="cut")
    parser.add_argument("--transition-sec", type=float, default=contract.DEFAULT_TRANSITION_SEC)
    parser.add_argument("--page-duration", type=float, default=contract.DEFAULT_PAGE_DURATION_SEC)
    parser.add_argument("--split-y", action="append", default=[], metavar="SCENE:PIXELS")
    parser.add_argument("--enable-detail", action="store_true", help="启用 detail 图层（quality 模式）")
    parser.add_argument("--wobble", type=float, default=0.0,
                        help=">0 时给揭示边缘加上手绘抖动（非上游行为）")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--project-dir", type=Path, default=default_project())
    parser.add_argument("--selftest", action="store_true", help="跑一遍离线自检并退出")
    return parser.parse_args(argv)


# --------------------------------------------------------------------------
# style helpers
# --------------------------------------------------------------------------


def style_locks(project: Path, entry: dict, palette: Optional[dict]) -> tuple:
    """A style recipe's own profile file wins over its one-line summary."""
    style_lock = entry.get("summary") or ""
    blocks = entry.get("prompt_blocks") or []
    if blocks:
        style_lock = (style_lock + "\n\n" + "\n".join(blocks)).strip()
    profile = entry.get("profile_file")
    if profile:
        candidate = project / profile
        if candidate.exists():
            style_lock = candidate.read_text(encoding="utf-8").strip()
    if palette:
        style_lock += "\n\n【主题配色】" + (
            palette.get("color_hint") or palette.get("summary") or ""
        )
    return style_lock.strip(), (entry.get("color_hint") or "")


# --------------------------------------------------------------------------
# storyboard IO
# --------------------------------------------------------------------------


def storyboard_path(project: Path) -> Path:
    return project / "storyboard.json"


def read_story(args) -> str:
    if args.text:
        return args.text
    if args.input:
        return Path(args.input).read_text(encoding="utf-8")
    raise SystemExit("需要 --input 或 --text")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def batch_dir_for(title: str, style_id: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title).strip("-") or "story"
    return f"assets/generated/{safe}-{style_id}-{stamp}"


def parse_split_overrides(values: List[str]) -> Dict[str, int]:
    overrides: Dict[str, int] = {}
    for item in values:
        if ":" not in item:
            raise SystemExit(f"--split-y 需要 SCENE:PIXELS 形式，收到 {item}")
        scene_id, pixels = item.split(":", 1)
        overrides[scene_id] = int(pixels)
    return overrides


# --------------------------------------------------------------------------
# modes
# --------------------------------------------------------------------------


def mode_plan(args, project: Path, library, entry, palette, generate: bool) -> None:
    story = read_story(args)
    beats = story_module.split_beats(story)
    if not beats:
        raise SystemExit("文案为空")

    visual_plan = story_module.load_visual_plan(args.visual_plan)
    style_lock, color_hint = style_locks(project, entry, palette)
    character_lock = args.character_lock or ""
    scenes = story_module.build_scenes(beats, visual_plan, character_lock, color_hint)

    batch = batch_dir_for(args.title, entry["id"])
    storyboard = story_module.build_storyboard(
        title=args.title,
        scenes=scenes,
        style_lock=style_lock,
        character_lock=character_lock,
        transition=args.transition,
        transition_sec=args.transition_sec,
        text_mode=args.text_mode,
        palette_id=palette["id"] if palette else None,
        enable_detail=args.enable_detail,
        style_id=entry["id"],
        batch=batch,
    )
    storyboard["project"]["layout"] = args.layout
    storyboard["project"]["lettering_jitter"] = 0.0

    jobs = story_module.generation_jobs(storyboard, batch, entry)
    out_dir = project / ".story-video"
    write_json(out_dir / "storyboard.plan.json", storyboard)
    write_json(out_dir / "generation-jobs.json", jobs)

    total = contract.total_frames(storyboard)
    print(f"分镜规划完成：{len(scenes)} 幕，{total} 帧 / {total / storyboard['project']['fps']:.1f} 秒")
    print("  分镜：.story-video/storyboard.plan.json")
    print(f"  出图清单：.story-video/generation-jobs.json")
    if generate:
        print("  下一步：按 generation-jobs.json 逐幕出图，然后运行 --mode import")
    return jobs


def mode_import(args, project: Path) -> None:
    plan_path = project / ".story-video" / "storyboard.plan.json"
    jobs_path = project / ".story-video" / "generation-jobs.json"
    if not plan_path.exists():
        raise SystemExit("找不到 .story-video/storyboard.plan.json，请先运行 --mode plan")

    storyboard = json.loads(plan_path.read_text(encoding="utf-8"))
    jobs = json.loads(jobs_path.read_text(encoding="utf-8")) if jobs_path.exists() else {"jobs": []}
    jobs_by_id = {job["scene_id"]: job for job in jobs.get("jobs", [])}

    imported, missing = 0, []
    for scene in storyboard["scenes"]:
        job = jobs_by_id.get(scene["id"])
        if not job:
            missing.append(scene["id"])
            continue
        master = project / job["output_master"]
        if not master.exists():
            alt = project / "public" / job["output_master"]
            master = alt if alt.exists() else master
        if not master.exists():
            missing.append(scene["id"])
            continue

        relative = job["output_master"].split("public/", 1)[-1]
        scene["assets"]["color"] = relative
        if job.get("text_image") and args.text_mode == "image2":
            text_file = project / job["text_image"]
            if text_file.exists():
                scene["assets"]["text_image"] = job["text_image"].split("public/", 1)[-1]
        imported += 1

    if missing:
        raise SystemExit(f"缺少母图：{', '.join(missing)}（先按 generation-jobs.json 出图）")

    target = storyboard_path(project)
    if target.exists() and not args.force:
        raise SystemExit(f"{target} 已存在；如需覆盖请加 --force")
    write_json(target, storyboard)
    print(f"已导入 {imported} 幕母图 → {target.name}")


def build_uploaded_storyboard(args, project: Path, library) -> dict:
    entry = library.resolve(args.style)
    images = [Path(p).expanduser().resolve() for p in args.images]
    scenes = []
    for index, path in enumerate(images, start=1):
        if not path.exists():
            raise SystemExit(f"图片不存在：{path}")
        with Image.open(path) as handle:
            width, height = handle.size
        scenes.append({
            "id": f"{index:02d}",
            "duration_sec": args.page_duration,
            "text": "",
            "narration": "",
            "visual": f"uploaded page {path.name}",
            "shot": "full_uploaded_page" if args.layout == "full" else "uploaded_page",
            "layers": ["color"] if args.transition == "page-flip" else ["text", "bw_full", "color"],
            "color_hint": None,
            "detail_hint": None,
            "assets": {"text_image": None, "bw": None, "detail": None, "color": str(path)},
            "source_size": [width, height],
        })
    return {
        "project": {
            "title": args.title,
            "mode": "speed",
            "enable_detail": False,
            "export_size": [contract.DESIGN_WIDTH, contract.DESIGN_HEIGHT],
            "ratio": contract.RATIO,
            "width": contract.DESIGN_WIDTH,
            "height": contract.DESIGN_HEIGHT,
            "fps": contract.DESIGN_FPS,
            "transition": args.transition,
            "transition_sec": args.transition_sec,
            "text_mode": args.text_mode,
            "layout": args.layout,
            "style_id": entry["id"],
            "style_lock": entry.get("summary", ""),
            "character_lock": args.character_lock or "",
            "lettering_jitter": 0.0,
            "audio": {"voiceover": "post", "bgm": "optional_bed_only", "bgm_follows_text": False},
        },
        "scenes": scenes,
    }


def do_render(args, project: Path, storyboard: dict, quality: str) -> None:
    full = quality == "render"
    size = (contract.DESIGN_WIDTH, contract.DESIGN_HEIGHT) if full else preview_size()
    overrides = parse_split_overrides(args.split_y)
    print(f"渲染 {size[0]}×{size[1]} @ {storyboard['project']['fps']}fps …")
    renderer = StoryRenderer(
        project, storyboard, size[0], size[1],
        wobble=args.wobble, split_overrides=overrides,
        resources_dir=resources_root(project),
    )
    name = "picture_silent.mp4" if full else "picture_silent-preview.mp4"
    output = project / "renders" / name
    result = renderer.render(output, crf=18 if full else 23)
    width, height, duration = probe(result.output)
    print(f"完成：{result.output}")
    print(f"  {result.frames} 帧 · {result.duration_seconds:.1f}s · {len(storyboard['scenes'])} 幕 · "
          f"transition={result.transition} · 音频：无（后期配音）")
    if width:
        print(f"  校验：{width}×{height} · {duration:.1f}s")


def run_selftest(project: Path) -> None:
    import subprocess

    subprocess.run([sys.executable, str(project / "tests" / "test_pipeline.py")], check=True)


# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    project = args.project_dir.expanduser().resolve()
    resources = resources_root(project)
    library = styles_module.load(resources)

    if args.selftest:
        run_selftest(project)
        return

    if args.list_styles:
        entries = library.list(args.asset_type, args.all_styles, args.category, args.query)
        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
            return
        scope = "全部" if args.all_styles else "精选"
        print(f"手绘风格库 v{library.data.get('version')} · {len(library.styles)} 条画风 + "
              f"{len(library.palettes)} 套配色 · 当前显示 {len(entries)} 项（{scope}）")
        for entry in entries:
            print("  " + library.describe(entry))
        return

    entry = library.resolve(args.style)
    palette = library.palette(args.palette)

    if args.images:
        if args.mode in ("plan", "import", "generate"):
            raise SystemExit("--images 用于整页图片，请使用 --mode preview 或 --mode full/render")
        storyboard = build_uploaded_storyboard(args, project, library)
        write_json(project / ".story-video" / "storyboard.uploaded.json", storyboard)
        do_render(args, project, storyboard, "render" if args.mode in ("full", "render") else "preview")
        return

    if args.mode == "import":
        mode_import(args, project)
        return

    if args.mode in ("plan", "generate"):
        mode_plan(args, project, library, entry, palette, args.mode == "generate")
        return

    storyboard_file = storyboard_path(project)
    if not storyboard_file.exists():
        raise SystemExit(
            f"找不到 {storyboard_file.name}；请先 --mode plan → 出图 → --mode import"
        )
    storyboard = json.loads(storyboard_file.read_text(encoding="utf-8"))
    for key, value in (("transition", args.transition), ("transition_sec", args.transition_sec),
                       ("text_mode", args.text_mode), ("lettering_jitter", 0.0)):
        storyboard["project"][key] = value
    if args.character_lock:
        storyboard["project"]["character_lock"] = args.character_lock
    do_render(args, project, storyboard, "render" if args.mode in ("render", "full") else "preview")


if __name__ == "__main__":
    main()
