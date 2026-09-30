#!/usr/bin/env python3
"""Offline pipeline self-test.

Synthesises a few hand-drawn-looking master pages with Pillow, runs the full
``plan -> import -> preview`` chain, and asserts the rendered file matches the
contract (3:4, expected frame count, silent H.264).  No network, no API keys.

    python3 tests/test_pipeline.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from handdrawn import contract  # noqa: E402
from handdrawn.encoder import probe  # noqa: E402
from handdrawn.story import split_beats  # noqa: E402
from handdrawn.styles import StyleLibrary  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def synth_page(seed: int, width: int = 1024, height: int = 1536) -> Image.Image:
    """A rough felt-tip + crayon page, standing in for a generated master."""
    rng = np.random.default_rng(seed)
    page = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    def wobble(points, amount=5.0):
        return [(x + float(rng.normal(0, amount)), y + float(rng.normal(0, amount)))
                for x, y in points]

    palette = [(186, 203, 214), (176, 96, 84), (222, 205, 176), (208, 194, 118), (150, 158, 150)]
    for index, colour in enumerate(palette[:3]):
        cx = 250 + index * 270
        cy = 700 + int(rng.integers(-60, 60))
        radius = int(rng.integers(90, 150))
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=colour)

    draw.line(wobble([(120, 1180), (900, 1210)]), fill=(38, 38, 36), width=9)
    draw.ellipse(wobble([(300, 300), (720, 720)])[:0] or [300, 300, 720, 720],
                 outline=(38, 38, 36), width=9)
    for _ in range(24):
        x0 = int(rng.integers(140, 880))
        y0 = int(rng.integers(380, 1080))
        draw.line(wobble([(x0, y0), (x0 + int(rng.integers(-90, 90)), y0 + int(rng.integers(-90, 90)))], 3),
                  fill=(38, 38, 36), width=int(rng.integers(4, 9)))
    return page


def main() -> int:
    print("手绘故事视频 · 离线自检\n")

    print("1. 渲染契约")
    check("画布为 3:4", abs(contract.DESIGN_WIDTH / contract.DESIGN_HEIGHT - 3 / 4) < 1e-6)
    check("预览尺寸为 720×960", contract.canvas_size(720, 960) == (720, 960))
    def board(transition: str) -> dict:
        return {
            "project": {"fps": 30, "transition": transition, "transition_sec": 0.7},
            "scenes": [{"duration_sec": 4.0}] * 3,
        }

    cut = board("cut")
    check("cut 总帧数 = Σ时长", contract.total_frames(cut) == 360, f"{contract.total_frames(cut)}")
    check("cut 无转场重叠", contract.transition_frames(cut) == 0)
    flip = board("page-flip")
    overlap = contract.transition_frames(flip)
    check("翻书有重叠", overlap == 21, f"overlap={overlap}")
    check("翻书总帧数扣除重叠", contract.total_frames(flip) == 360 - overlap * 2,
          f"{contract.total_frames(flip)}")
    check("字幕时长落在 4.4–6.2s", 4.4 <= contract.timing_for_text("他推开门，屋里一片安静。") <= 6.2)

    print("\n2. 分句")
    beats = split_beats("小猫坐在窗边。小鸟停在枝头。\n风把窗帘吹起来，又慢慢放下。")
    check("按完整句切分", len(beats) == 3, " | ".join(beats))
    check("保留原文措辞", "".join(beats).replace(" ", "") ==
          "小猫坐在窗边。小鸟停在枝头。风把窗帘吹起来，又慢慢放下。".replace(" ", ""))

    print("\n3. 风格库")
    library = StyleLibrary(ROOT / "references" / "handdrawn-style-library.json")
    check("327 项资产", len(library.styles) + len(library.palettes) == 327,
          f"{len(library.styles)}+{len(library.palettes)}")
    check("精选 30 项", len(library.featured) == 30)
    check("默认画风可解析", library.resolve(None)["id"] == "colored-pencil-diary")
    check("中文名可解析", library.resolve("水墨")["id"] != "")
    check("配色 C-01 可解析", library.palette("C-01")["id"] == "C-01")

    print("\n4. 端到端渲染（合成母图）")
    workdir = Path(tempfile.mkdtemp(prefix="handdrawn-test-"))
    try:
        batch = workdir / "public" / "assets" / "generated" / "selftest"
        batch.mkdir(parents=True)
        story = "小猫坐在窗边。小鸟停在枝头。风把窗帘吹起来。"
        (workdir / "story.txt").write_text(story, encoding="utf-8")

        env = {"PYTHONPATH": str(ROOT / "scripts"), "PATH": "/usr/bin:/bin:/usr/local/bin"}

        def run(*extra: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "run_story_video.py"),
                 "--project-dir", str(workdir), *extra],
                capture_output=True, text=True, env={**env},
            )

        result = run("--input", str(workdir / "story.txt"), "--title", "自检",
                     "--mode", "plan")
        check("plan 模式成功", result.returncode == 0, result.stderr.strip()[-300:])
        plan = json.loads((workdir / ".story-video" / "storyboard.plan.json").read_text("utf-8"))
        check("分镜数量正确", len(plan["scenes"]) == 3, f"{len(plan['scenes'])} 幕")

        jobs = json.loads((workdir / ".story-video" / "generation-jobs.json").read_text("utf-8"))
        check("生成清单齐全", len(jobs["jobs"]) == 3)
        check("提示词含字幕原文", story[:4] in jobs["jobs"][0]["prompt"])

        for index in range(1, 4):
            synth_page(index).save(batch / f"{index:02d}_master.png")

        # the manifest writes paths relative to public/
        jobs["jobs"] = [
            {**job, "output_master": f"public/assets/generated/selftest/{job['scene_id']}_master.png"}
            for job in jobs["jobs"]
        ]
        (workdir / ".story-video" / "generation-jobs.json").write_text(
            json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")

        result = run("--mode", "import")
        check("import 模式成功", result.returncode == 0, result.stderr.strip()[-300:])

        result = run("--mode", "preview", "--transition", "cut")
        check("预览渲染成功", result.returncode == 0, result.stderr.strip()[-400:])
        preview = workdir / "renders" / "picture_silent-preview.mp4"
        check("预览文件存在", preview.exists(), str(preview))
        if preview.exists():
            width, height, duration = probe(preview)
            check("预览分辨率 720×960", (width, height) == (720, 960), f"{width}×{height}")
            expected = contract.total_frames(plan) / 30
            check("时长符合契约", abs(duration - expected) < 0.35,
                  f"{duration:.2f}s vs {expected:.2f}s")

        result = run("--mode", "preview", "--transition", "page-flip")
        check("翻书渲染成功", result.returncode == 0, result.stderr.strip()[-400:])
        if preview.exists():
            width, height, _ = probe(preview)
            check("翻书输出仍为 720×960", (width, height) == (720, 960), f"{width}×{height}")

        storyboards = json.loads((workdir / "storyboard.json").read_text("utf-8"))
        check("已导入素材路径", all(s["assets"]["color"] for s in storyboards["scenes"]))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} 项失败：" + "、".join(FAILURES))
        return 1
    print("✅ 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
