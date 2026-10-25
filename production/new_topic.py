#!/usr/bin/env python3
"""新题目开工脚手架（狂犬病模式）：以《狂犬病疫苗：一百四十年前那场赌局》为参考实现，开出一个可以独立编辑的项目目录。

用法::

    python3 production/new_topic.py --slug ripper1888 \\
        --title "开膛手杰克：1888 年的秋天" \\
        --branch arena/xxxx-desktop-tutorial

它做的事（不改参考项目一个字节）：

1. **复制**流水线引擎到 ``production/<slug>/``：
   ``media / throttle / align_audio / build_audio / generate / fetch_sources / watch_run``
   + 中文配音那部新增的 ``tighten_pauses``（收紧 TTS 停顿）和 ``clause_times``（分句对时间 + CUTS 校验）
   + **检验工具链**：``qc_shots``（逐镜接触表初筛）、``audit_frame_distortions``（成片全帧审计）、
   ``compose_all_frame_sheets``（5400 张全帧接触表）、``export_visual_review_candidates``（候选帧导出）、
   ``publish_visual_review_bundle``（把审片证据写回仓库）——狂犬病那部就是靠这条链子才查出
   "片尾卡一行字越出画面"这种自动审计量不到的缺陷；
2. **替换**副本里所有 ``production/rabies1885``、``work/rabies1885``、分支名、片名、Actions 并发组名；
3. 从 ``production/templates/`` **渲染**三份"内容与引擎分离"的文件：
   ``build_story.py``（唯一内容源：解说词 / 45 镜 / 信息卡文案 / 字幕高亮词 / 发布文案，全是 TODO）、
   ``render.py``（引擎；只有 CUTS 和看片后的镜头修正属于本片）、``script_table.py``（抖音脚本 / 发布文案生成）；
4. **生成**骨架：``story.json``（45 镜 × 4 秒、6 章 × 30 秒的时间轴已算好）、``screenplay.md``、
   ``audio/manifest.json``、``README.md``（待办清单），以及 ``workflows/`` 下四份 marker 触发的工作流
   （生成 / 出片 / 逐字听检 / **全帧视觉 QC**；Release 上传用仓库里通用的 ``release-upload.yml``）。

生成的项目**故意过不了** ``generate.py --validate``：解说词、提示词、配音、SHA-256 都是空的，
必须人来填（填在 ``build_story.py`` 里，跑一次 ``build_story.py`` 写进 story.json）。
这是设计，不是缺陷——参考项目的前身里"无声成片"就是被一道只看容器字段的校验放过去的。

参考实现只在被复制时被读取，永不写入（``test_new_topic.py::test_reference_project_is_untouched``）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # production/
ROOT = HERE.parent                              # repo root
REFERENCE = HERE / "rabies1885"
TEMPLATES = HERE / "templates"

# 参考项目里原样复制的流水线引擎（内容无关，只需换路径/分支/片名）。
ENGINE_FILES = (
    "media.py",
    "throttle.py",
    "align_audio.py",
    "build_audio.py",
    "generate.py",
    "fetch_sources.py",
    "watch_run.py",
    "tighten_pauses.py",
    "clause_times.py",
    # 参考项目本部新增的检验工具链：逐镜初筛 + 成片全帧审计 + 证据打包
    "qc_shots.py",
    "audit_frame_distortions.py",
    "compose_all_frame_sheets.py",
    "export_visual_review_candidates.py",
    "publish_visual_review_bundle.py",
    # 人看的两个本地页面（镜头复审、制作进度），可选但跟着复制过去
    "review_app.py",
    "progress_app.py",
)
# production/templates/ 里"内容与引擎分离"的文件：占位符由本脚本替换。
TEMPLATE_FILES = ("render.py", "build_story.py", "script_table.py")
WORKFLOW_TEMPLATES = {
    "gen.workflow.yml": "{slug}-gen.yml",
    "render.workflow.yml": "{slug}-render.yml",
    "verbatim.workflow.yml": "{slug}-verbatim.yml",
    "visual-qc.workflow.yml": "{slug}-visual-qc.yml",
}

# 参考项目的固定标识 -> 新项目标识。顺序有意义：先长串后短串。
# 2026-10-06 起参考实现是《狂犬病疫苗：一百四十年前那场赌局》（production/rabies1885）：
# 它是唯一跑通"全帧视觉 QC + 卡片排字闸门 + 人工语义签收"三步的成片，
# 也带着本部踩出来的两个真缺陷的修法（片尾卡裁字、S18 取景窗）。
REFERENCE_SLUG = "rabies1885"
REFERENCE_BRANCH = "arena/cb25986c-desktop-tutorial"
REFERENCE_TITLE = "狂犬病疫苗：一百四十年前那场赌局"
REFERENCE_FILM = "狂犬病疫苗_一百四十年前那场赌局_三分钟_带声音.mp4"

SHOT_COUNT = 45
GRID = 4
CHAPTER_COUNT = 6
CHAPTER_LENGTH = 30
AGNES_SECONDS = 7

CUTS_BLOCK = re.compile(r"^CUTS = \{.*?^\}", re.M | re.S)


def film_name(title: str) -> str:
    """片名 -> 成片文件名：狂犬病疫苗：一百四十年前那场赌局 -> 狂犬病疫苗_一百四十年前那场赌局_三分钟_带声音.mp4"""
    safe = re.sub(r'[\\/:*?"<>|：]', "_", title).strip("_ ") or "untitled"
    return f"{safe}_三分钟_带声音.mp4"


# --------------------------------------------------------------------------
# 文本替换
# --------------------------------------------------------------------------
def substitutions(slug: str, branch: str, title: str) -> tuple[tuple[str, str], ...]:
    """参考项目标识到新项目标识的替换表（长串优先，避免半截替换）。"""
    short_branch = branch.rsplit("/", 1)[-1] if branch else slug
    return (
        (REFERENCE_BRANCH, branch),
        (f"production/{REFERENCE_SLUG}", f"production/{slug}"),
        (f"work/{REFERENCE_SLUG}", f"work/{slug}"),
        (f"arena-{REFERENCE_SLUG}-refetch", f"arena-{slug}-refetch"),
        (f"{REFERENCE_SLUG}-agnes-", f"{slug}-agnes-"),
        (f"{REFERENCE_SLUG}-render-arena-", f"{slug}-render-arena-"),
        (f"'{REFERENCE_SLUG}: '", f"'{slug}: '"),
        (REFERENCE_FILM, film_name(title)),
        (REFERENCE_TITLE, title),
        ("cb25986c-desktop-tutorial", short_branch),
        # 兜底：任何漏网的旧 slug / 旧片名都换掉，副本里不残留旧品牌
        (REFERENCE_SLUG, slug),
        ("狂犬病疫苗：一百四十年前那场赌局", title),
        ("一百四十年前那场赌局", title),
        ("狂犬病疫苗", title),
    )


def patch(text: str, slug: str, branch: str, title: str) -> str:
    for old, new in substitutions(slug, branch, title):
        text = text.replace(old, new)
    return text


def template_substitutions(slug: str, branch: str, title: str) -> tuple[tuple[str, str], ...]:
    short_branch = branch.rsplit("/", 1)[-1] if branch else slug
    return (
        ("__SHORT_BRANCH__", short_branch),
        ("__BRANCH__", branch),
        ("__SLUG__", slug),
        ("__TITLE__", title),
        ("__FILM__", film_name(title)),
    )


def render_template(name: str, slug: str, branch: str, title: str, templates: Path) -> str:
    text = (templates / name).read_text(encoding="utf-8")
    for old, new in template_substitutions(slug, branch, title):
        text = text.replace(old, new)
    return text


# --------------------------------------------------------------------------
# 骨架内容
# --------------------------------------------------------------------------
def chapter_of(start: int) -> str:
    return f"N{min(CHAPTER_COUNT, start // CHAPTER_LENGTH + 1):02d}"


def starter_story(slug: str, branch: str, title: str, reference: Path) -> dict:
    """按参考项目的分镜结构生成骨架：45 镜 × 4 秒规划网格、6 章 × 30 秒。

    时间轴、分辨率、帧率这些"机械正确"的部分直接算好；提示词与解说词留空，
    留给人写（写在 build_story.py 里）——空的提示词会让 ``validate()`` 直接报错。
    """
    ref_story = json.loads((reference / "story.json").read_text(encoding="utf-8"))
    ref_shot = next(s for s in ref_story["shots"] if s["kind"] == "agnes")

    shots = []
    for index in range(SHOT_COUNT):
        start = index * GRID
        shots.append({
            "id": f"S{index + 1:02d}",
            "kind": "agnes",
            "start": start,
            "duration": GRID,
            "narration_id": chapter_of(start),
            "prompt": "",                      # TODO 人来写（build_story.py 的 SHOTS）
            "purpose": "",
            "transition_out": "",
            "graphic": "",
            "seed": 1000 + index,
            "seconds": ref_shot.get("seconds", AGNES_SECONDS),
            "aspect": ref_shot.get("aspect", "16:9"),
            "resolution": ref_shot.get("resolution", "1080p"),
            "frame_rate": ref_shot.get("frame_rate", 24),
        })

    chapters = []
    for index in range(CHAPTER_COUNT):
        chapters.append({
            "id": f"N{index + 1:02d}",
            "title": "",                       # TODO 章节标题
            "start": index * CHAPTER_LENGTH,
            "duration": CHAPTER_LENGTH,
            "text": "",                        # TODO 解说词（六段合计 ≈ 760–800 字）
        })

    return {
        "title": title,
        "target_duration": SHOT_COUNT * GRID,
        "width": ref_story.get("width", 1920),
        "height": ref_story.get("height", 1080),
        "fps": ref_story.get("fps", 30),
        "model": ref_story.get("model", "agnes-video-v2.0"),
        "branch": branch,
        "style_prefix": "",                    # TODO build_story.py 的 STYLE_PREFIX
        "negative_prompt": ref_story.get("negative_prompt", ""),
        "principles": [],
        "chapters": chapters,
        "shots": shots,
        "sources": [],
        "presentation": {},                    # build_story.py 写入：信息卡文案、片头/片尾卡、字幕高亮词、标签、音效
        "_scaffold": {
            "reference": f"production/{REFERENCE_SLUG}",
            "generator": "production/new_topic.py",
            "slug": slug,
            "note": f"{SHOT_COUNT} 镜 × {GRID} 秒 / 6 章 × 30 秒 的骨架已算好；内容写在 build_story.py 里，"
                    "跑一次 build_story.py 才会进 story.json；提示词、解说词、style_prefix、principles、"
                    "sources 必须填完才能通过 --validate。",
        },
    }


def chapter_shots(story: dict) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for shot in story["shots"]:
        grouped.setdefault(shot["narration_id"], []).append(shot["id"])
    return grouped


def cuts_skeleton(story: dict) -> str:
    """按 story.json 生成 render.py 的 CUTS 剪辑表骨架（每章第一个切点必须是 0）。

    参考项目里 CUTS 的时间点是按 audio/clause-times.json 的分句边界对出来的；这里只给一个
    均匀起点（每 4 秒一切），拿到配音后必须重对，并用 clause_times.py --check-cuts 校验。
    """
    lines = ["CUTS = {"]
    for cue, shots in chapter_shots(story).items():
        body = ", ".join(f"({slot * GRID},'{shot}','')" for slot, shot in enumerate(shots))
        lines.append(f"    '{cue}': [{body}],")
    lines.append("}")
    return "\n".join(lines)


def shots_skeleton(story: dict) -> str:
    """build_story.py 里 SHOTS 的 45 个占位元组（按章分组，带 TODO）。"""
    lines = []
    for cue, shots in chapter_shots(story).items():
        lines.append(f"    # ---------------- {cue}（{len(shots)} 镜）----------------")
        for shot in shots:
            lines.append(
                f'    ("{shot}", "agnes", "TODO 运镜", "TODO 叙事职责", "TODO 衔接方式",\n'
                f'     "TODO English prompt: one place, one camera move, no faces, no readable text, HOLD sentence",\n'
                f'     "TODO 音效备注"),')
    return "\n".join(lines)


def starter_screenplay(title: str, story: dict) -> str:
    head = [
        f"# {title}",
        "",
        "三分钟横屏解说 · 成片目标 "
        f"{story['width']}×{story['height']} / {story['fps']} fps / {story['target_duration']} 秒",
        "",
        "## 事实边界",
        "",
        "TODO 写清楚：哪些是公开资料可证的事实，哪些是情景重现，哪些坚决不写。",
        "这一段是这部片子的底线，比任何画面都重要（参考 `production/rabies1885/screenplay.md`）。",
        "",
        "## 解说稿与时间线",
        "",
    ]
    sections = []
    for chapter in story["chapters"]:
        start = chapter["start"]
        end = start + chapter["duration"]
        sections.append(
            f"### {start // 60:02d}:{start % 60:02d}—{end // 60:02d}:{end % 60:02d}"
            f"　TODO 章节标题（{chapter['id']}）\n\n"
            "TODO 解说词。六段合计约 760–800 字；写在 `build_story.py` 的 CHAPTERS 里，跑一次 "
            "`build_story.py` 会同步进 `story.json` 的 `chapters[].text` 和 `audio/manifest.json` 的 "
            "`clips[].text`；这里再抄一遍，三处必须逐字一致，否则 `generate.py` 会拒绝出片。\n"
        )
    table = [
        "## 分镜与衔接",
        "",
        "| 镜头 | 规划时间 | 类型 | 叙事职责 | 衔接方式 |",
        "|---|---|---|---|---|",
    ]
    grouped = chapter_shots(story)
    for cue, shots in grouped.items():
        for shot_id in shots:
            shot = next(s for s in story["shots"] if s["id"] == shot_id)
            start = shot["start"]
            table.append(
                f"| {shot['id']} | {start:03d}—{start + shot['duration']:03d}s | "
                f"{shot['kind']} | TODO | TODO |"
            )
        table.append(f"| — | — | 解说 {cue} 结束 | — | — |")
    return "\n".join(head + sections + table) + "\n"


def starter_manifest(story: dict) -> dict:
    return {
        "voice_id": "",
        "language": "zh-CN",
        "selection": "TODO 用户试听后选定的音色（add_voice 的 voice_id）",
        "clips": [
            {"id": chapter["id"], "file": f"{chapter['id']}.mp3", "sha256": "", "text": ""}
            for chapter in story["chapters"]
        ],
        "post_processing": "TODO tighten_pauses.py 收紧停顿后的说明（原始 TTS 在 audio/raw/）",
    }


def starter_readme(slug: str, title: str, branch: str) -> str:
    film = film_name(title)
    return f"""# {title}

