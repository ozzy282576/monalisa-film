#!/usr/bin/env python3
"""把 story.json + render.py 的 CUTS + 配音分句时间，拼成抖音脚本的四列分镜表和发布文案。

四列：时间轴 / 口播文案 / 画面描述（动画建议）/ 音效备注。
- 时间轴：按 render.py 的排版常数（INTRO/GAP/OUTRO）和收紧后配音的实际时长算出的成片时间；
- 口播文案：CHAPTERS 里的原句，按 CUTS 切点分到每个镜头下（分句时间来自 audio/clause-times.json）；
- 画面描述：story.json 里每镜的 purpose + camera（中文），不重复抄英文提示词；
- 音效备注：story.json 的 sfx_note。

标题 / 核心爆点 / 金句 / 抖音介绍 / 提问读者 / 话题 全部来自 build_story.py（唯一内容源），
这样《抖音脚本.md》《抖音发布文案.md》《screenplay.md》《story.json》《render.py》说的是同一份数据。

    python3 production/<slug>/build_story.py --script    # 抖音脚本.md
    python3 production/<slug>/build_story.py --publish   # 抖音发布文案.md
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load():
    import render  # noqa: E402  (同目录；只取常数与 CUTS)
    story = json.loads((HERE / "story.json").read_text())
    clause_times = json.loads((HERE / "audio" / "clause-times.json").read_text())
    report = json.loads((HERE / "audio" / "tighten-report.json").read_text())
    durations = {row["id"]: row["tight_seconds"] for row in report["clips"]}
    usable = render.DURATION - render.INTRO - render.OUTRO - render.GAP * (len(story["chapters"]) - 1)
    tempo = sum(durations.values()) / usable
    return render, story, clause_times, durations, tempo


def segments():
    render, story, clause_times, durations, tempo = load()
    by_id = {s["id"]: s for s in story["shots"]}
    rows = []
    start = render.INTRO
    chapters = story["chapters"]
    for i, ch in enumerate(chapters):
        cid = ch["id"]
        cuts = render.CUTS[cid]
        clauses = clause_times[cid]["clauses"]
        chapter_end = (start + durations[cid] / tempo + render.GAP) if i + 1 < len(chapters) else render.END_AT
        for j, (raw, sid, _variant) in enumerate(cuts):
            seg_start = 0.0 if (i == 0 and j == 0) else start + raw / tempo
            seg_end = (start + cuts[j + 1][0] / tempo) if j + 1 < len(cuts) else chapter_end
            next_raw = cuts[j + 1][0] if j + 1 < len(cuts) else 1e9
            text = "".join(c["text"] + punct_after(ch["text"], c["text"])
                           for c in clauses if raw <= c["start"] + 0.05 < next_raw)
            shot = by_id[sid]
            rows.append({"id": sid, "kind": shot["kind"], "chapter": cid, "start": seg_start, "end": seg_end,
                         "text": text, "purpose": shot["purpose"], "camera": shot.get("camera", ""),
                         "sfx": shot.get("sfx_note", ""), "graphic": shot.get("graphic", "")})
        start += durations[cid] / tempo + render.GAP
    end_card = (story.get("presentation") or {}).get("end_card") or ["", ""]
    rows.append({"id": "END", "kind": "graphic", "chapter": chapters[-1]["id"], "start": render.END_AT,
                 "end": render.DURATION, "text": "",
                 "purpose": f"片尾卡：把互动问题「{end_card[0]}」留在屏幕上，附资料来源",
                 "camera": "静态卡 + 淡出", "sfx": "音乐尾音，最后 0.8 秒渐隐", "graphic": ""})
    return rows, tempo


def punct_after(full, clause):
    """把分句后面紧跟的标点找回来（clause-times 里的分句是去掉标点的）。"""
    i = full.find(clause)
    if i < 0:
        return ""
    j = i + len(clause)
    m = re.match(r"[，。！？；：、—]+", full[j:])
    return m.group(0) if m else ""


def clock(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def render_table():
    rows, tempo = segments()
    story = json.loads((HERE / "story.json").read_text())
    chapter_names = {c["id"]: c["title"] for c in story["chapters"]}
    out = ["| 时间轴 | 口播文案 | 画面描述（动画建议） | 音效备注 |", "|---|---|---|---|"]
    seen = set()
    for r in rows:
        if r["chapter"] not in seen and r["id"] != "END":
            seen.add(r["chapter"])
            out.append(f"| **{chapter_names[r['chapter']]}** | | | |")
        kind = "信息卡" if r["kind"] == "graphic" else "AI动画"
        picture = f"【{r['id']} · {kind}】{r['purpose']}（运镜：{r['camera']}）"
        text = r["text"] if r["text"] else "（无口播，画面收尾）"
        out.append(f"| {clock(r['start'])}–{clock(r['end'])} | {text} | {picture} | {r['sfx']} |")
    return "\n".join(out)


def _content():
    import build_story  # noqa: E402  (同目录；唯一内容源)
    return build_story


def render_document():
    c = _content()
    rows, tempo = segments()
    story = json.loads((HERE / "story.json").read_text())
    total_chars = sum(len(re.sub(r"[，。！？；：、—]", "", ch["text"])) for ch in story["chapters"])
    agnes = sum(s["kind"] == "agnes" for s in story["shots"])
    cards = sum(s["kind"] == "graphic" for s in story["shots"])
    end_card = (story.get("presentation") or {}).get("end_card") or ["", "", ""]
    doc = [f"# 抖音脚本 · {story['title']}", "",
           "> 横版 16:9 · 1920×1080 · 30fps · 成片 180 秒（口播 ≈ 176 秒、"
           f"{total_chars} 字）· {len(story['shots'])} 个镜头（{agnes} 个 Agnes AI 动画镜头 + {cards} 张信息卡，"
           "每个镜头只出现一次）· 风格：沉稳男声科普解说 + 超写实 3D 动画情景重现（近黑 / 棕褐 / 橄榄、暖调、强反差、35mm 颗粒；真人只背影、剪影或手）", "",
           "## 一、视频标题（三选一）", ""]
    doc += [f"{i}. {t}" for i, t in enumerate(c.TITLES, 1)]
    doc += ["", "## 二、核心爆点（一句话）", "", c.HOOK, "",
            "## 三、详细脚本（时间轴 / 口播文案 / 画面描述 / 音效备注）", "",
            "口播文案与成片配音**逐字一致**（`audio/manifest.json` 里有 SHA-256 收据）；"
            f"时间轴按收紧停顿后的真实配音时长算出，成片以 `production/{HERE.name}/delivery/edit-decision-list.json` 为准。", "",
            render_table(), "",
            "## 四、金句结尾（引导评论）", ""]
    doc += [f"- {line}" for line in c.GOLDEN_LINES]
    doc += ["", f"片尾卡停留 3.8 秒：**「{end_card[0]}」** + 「{end_card[2] if len(end_card) > 2 else ''}」+ 资料来源。", "",
            "## 五、事实边界（发布前自查）", ""]
    doc += [f"- {p}" for p in story["principles"]]
    doc += ["", "## 六、资料来源", ""]
    doc += [f"{src['id']}. {src['url']} —— {src['usage']}" for src in story["sources"]]
    doc.append("")
    return "\n".join(doc)


def publish_document():
    c = _content()
    story = json.loads((HERE / "story.json").read_text())
    doc = [f"# 抖音发布文案 · {story['title']}", "",
           "> 横版 16:9 · 180 秒 · 发布时从下面三个标题里选一个，介绍直接粘贴，提问放在评论区置顶。", "",
           "## 题目（三选一）", ""]
    doc += [f"{i}. {t}" for i, t in enumerate(c.TITLES, 1)]
    doc += ["", "## 抖音介绍（视频正文）", "", c.DESCRIPTION, "", " ".join(c.HASHTAGS), "",
            "## 提问读者一句话（置顶评论 / 片尾卡）", "", c.QUESTION, "",
            "## 金句（可做封面文字）", ""]
    doc += [f"- {line}" for line in c.GOLDEN_LINES]
    doc += ["", "## 发布前自查", "",
            "- 成片、字幕、脚本三处口播逐字一致（`generate.py --validate` + `delivery/verbatim-check.json`）",
            "- 画面常驻「AI动画情景重现 · 非新闻影像」标签，介绍里也写明是动画情景重现",
            "- 介绍里的每个事实都能在 `抖音脚本.md` 第六节的来源里找到", ""]
    return "\n".join(doc)


if __name__ == "__main__":
    if "--write" in sys.argv:
        out = HERE / "抖音脚本.md"
        out.write_text(render_document())
        print("written", out)
    elif "--publish" in sys.argv:
        out = HERE / "抖音发布文案.md"
        out.write_text(publish_document())
        print("written", out)
    else:
        print(render_table())
