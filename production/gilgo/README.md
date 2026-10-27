# 吉尔戈海滩：披萨盒里的凶手

抖音横版三分钟悬疑科普解说（长岛吉尔戈海滩连环案 / Rex Heuermann），
由 `production/new_topic.py` 从参考项目 `production/dahlia` 开出来、按 `新题目开工手册.md` 走完的项目。
参考实现只被复制，没有被修改；本片的所有编辑都发生在这个目录里。

- slug：`gilgo`　出片分支：`arena/01a0c30d-desktop-tutorial`
- 成片规格：1920×1080 / 30 fps / 180 秒 / AAC 立体声
- 画面：**45 个镜头 = 38 个 Agnes Video V2.0 二维动画镜头 + 7 张信息卡，每个镜头只出现一次（不复用）**
- 配音：voice-00（用户试听选定），六段合计 176.1 秒，`render.py` 整体变速 1.048×

## 交付物

| 文件 | 内容 |
|---|---|
| `抖音脚本.md` | 用户要的脚本：3 个标题、核心爆点、四列分镜表（时间轴 / 口播文案 / 画面描述 / 音效备注）、金句结尾 |
| `抖音发布文案.md` | 发布用：题目三选一、抖音介绍、提问读者一句话、话题、金句（`build_story.py --publish`） |
| `screenplay.md` | 事实边界 + 六段逐字解说稿 + 分镜与衔接表 + 信息卡文案 + 来源 |
| `交付/吉尔戈海滩_披萨盒里的凶手_三分钟_带声音.mp4` | 成片（由出片工作流 commit 回分支） |
| `delivery/` | 成片的 EDL、字幕（srt）、音频实测报告、接触表 |
| `qa/Sxx.jpg` | 每个 Agnes 镜头的接触表（2 fps 抽帧），人工复审用 |
| `制作过程.md` | 这次是怎么做出来的、踩了什么坑 |

## 这次流水线（与手册一致，多了两步）

1. `new_topic.py --slug gilgo` 开骨架 → `build_story.py` 一次性写入解说词、45 镜提示词、来源、红线（`story.json` / `audio/manifest.json` 文本）。
2. 试音 → 选定 voice-00 → 六段 TTS 原始文件放在 `audio/raw/`。
3. **新增** `tighten_pauses.py`：TTS 在标点处停 0.8–1.2 秒，六段原始 201.7 秒塞不进 168 秒的可用时长；
   只剪静音（片头 0.15 / 片尾 0.25 / 句内 ≤0.35 秒）、逐字不动，得到 `audio/N0x.mp3`（176.1 秒），SHA-256 写进 `audio/manifest.json`。
4. **新增** `clause_times.py`：按停顿把每个分句对到时间（动态规划挑静音段），输出 `audio/clause-times.json`；
   `render.py` 的 `CUTS` 切点和 `抖音脚本.md` 的时间轴都从这里来。
5. `generate.py --validate` → push `GEN_REQUEST`（`{"workers":2}`）→ Actions 生成 38 个镜头，`results.json` + `qa/` commit 回分支。
6. 人工看 `qa/*.jpg`（露脸 / 畸变 / 伪文字），坏镜头 `{"workers":1,"only":"Sxx"}` 重生成或改 `render.py` 的 `WINDOWS` / `TIGHTER_CROPS`。
7. push `RENDER_REQUEST` → Actions 出片（`production/run_project.sh gilgo`），成片与报告 commit 回分支。
8. 复审成片（按 EDL 逐段抽帧看画面 / 字幕 / 标签，按分句边界前后 0.25 s 抽帧核对字幕切换），push `VERBATIM_REQUEST` 做逐字听检，`gh release create` + `RELEASE_UPLOAD_REQUEST` 上传下载链接。

## 目录

| 路径 | 作用 |
|---|---|
| `build_story.py` | 剧本源数据：CHAPTERS（六段解说）、SHOTS（45 镜）、STYLE_PREFIX / NEGATIVE_PROMPT、SOURCES、PRINCIPLES；`--script` 生成 `抖音脚本.md`，`--publish` 生成 `抖音发布文案.md` |
| `script_table.py` | 把 story.json + CUTS + 分句时间拼成四列分镜表（`抖音脚本.md` 的正文）；标题 / 爆点 / 金句 / 介绍 / 提问 / 话题也在这里 |
| `story.json` | 分镜计划：45 镜 × 4 秒规划网格、6 章 × 30 秒；Agnes 每镜请求 7 秒 |
| `screenplay.md` | 解说稿 + 事实边界 + 分镜表 |
| `audio/raw/N0x.mp3` | TTS 原始输出（voice-00） |
| `audio/N0x.mp3` | 收紧停顿后的配音（成片用；manifest 的 SHA-256 记的是它） |
| `audio/manifest.json` | 六段配音的文件名、SHA-256、逐字文本、voice_id、后处理说明 |
| `audio/clause-times.json` | 每个分句在配音里的起止时间（clause_times.py 生成） |
| `audio/tighten-report.json` | 收紧前后的时长与参数 |
| `tighten_pauses.py` / `clause_times.py` | 上面两步的脚本（本项目新增） |
| `generate.py` | 生成 Agnes 素材（75 秒节流、断点续跑、`--prune-failed`）+ `--validate` 闸门；网格改成 45×4 |
| `fetch_sources.py` | 按 `results.json` 的 SHA-256 回填素材，不重新生成 |
| `render.py` | CUTS（每镜只用一次，有断言守着）、信息卡、字幕高亮词、逐镜标签、混音、成品复测；字幕时间三级来源：ASR 词级 → `audio/clause-times.json` 的 DP 分句边界 → 比例估计 |
| `build_audio.py` / `align_audio.py` / `media.py` / `throttle.py` | 参考项目的公共实现（副本） |
| `gilgo.workflow.yml` | `.github/workflows/gilgo-gen.yml` 的模板（逐字节相同） |
| `GEN_REQUEST` / `RENDER_REQUEST` / `VERBATIM_REQUEST` / `RELEASE_UPLOAD_REQUEST` | push 触发四条工作流的 marker 文件（生成 / 出片 / 逐字听检 / 上传 Release） |
| `../run_project.sh` | **所有项目共用**的出片脚本：`bash production/run_project.sh gilgo` |

## 红线（继承自参考项目 + 本片追加）

- AI 画面一律标注「AI动画情景重现 · 非新闻影像」（法庭 / 监狱 / 取证 / 搜查镜头分别写明「非庭审影像」等），不冒充真实影像；
- 真实人物不用 AI 生成的脸冒充：赫曼只以背影、剪影、手出现；受害者不以人像出现；
- 不展示遗体、血腥或侵害过程；地下室只有楼梯、灯泡、硬盘、搜查现场；
- 每一句事实都能指到 `story.json` 的 `sources`；未起诉的第八起只写「承认」不写「判决」；
- 中文姓名、日期、字幕一律后期添加，不交给视频模型拼写；
- 成片必须实测电平（`--validate` 之后还有 `render.py` 的成品复测），无声不许交付。