由 `production/new_topic.py` 从参考项目 `production/rabies1885`（《狂犬病疫苗：一百四十年前那场赌局》，已成片、已发布）
开出来的新项目目录。参考实现只被复制，没有被修改；本片的所有编辑都发生在这个目录里。
流程细节见仓库根目录的 `新题目开工手册.md`。

- slug：`{slug}`　出片分支：`{branch}`　成片文件名：`{film}`
- 规格：1920×1080 / 30 fps / 180 秒；**45 镜 = 38 个 Agnes 动画镜头 + 7 张信息卡（比例可调），每个镜头只出现一次**

## 现在还不能出片（故意的）

`generate.py --validate` 现在**会失败**，因为解说词、提示词、配音都是空的。按下面顺序填完，它才会放行。

## 待办清单（狂犬病模式）

1. **事实与红线** → `build_story.py` 的 `SOURCES` / `PRINCIPLES`，`screenplay.md` 的「事实边界」。每句话都要有公开来源。
2. **解说稿** → `build_story.py` 的 `CHAPTERS`：六段合计 ≈ 760–800 字，数字写中文读法，每段末尾留钩子，不写血腥细节。
3. **分镜** → `build_story.py` 的 `SHOTS`（45 个元组）：哪几镜是信息卡（`kind="graphic"`）由你定，信息卡文案写进 `CARDS`；
   提示词先钉死唯一场景、再排除别的场景、最后加 HOLD 句。`TITLE_CARD` / `END_CARD` / `CAPTION_KEYWORDS` /
   `LABEL_OVERRIDES` / `SFX_EVENTS` 也在这里。写完跑：

   ```bash
   python3 production/{slug}/build_story.py          # 写 story.json + audio/manifest.json 的逐字文本
   ```

