"""Story splitting and storyboard construction.

The upstream Skill asks the Agent to "preserve original wording, keep one
complete sentence per beat, and split only long compound sentences at narrative
turns".  :func:`split_beats` is the deterministic version of that rule so the
whole pipeline can run without an LLM in the loop, while
:func:`build_storyboard` emits the same schema the Remotion renderer consumed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from . import contract

SENTENCE_END = "。！？!?；;…"
SOFT_BREAK = "，,、：:—"
MAX_BEAT_CHARS = 26
HARD_BEAT_CHARS = 40
LAYERS = ("text", "bw_full", "color")


def _split_long(clause: str, limit: int = MAX_BEAT_CHARS) -> List[str]:
    """Break an over-long clause at its softest nearby punctuation."""
    clause = clause.strip()
    if len(clause) <= limit:
        return [clause] if clause else []
    pieces: List[str] = []
    remaining = clause
    while len(remaining) > limit:
        window = remaining[:limit + 8]
        cut = max((window.rfind(mark) for mark in SOFT_BREAK), default=-1)
        if cut < limit // 3:
            cut = limit - 1
        pieces.append(remaining[:cut + 1].strip())
        remaining = remaining[cut + 1:].strip()
    if remaining:
        pieces.append(remaining)
    return [piece for piece in pieces if piece]


def split_beats(story: str, limit: int = MAX_BEAT_CHARS) -> List[str]:
    """One complete sentence per beat, long compounds split at soft pauses."""
    text = story.replace("\r\n", "\n").strip()
    text = re.sub(r"[ \t]+", " ", text)
    beats: List[str] = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        current = ""
        for char in block:
            current += char
            if char in SENTENCE_END:
                beats.extend(_split_long(current, limit))
                current = ""
        if current.strip():
            beats.extend(_split_long(current, limit))
    return [beat for beat in (b.strip() for b in beats) if beat]


def format_caption(beat: str, per_line: int = 13) -> str:
    """Wrap a beat into the two-line caption the reference masters use."""
    beat = beat.strip()
    if len(beat) <= per_line:
        return beat
    midpoint = len(beat) // 2
    candidates = [i for i, char in enumerate(beat) if char in SOFT_BREAK]
    if candidates:
        best = min(candidates, key=lambda i: abs(i - midpoint))
        if 3 <= best <= len(beat) - 4:
            return beat[:best + 1].strip() + "\n" + beat[best + 1:].strip()
    return beat[:per_line].strip() + "\n" + beat[per_line:].strip()


def build_scenes(
    beats: Sequence[str],
    visual_plan: Optional[dict] = None,
    character_lock: str = "",
    color_hint: str = "",
    detail_hint: Optional[str] = None,
) -> List[dict]:
    scenes: List[dict] = []
    for index, beat in enumerate(beats, start=1):
        scene_id = f"{index:02d}"
        plan = (visual_plan or {}).get(scene_id, {})
        caption = format_caption(plan.get("caption") or beat)
        scenes.append({
            "id": scene_id,
            "duration_sec": plan.get("duration_sec") or contract.timing_for_text(caption),
            "text": caption,
            "narration": plan.get("narration") or beat,
            "visual": plan.get("visual")
            or f"根据文案绘制一个单一、清楚、可画的白底日记漫画场景：{beat.replace(chr(10), '')}",
            "shot": plan.get("shot") or "story_beat",
            "character_lock": character_lock or None,
            "color_hint": plan.get("color_hint") or color_hint or None,
            "detail_hint": plan.get("detail_hint") or detail_hint,
            "layers": list(LAYERS),
            "assets": {"text_image": None, "bw": None, "detail": None, "color": None},
        })
    return scenes


def build_storyboard(
    title: str,
    scenes: Sequence[dict],
    style_lock: str,
    character_lock: str,
    transition: str = "cut",
    transition_sec: float = contract.DEFAULT_TRANSITION_SEC,
    text_mode: str = "font",
    palette_id: Optional[str] = None,
    width: int = contract.DESIGN_WIDTH,
    height: int = contract.DESIGN_HEIGHT,
    fps: int = contract.DESIGN_FPS,
    enable_detail: bool = False,
    style_id: str = "colored-pencil-diary",
    batch: Optional[str] = None,
) -> dict:
    return {
        "project": {
            "title": title,
            "mode": "quality" if enable_detail else "speed",
            "images_per_scene": 1,
            "derive_bw": "local",
            "enable_detail": enable_detail,
            "gen_size": 1024,
            "export_size": [width, height],
            "ratio": contract.RATIO,
            "width": width,
            "height": height,
            "fps": fps,
            "transition": transition,
            "transition_sec": transition_sec,
            "text_mode": text_mode,
            "palette_id": palette_id,
            "style_id": style_id,
            "batch": batch,
            "lettering_jitter": 0.0,
            "style_lock": style_lock,
            "character_lock": character_lock,
            "audio": {
                "voiceover": "post",
                "bgm": "optional_bed_only",
                "bgm_follows_text": False,
            },
        },
        "scenes": list(scenes),
    }


def generation_jobs(storyboard: dict, batch_dir: str, style: dict) -> dict:
    """The image-generation manifest an Agent fulfils (upstream ``codex-image-jobs``)."""
    project = storyboard["project"]
    jobs = []
    for scene in storyboard["scenes"]:
        prompt = "\n\n".join(part for part in (
            "画一张 3:4 竖版手绘故事母图：上半部分是手写中文字幕，下半部分是插画。"
            "整页保持纯白纸张，不要边框、不要水印、不要签名。",
            f"【画风锁定】{project['style_lock']}",
            f"【角色锁定】{project['character_lock']}" if project.get("character_lock") else "",
            f"【本幕画面】{scene['visual']}",
            f"【字幕文字】手写中文字幕，必须逐字准确：{scene['text'].replace(chr(10), ' / ')}",
            f"【字幕写法】{style.get('caption_prompt', '')}",
            f"【配色】{scene.get('color_hint') or ''}",
            f"【避免】{style.get('avoid', '')}",
        ) if part and part.strip())
        jobs.append({
            "scene_id": scene["id"],
            "engine": "generate_image",
            "size": [1024, 1536],
            "aspect": "2:3",
            "prompt": prompt,
            "output_master": f"public/{batch_dir}/{scene['id']}_master.png",
            "text_image": f"public/{batch_dir}/{scene['id']}_text.png",
            "bw": f"public/{batch_dir}/{scene['id']}_bw.png",
            "color": f"public/{batch_dir}/{scene['id']}_color.png",
        })
    return {
        "title": project["title"],
        "style_id": project.get("style_id"),
        "batch_dir": batch_dir,
        "text_mode": project.get("text_mode"),
        "jobs": jobs,
    }


def load_visual_plan(path: Optional[Path]) -> Optional[dict]:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))
