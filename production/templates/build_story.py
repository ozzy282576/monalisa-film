#!/usr/bin/env python3
"""《__TITLE__》的全部内容源：解说词、45 镜分镜、信息卡文案、字幕高亮词、发布文案。

这是这部片子**唯一需要动脑写的文件**（模板来自 production/templates/build_story.py，
样板是 production/rabies1885/build_story.py —— 一部出片、听检、全帧 QC 与人工语义签收都跑完的成片）。

用法::

    python3 production/__SLUG__/build_story.py            # 写 story.json（含 presentation 块）+ audio/manifest.json 的逐字文本
    python3 production/__SLUG__/build_story.py --script   # 生成 抖音脚本.md（3 标题 / 核心爆点 / 四列分镜表 / 金句）
    python3 production/__SLUG__/build_story.py --publish  # 生成 抖音发布文案.md（标题 / 介绍 / 提问读者一句话 / 话题）

写法规则（都是狂犬病那部踩出来的，别省）：

- 六段解说合计 ≈ 760–800 字（含标点；狂犬病那部 786 字），TTS 收紧停顿后 ≈ 160–176 秒
  （可用窗口 = 180 − 片头 0.6 − 片尾 6.0 − 5 个章间隔 × 1.08 = 168 秒）；每段末尾留一个钩子；
  数字一律写成中文读法（"二零二三年一月二十六日""百分之九十九点九六"），TTS 和字幕才一致；
  不写血腥/侵害过程的具体描写（TTS 审核会拒，红线也不允许）。
- 45 镜 = 38 个 Agnes 动画镜头 + 7 张信息卡，按成片顺序编号，**每个镜头只出现一次**；
  规划网格 4 秒/镜，Agnes 每镜实际请求 7 秒，真正的时长由 render.py 的 CUTS 按配音停顿决定。
- 提示词先钉死"唯一场景"（framed on … from the first frame to the last），再明确排除别的场景
  （no windows / no view outside / no skyline），最后加 HOLD 句（no cut, no scene change, no camera relocation）。
  否定词对这个模型基本没用，想去掉天际线就别给它地平线（低机位、让墙/树篱/门廊填满背景）。
- 人只能是背影、剪影、手；画面里不许有可读文字；不出现遗体、暴力动作。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"

TITLE = "__TITLE__"

# 全片统一的画面风格前缀（英文）。TODO：把「世界描述」换成本片的地点/年代/道具；
# 后半句（人物只给背影/剪影/手、无文字、单一运镜）是流水线规则，别删。
# 注意：style_prefix 参与全部 Agnes 镜头的 request_hash，开工后改一个字 = 38 镜全部重做。
STYLE_PREFIX = (
    "Stylized 2D animated documentary illustration with hand-painted graphic-novel textures and soft "
    "cel shading, TODO world description (places, era, props, weather); horizontal 16:9 cinematic composition, "
    "muted palette of slate blue, steel grey and sodium-orange practical light, restrained procedural "
    "true-crime mood, no horror excess; every character is shown only from behind, in silhouette, or as "
    "hands and props - never a clear frontal face; absolutely no readable text, letters, numbers, logos, "
    "license plates or brand marks anywhere inside the frame; one single continuous smooth slow camera move "
    "per shot exactly as directed. "
)

NEGATIVE_PROMPT = (
    "readable text, letters, numbers, words, signage writing, invented headlines, logos, brand marks, "
    "watermark, subtitles, on-screen caption, photorealistic face, recognizable real person likeness, "
    "frontal face close-up, eyes visible in detail, blood, gore, wound, corpse, body bag, body parts, "
    "autopsy, violence, assault, strangling, weapon attack, gun, firearm, nudity, erotic content, horror "
    "monster, ghost, jump scare, 3D render look, plastic CGI, distorted anatomy, deformed hands, extra "
    "fingers, extra limbs, duplicated people, changing face, morphing objects, teleportation, jitter, "
    "flicker, whip pan, fast zoom, jump cut, split screen, collage"
)

# 事实边界与红线：每一条都会印在 抖音脚本.md 的「发布前自查」里。TODO：按本片补充/收紧，别删通用项。
PRINCIPLES = [
    "全部 Agnes 镜头为风格化 2D 动画情景重现，画面常驻标注「AI动画情景重现 · 非新闻影像」，不冒充庭审、监控或证物照片",
    "不展示遗体、血腥或侵害过程；不重现作案",
    "真实人物只以背影、剪影、手部出现，不用 AI 生成的脸冒充本人；真实人物只允许使用有出处的档案照片",
    "受害者不以任何人像出现，只用信息卡与象征物致意",
    "每一句事实都能指到 sources 里的一条公开报道；未定论的事只写「指控/承认」不写「判决」",
    "所有中文姓名、日期、字幕后期添加，不交给视频模型拼写",
    "同一地点保留光线、道具、运动方向；跨地点通过声音桥与物件匹配衔接",
    "人工检视 qa/ 接触表，露脸、畸变、伪文字、中途换场的镜头用 {\"only\":\"Sxx\"} 重生成，不直接进成片",
]

# 每条事实的公开来源。TODO：id 从 1 连续编号，usage 写清"这条来源支撑了哪几句话"。
SOURCES = [
    # {"id": 1, "url": "https://…", "usage": "支撑：…"},
]

# 六段解说：(章节 id, 章节标题, 逐字解说词)。TODO：六段合计 ≈ 760–800 字。
CHAPTERS = [
    ("N01", "TODO 黄金开头（0–5 秒最离奇的细节 → 案件名片 → 今天讲什么）", "TODO"),
    ("N02", "TODO 案件背景（人物是谁、双面人生）", "TODO"),
    ("N03", "TODO 作案手法（怎么做的、持续多久、多离谱）", "TODO"),
    ("N04", "TODO 破案关键（上）：转机", "TODO"),
    ("N05", "TODO 破案关键（下）：决定性证据", "TODO"),
    ("N06", "TODO 结局与金句（判决 → 金句 → 提问读者）", "TODO"),
]

# 每一镜：(id, kind, 运镜, 叙事职责, 衔接方式, 英文提示词 或 信息卡说明, 音效/备注)
# kind = "agnes"（AI 动画）或 "graphic"（信息卡；文案写在下面的 CARDS 里，这里只写它的作用）。
# 45 镜按成片顺序编号 S01–S45，每镜只用一次；哪几镜是信息卡、各放什么由你定
# （参考实现那部的 7 张覆盖：疾病阶段 / 人物档案 / 关键日期 / 处置方式 / 数字对比 / 机构起点 / 现代对照）。
SHOTS = [
__SHOTS__
]

# ---------------------------------------------------------------------------
# 画面上的文字（render.py 从 story.json 的 presentation 块读，不在 render.py 里写死）
# ---------------------------------------------------------------------------
CARD_HEADER = "TODO 案件档案  /  地点 · 年代"                       # 每张信息卡左上角的小字
CARD_FOOTER = "资料摘要与示意图 · 并非原始档案影像"                   # 每张信息卡左下角的小字
# 信息卡文案：镜头号 -> (大标题, 第一行, 第二行)。只写公开报道里的事实，不写推测。kind=graphic 的每一镜都要有。
CARDS = {
    # "S05": ("案名", "地点 · 年代", "一句话规模"),
}
# 片头字幕卡（0.35–4.7 秒叠在第一镜上）：两行，第二行小字
TITLE_CARD = ["TODO 主标题", "TODO 副标题"]
# 片尾卡（最后 3.8 秒）：大字提问 / 一行案件信息 / 一行金句 / 一行资料来源
END_CARD = [
    "TODO 提问读者的一句话？",
    "TODO 案名 · 年代 · 规模",
    "TODO 金句",
    "资料：TODO 来源媒体 / 原创解说 · AI动画情景重现",
]
# 字幕里描黄的关键词（人名、数字、结论词）
CAPTION_KEYWORDS = [
    # 例："关键物证", "三十年", "认罪" —— 每章两三个就够，多了等于没有
]
# 逐镜标签覆盖：默认 agnes 镜头标「AI动画情景重现 · 非新闻影像」，法庭/监狱/取证/搜查镜头要写得更具体
LABEL_OVERRIDES = {
    # "S40": "AI动画示意 · 非庭审影像",
}
# 合成音效事件：(镜头号, 类型)，类型可选 paper / phone / keys / machine / press，落在该镜开始前 0.18 秒
SFX_EVENTS = [
    # ("S04", "paper"),
]

# ---------------------------------------------------------------------------
# 发布文案（抖音脚本.md / 抖音发布文案.md 用）
# ---------------------------------------------------------------------------
TITLES = [
    "TODO 标题一（悬念 + 关键词）",
    "TODO 标题二",
    "TODO 标题三",
]
HOOK = "TODO 核心爆点一句话"
GOLDEN_LINES = [
    "TODO 金句一",
    "TODO 金句二",
    "TODO 提问读者一句话？评论区聊聊。",
]
DESCRIPTION = "TODO 抖音介绍（发布时的正文，120–200 字：三句话讲清案子 + 一句话免责 + 提问）"
QUESTION = "TODO 提问读者一句话？"
HASHTAGS = ["#悬疑", "#真实案件", "#科普", "#TODO"]

GRID = 4           # 规划网格：每镜 4 秒，45 镜 = 180 秒
AGNES_SECONDS = 7  # 每个 Agnes 镜头实际请求的时长（169 帧 @ 24 fps）
SEED_BASE = 20260921  # TODO 换成与本片有关的日期，让 seed 可追溯


def presentation():
    return {
        "card_header": CARD_HEADER, "card_footer": CARD_FOOTER,
        "cards": {sid: list(lines) for sid, lines in CARDS.items()},
        "title_card": TITLE_CARD, "end_card": END_CARD,
        "caption_keywords": CAPTION_KEYWORDS, "label_overrides": LABEL_OVERRIDES,
        "sfx_events": [list(e) for e in SFX_EVENTS],
    }


def build():
    story = json.loads(PLAN.read_text())
    assert len(SHOTS) * GRID == 180, f"{len(SHOTS)} 镜 × {GRID} 秒 ≠ 180 秒"
    assert len(story["chapters"]) == len(CHAPTERS) == 6
    assert len({sid for sid, *_ in SHOTS}) == len(SHOTS), "镜头号重复"
    cards_needed = {sid for sid, kind, *_ in SHOTS if kind == "graphic"}
    missing = sorted(cards_needed - set(CARDS))
    assert not missing, f"这些信息卡镜头在 CARDS 里没有文案：{missing}"
    story["title"] = TITLE
    story["style_prefix"] = STYLE_PREFIX
    story["negative_prompt"] = NEGATIVE_PROMPT
    story["principles"] = PRINCIPLES
    story["sources"] = SOURCES
    for chapter, (cid, title, text) in zip(story["chapters"], CHAPTERS):
        assert chapter["id"] == cid
        chapter["title"] = title
        chapter["text"] = text
    shots = []
    for i, (sid, kind, camera, purpose, transition, body, sfx) in enumerate(SHOTS):
        assert sid == f"S{i + 1:02d}", sid
        assert kind in ("agnes", "graphic"), f"{sid}: kind 只能是 agnes / graphic"
        start = i * GRID
        shots.append({
            "id": sid, "kind": kind, "start": start, "duration": GRID,
            "narration_id": f"N{min(6, start // 30 + 1):02d}",
            "prompt": body if kind == "agnes" else "",
            "purpose": purpose, "transition_out": transition,
            "graphic": body if kind == "graphic" else "",
            "seed": SEED_BASE + i + 1,
            "seconds": AGNES_SECONDS, "aspect": "16:9", "resolution": "1080p", "frame_rate": 24,
            "camera": camera, "sfx_note": sfx,
        })
    story["shots"] = shots
    story["presentation"] = presentation()
    story.setdefault("_scaffold", {})["note"] = (
        "内容由 build_story.py 一次性写入；45 镜 × 4 秒规划网格（每镜只用一次）；"
        "解说词与 screenplay.md、audio/manifest.json 三处逐字一致由 generate.py --validate 守着。")
    PLAN.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n")

    manifest = json.loads(MANIFEST.read_text())
    for clip, chapter in zip(manifest["clips"], story["chapters"]):
        assert clip["id"] == chapter["id"]
        clip["text"] = chapter["text"]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    kinds = [s["kind"] for s in story["shots"]]
    print(f"story.json 已写入：{len(shots)} 镜 = {kinds.count('agnes')} agnes + {kinds.count('graphic')} graphic，"
          f"解说 {sum(len(c['text']) for c in story['chapters'])} 字（含标点）")
    todo = json.dumps(story, ensure_ascii=False).count("TODO") + json.dumps(presentation(), ensure_ascii=False).count("TODO")
    if todo:
        print(f"注意：还有 {todo} 处 TODO 没填，generate.py --validate 不会放行", file=sys.stderr)


if __name__ == "__main__":
    if "--script" in sys.argv:
        from script_table import render_document  # noqa: E402  (同目录)
        out = HERE / "抖音脚本.md"
        out.write_text(render_document())
        print(f"抖音脚本.md 已写入（{len(out.read_text())} 字符）")
    elif "--publish" in sys.argv:
        from script_table import publish_document  # noqa: E402  (同目录)
        out = HERE / "抖音发布文案.md"
        out.write_text(publish_document())
        print(f"抖音发布文案.md 已写入（{len(out.read_text())} 字符）")
    else:
        build()