4. **配音** → 试音选定音色 → 六段 TTS 放 `audio/raw/N0x.mp3` → 收紧停顿、对分句时间、填 SHA-256：

   ```bash
   python3 production/{slug}/tighten_pauses.py       # raw/ -> audio/N0x.mp3，写 audio/tighten-report.json
   python3 production/{slug}/clause_times.py         # 写 audio/clause-times.json
   sha256sum production/{slug}/audio/N0*.mp3         # 填进 audio/manifest.json 的 sha256，voice_id 也要填
   python3 production/{slug}/generate.py --validate  # 闸门一
   ```

5. **生成素材** → 把 `workflows/` 下四份（`{slug}-gen.yml` / `-render.yml` / `-verbatim.yml` / `-visual-qc.yml`）复制到
   `.github/workflows/`（需要 workflows 写权限），然后写 `GEN_REQUEST`（`{{"workers":2}}`）并 push；
   `watch_run.py` 拉回 `results.json` 与 `qa/` 接触表；逐镜初筛可跑 `qc_shots.py`（黑帧 / 冻结 / 中途换场 /
   伪文字 / 人脸 / 手部几何），看完再用 `review_app.py` 把要重做的镜头勾成 `REDO.json`。
6. **复审** → 逐镜看 `qa/Sxx.jpg`（14 帧）：画的是不是这一镜的场景、7 秒内有没有换场、有没有脸/可读伪文字/遗体。
   坏镜头只改它的 prompt，`GEN_REQUEST` 写 `{{"workers":2,"only":"S03,S08"}}` 重做，其余按 SHA-256 复用。
7. **剪辑表** → `render.py` 的 `CUTS` 骨架是 4 秒均匀一切，**必须**按 `audio/clause-times.json` 重对
   （切点落在分句起点前 0.15 s 左右），然后：

   ```bash
   python3 production/{slug}/clause_times.py --check-cuts   # 每个切点都要在停顿窗内
   ```

8. **出片** → 写 `RENDER_REQUEST` 并 push；成片 commit 回 `交付/{film}`，报告在 `delivery/`。
   复检：按 EDL 逐段抽帧看画面/字幕/标签；按分句起点前后 0.25 s 抽帧核对字幕切换。
9. **听检** → 写 `VERBATIM_REQUEST` 并 push；`delivery/verbatim-check.json` 六章 CER 都要 ≤ 0.15。
10. **全帧视觉 QC** → 写 `VISUAL_QC_REQUEST` 并 push；工作流解码成片**每一帧**（5400/5400），
    输出 `delivery/frame-distortion-audit.md`、`visual-qc-summary.json` 与 `qa/final-frame-review/`
    （全帧接触表 + 手部动态表 + 原始分辨率候选帧）。自动结果是**分诊**，不是签收。
11. **人工语义签收** → 逐张看完候选帧再决定：片尾卡与信息卡**有没有字被画面裁掉**
    （自动审计不量这个！本部就是在这一步发现片尾卡问句两端缺字的）、人脸是不是误检、
    手部是否畸变、有没有可读伪文字。确认无问题才动 Release；有问题回对应步骤修完重渲。
    卡片排字有闸门守着：`production/tests/test_card_typography.py`（**通用**，自动扫 production/*/，
    有 `presentation.end_card` 的项目都会被真画一遍卡片、量左右 100 px 安全带，不用照抄）。
12. **发布** → `gh release create <tag>` + 写 `RELEASE_UPLOAD_REQUEST`（tag / src / asset）；
    `build_story.py --script` 生成 `抖音脚本.md`，`build_story.py --publish` 生成 `抖音发布文案.md`。

## 目录

| 路径 | 作用 |
|---|---|
| `build_story.py` | **唯一内容源**：解说词、45 镜、信息卡文案、片头/片尾卡、字幕高亮词、标签、音效事件、发布文案 |
| `story.json` | 分镜计划：45 镜 × 4 秒、6 章 × 30 秒（由 build_story.py 写入，含 `presentation` 块） |
| `screenplay.md` | 解说稿 + 事实边界 + 分镜表 |
| `script_table.py` | 由 story.json + CUTS + 分句时间生成 `抖音脚本.md` / `抖音发布文案.md` |
| `audio/raw/` → `audio/N0x.mp3` | TTS 原始输出 → 收紧停顿后的配音（manifest 的 SHA-256 记的是后者） |
| `audio/manifest.json` / `clause-times.json` / `tighten-report.json` | 配音收据、分句时间、收紧报告 |
| `tighten_pauses.py` / `clause_times.py` | 收紧停顿；分句对时间 + `--check-cuts` |
| `generate.py` | 生成 Agnes 素材（75 秒节流、断点续跑、`--prune-failed`）+ `--validate` 闸门 |
| `fetch_sources.py` / `watch_run.py` | 按 SHA-256 回填素材；从分支拉回 results/qa/delivery |
| `render.py` | 剪辑引擎：CUTS（每镜只用一次，有断言）、信息卡（排字自适应缩号）、字幕（ASR → clause-times → 估算）、混音、成品复测 |
| `build_audio.py` / `align_audio.py` / `media.py` / `throttle.py` | 公共实现（副本） |
| `qc_shots.py` | 逐镜初筛：黑帧 / 冻结 / 中途换场 / 伪文字 / 人脸 / 手部几何 / 色温颗粒 |
| `audit_frame_distortions.py` / `compose_all_frame_sheets.py` / `export_visual_review_candidates.py` / `publish_visual_review_bundle.py` | 成片全帧审计 → 全帧接触表 → 候选帧 → 审片证据写回仓库 |
| `review_app.py` / `progress_app.py` | 本地页面：勾选要重做的镜头（`REDO.json`）；一屏看制作进度 |
| `workflows/` | 四份 marker 触发的工作流（生成 / 出片 / 听检 / 全帧视觉 QC），复制到 `.github/workflows/` 才生效 |
| `GEN_REQUEST` / `RENDER_REQUEST` / `VERBATIM_REQUEST` / `VISUAL_QC_REQUEST` / `RELEASE_UPLOAD_REQUEST` | push 触发工作流的 marker 文件（按需创建） |
| `../run_project.sh` | **所有项目共用**的出片脚本：`bash production/run_project.sh {slug}` |

## 红线（继承自参考项目，不要删）

- AI 画面一律标注「AI动画情景重现 · 非新闻影像」，不冒充真实影像；
- 真实人物只以背影、剪影、手出现，不用 AI 生成的脸冒充本人；受害者不以人像出现；
- 不展示遗体、血腥或侵害过程；未定论的事不写成结论；
- 中文姓名、日期、字幕一律后期添加，不交给视频模型拼写；
- 成片必须实测电平（`--validate` 之后还有 `render.py` 的成品复测），无声不许交付；
- 每个镜头只出现一次，不复用（`render.py` 的 `make_edl` 有断言）；
- **卡片上的一行字不许越出画面**：`render.py` 的 `centered()` 会按 `max_width` 缩号，放不下直接报错。
  狂犬病那部的片尾卡问句曾按固定 96 px 排出 2304 px 宽、两端各裁掉两个字，而三道自动闸门全是绿的
  —— 自动审计只量黑帧、冻结、帧间差异和人脸/手，**从不量文字溢出**。
"""


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def scaffold(slug: str, title: str, branch: str, dest: Path, reference: Path,
             templates: Path = TEMPLATES) -> Path:
    if not reference.is_dir():
        raise SystemExit(f"参考项目不存在：{reference}")
    if not templates.is_dir():
        raise SystemExit(f"模板目录不存在：{templates}")
    missing = [name for name in ENGINE_FILES if not (reference / name).is_file()]
    if missing:
        raise SystemExit(f"参考项目缺少引擎文件：{', '.join(missing)}")
    missing = [name for name in (*TEMPLATE_FILES, *WORKFLOW_TEMPLATES) if not (templates / name).is_file()]
    if missing:
        raise SystemExit(f"模板目录缺少：{', '.join(missing)}")
    if dest.exists():
        raise SystemExit(f"目标目录已存在，先删掉或换一个 slug：{dest}")

    dest.mkdir(parents=True)
    (dest / "audio" / "raw").mkdir(parents=True)
    (dest / "workflows").mkdir()

    story = starter_story(slug, branch, title, reference)

    for name in ENGINE_FILES:
        text = (reference / name).read_text(encoding="utf-8")
        (dest / name).write_text(patch(text, slug, branch, title), encoding="utf-8")

    for name in TEMPLATE_FILES:
        text = render_template(name, slug, branch, title, templates)
        if name == "render.py":
            text, hits = CUTS_BLOCK.subn(lambda _m: cuts_skeleton(story), text, count=1)
            if hits != 1:
                raise SystemExit("模板 render.py 里找不到 CUTS 剪辑表，脚手架已中止")
        if name == "build_story.py":
            if "__SHOTS__" not in text:
                raise SystemExit("模板 build_story.py 里找不到 __SHOTS__ 占位，脚手架已中止")
            text = text.replace("__SHOTS__", shots_skeleton(story))
        (dest / name).write_text(text, encoding="utf-8")

    for name, target in WORKFLOW_TEMPLATES.items():
        (dest / "workflows" / target.format(slug=slug)).write_text(
            render_template(name, slug, branch, title, templates), encoding="utf-8")

    (dest / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "screenplay.md").write_text(starter_screenplay(title, story), encoding="utf-8")
    (dest / "audio" / "manifest.json").write_text(
        json.dumps(starter_manifest(story), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(starter_readme(slug, title, branch), encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True, help="新项目目录名，小写字母数字，如 ripper1888")
    parser.add_argument("--title", required=True, help="中文片名，如 开膛手杰克：1888 年的秋天")
    parser.add_argument("--branch", default="", help="出片分支（默认取当前 git 分支）")
    parser.add_argument("--dest", type=Path, default=None,
                        help="项目目录（默认 production/<slug>）")
    parser.add_argument("--reference", type=Path, default=REFERENCE,
                        help="参考项目目录（默认 production/rabies1885）")
    parser.add_argument("--templates", type=Path, default=TEMPLATES,
                        help="模板目录（默认 production/templates）")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", args.slug):
        raise SystemExit("slug 只能是小写字母、数字、下划线，且以字母开头")

    branch = args.branch
    if not branch:
        import subprocess
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
    if not branch:
        raise SystemExit("取不到当前分支，请用 --branch 指定出片分支")

    dest = args.dest or (HERE / args.slug)
    created = scaffold(args.slug, args.title, branch, dest, args.reference, args.templates)

    print(f"已开出新项目：{created.relative_to(ROOT) if created.is_relative_to(ROOT) else created}")
    print(f"  出片分支：{branch}")
    print(f"  下一步：填 {created.name}/build_story.py（解说词 / 45 镜 / 信息卡 / 发布文案），")
    print(f"        跑 python3 production/{args.slug}/build_story.py 写入 story.json，")
    print(f"        再跑 python3 production/{args.slug}/generate.py --validate")
    print(f"  工作流：把 {created.name}/workflows/*.yml 复制到 .github/workflows/ 才能用 marker 文件触发")
    return 0


if __name__ == "__main__":
    sys.exit(main())
