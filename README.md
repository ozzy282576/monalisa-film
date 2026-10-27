# monalisa-film

本仓库已整体拷入上游视频流水线 [`32r4e2q-hub/desktop-tutorial`](https://github.com/32r4e2q-hub/desktop-tutorial)
的 `kitakyushu2002-v1` 快照（含全部代码、工作流、手册、模板、测试与各案例工程），用于自行制作三分钟中文解说短片。

## 快速导航

- **想做新片，先读**：[`新题目开工手册.md`](新题目开工手册.md) → `python3 production/new_topic.py --slug <片名> --title "<标题>" --branch <当前分支>`
- **拷贝了什么 / 媒体怎么恢复**：[`拷贝说明.md`](拷贝说明.md)
- 成片 mp4、抽帧 jpg、配音 mp3 等 **677.7 MB 媒体文件不进 git**，需要时执行：
  `python3 scripts/fetch_upstream_media.py`（逐文件 SHA-256 校验，清单见 `scripts/upstream-media-manifest.json`）
- 本仓库原有的 `config/`（Agnes 3D 配置）与 `.github/workflows/agnes-3d-generate.yml` 原样保留，未受影响
- 跑 Actions 工作流前需自备密钥与运行环境，见 [`转私有与自托管Runner手册.md`](转私有与自托管Runner手册.md)

---

# 雨夜屠夫林过云：一卷菲林里的四条人命（上游 README 原文）

三分钟横版（16:9）中文悬疑解说短片 · 抖音横屏观看版 · 写实 3D 动画情景重现。
一九八二年二月至七月，香港四名夜归女子坐上同一辆夜班的士后再没有回家；
警方查了半年，最后揭开真相的不是目击者、不是指纹，而是凶手自己送去冲印店的一卷菲林。

这个仓库是这部片子的**成片、脚本、发布文案**，以及把它做出来的**整条可复现流水线**
（换题目照 [`新题目开工手册.md`](新题目开工手册.md) 再做一部）。

## 成片

| 项 | 内容 |
|---|---|
| 文件 | [`交付/雨夜屠夫林过云_一卷菲林里的四条人命_三分钟_带声音.mp4`](交付/雨夜屠夫林过云_一卷菲林里的四条人命_三分钟_带声音.mp4)（67.0 MB · 1920×1080 · 30 fps · 180.0 s · 5400 帧） |
| 下载 | [Release lamkorwan-v1](https://github.com/32r4e2q-hub/desktop-tutorial/releases/tag/lamkorwan-v1) → `lamkorwan-rainy-night-butcher-3min-1080p.mp4`（与 `交付/` 里的文件字节一致，SHA-256 `b57ad26f7d520bb1d5066daa9a257d9c87651e3f9c0b99b80fa736fae9d20804`） |
| 画面 | 45 个镜头 = **38 个 Agnes Video V2.0 写实 3D 动画镜头 + 7 张信息卡 + 片尾卡，每个镜头只出现一次**；全片常驻「AI动画情景重现 · 非新闻影像」标签 |
| 声音 | 六段配音 796 字（TTS → 只剪静音收紧到 174.34 s，整体变速 1.038）+ 原创配乐 + 合成音效；成片实测 RMS −20.31 dBFS · 峰值 −1.51 dBFS · 静音占比 0.55 %（六章逐段 RMS −19.91 / −19.92 / −20.00 / −20.12 … dBFS） |
| 字幕 | 分句字幕、关键词描黄；**字号 60 px**（模板默认 43，按「字幕要大一些」调大）、描边 3.2 |
| 调色 | 手机端可读性提亮 `eq=gamma=1.45:brightness=0.012`：暗部由 22–28/255 抬到 51–55/255，夜景氛围保留（改动记在 `render.py` 的 `GRADE`） |
| 听检 | whisper small 逐章字错率 0.018–0.081（同一成片重复跑有小幅波动，上限 0.15），报告 [`delivery/verbatim-check.json`](production/lamkorwan/delivery/verbatim-check.json) |
| 全帧 QC | 5400/5400 帧解码；冻结段 0；**人脸复核候选 0**；非计划黑帧 1（S45→片尾卡交接的转场压黑，已人工确认），报告 [`delivery/visual-qc-summary.json`](production/lamkorwan/delivery/visual-qc-summary.json) |

## 发布用

- **题目（三选一）**
  1. 香港最轰动的奇案：他把四条人命拍进菲林，最后栽在一台坏掉的放大机上
  2. 雨夜屠夫林过云：一卷送去冲印的照片，把自己送进了法庭｜香港十大奇案
  3. 1982年香港雨夜，四个女人上了同一辆的士，再也没下车
- **提问读者一句话**：如果那台放大机没有坏，这个案子还会被揭开吗？
- **金句**：他想让全世界看见自己的作品，结果正是那卷菲林，把他送上了法庭。
- **抖音介绍 + 话题**：[`production/lamkorwan/抖音发布文案.md`](production/lamkorwan/抖音发布文案.md)
- **脚本**（三个标题 / 核心爆点 / 四列分镜表：时间轴 · 口播文案 · 画面描述 · 音效备注 / 金句结尾 / 事实边界 / 资料来源）：
  [`production/lamkorwan/抖音脚本.md`](production/lamkorwan/抖音脚本.md)
- **流水线更新**：本片把两条新规矩写进了 [`新题目开工手册.md`](新题目开工手册.md)——① 街景/店面镜头必须放大到原始像素查 AI 伪文字（缩略图看不见）；② **露脸模式**：从下一部起可以露脸，但「每个人物一张不同的脸、同一人物跨镜同一张脸」由 `production/face_cast.py` 两道闸门守着（静态查 token、画面查换脸/撞脸）

## 案件事实链（片中每一句都有公开来源，见脚本第六节）

| 时间 | 事 |
|---|---|
| 1982-02-03 → 02-11 | 陈凤兰（22 岁）凌晨在尖沙咀搭上一辆的士后失踪；二月十一日，警方在沙田城门河发现女性头颅与一双女子手臂，全案曝光 |
| 1982-05-29 | 陈云洁（31 岁，收银员）凌晨下班搭车后遇害 |
| 1982-06-17 | 梁秀云（29 岁，清洁工）凌晨下班搭车后遇害 |
| 1982-07-02 | 梁惠心（17 岁，学生）参加谢师宴后搭车，是四名受害者中最后一位 |
| 1982-08 | 凶手家中没有暗房，惯常把菲林送到尖沙咀一间相铺冲洗；放大机故障，底片转到分店由人手冲晒，店员看清照片内容后报警 |
| 1982-08-18 | 警方在冲印店埋伏，等他自己来取相时拘捕；同日搜查土瓜湾贵州街住所，搜出照片、录像带、手术器材等证物 |
| 1983-03-03 → 04-08 | 高等法院开审；五名精神科医生评估过；四月八日，七人陪审团一致通过四项谋杀罪名成立，判处死刑 |
| 1984-08 | 港督会同行政局赦免死刑，改判终身监禁；至今仍在服刑 |

事实边界：AI 画面不冒充新闻、庭审或证物影像；凶嫌只以背影、剪影、手出现；**四名受害者不以任何人像出现**，
只用信息卡致意；不展示遗体、血腥或侵害过程，不重演作案；来源打架的细节（拘捕日、冲印店位置、发现照片的具体日子、
精神鉴定的比例）一律用不会写错的写法，处理方式见 [`史实核对.md`](production/lamkorwan/史实核对.md)；
**不说「已释放／已出狱」**；中文姓名、日期、字幕一律后期添加。

## 这部片子是怎么做出来的

```
文案上传（抖音文案/ + 电影解说工具包/upload_text_server.py：网页上传区收 txt）
  └─ 事实核查（7 条公开来源：HK01 / 思考香港 / NOWnews / 香港教育城 / 百度百科 …）
       └─ build_story.py：六段解说 796 字 + 45 镜提示词 + 7 张信息卡 + 片头片尾卡   ← 唯一内容源
            └─ TTS 六段 → tighten_pauses.py（只剪静音不动字）→ clause_times.py（分句对时间）
                 └─ generate.py --validate → GEN_REQUEST → Actions 生成 38 镜（75 秒节流、断点续跑）
                      └─ 逐镜复审 qa/ 接触表 → {"only":"Sxx"} 重做坏镜头（按 SHA-256 复用其余）
                           └─ render.py：CUTS 按分句停顿切、信息卡、60 px 字幕、调色、混音 → RENDER_REQUEST
                                └─ VERBATIM_REQUEST 逐字听检（六章 CER ≤ 0.15）
                                     └─ VISUAL_QC_REQUEST 全帧审计 5400/5400 帧 + 候选帧导出
                                          └─ 人工语义复核 + 抽帧复检 → Release 资产上传
```

全过程（含三轮复审改了哪些镜头、终版两个缺陷怎么被发现和修掉的）：
[`production/lamkorwan/制作过程.md`](production/lamkorwan/制作过程.md)。

| 路径（`production/lamkorwan/`） | 内容 |
|---|---|
| `build_story.py` / `story.json` / `screenplay.md` | 解说词、45 镜分镜、信息卡、片头/片尾卡、事实边界、来源 |
| `audio/` | 六段配音（收紧后）、原始 TTS、SHA-256 收据、分句时间、收紧报告 |
| `results.json` / `qa/` | 38 镜的生成回执、接触表 |
| `render.py` / `clause_times.py` / `tighten_pauses.py` / `generate.py` … | 出片引擎（详见目录里的 README） |
| `qc_shots.py` / `audit_frame_distortions.py` / … | 逐镜初筛与成片全帧审计 |
| `delivery/` | 技术报告、EDL、字幕时间轴、混音与成品音频实测、逐字听检、全帧审计、[AI 辅助视觉复核](production/lamkorwan/delivery/AI辅助视觉复核-2026-10-06.md) |
| `抖音脚本.md` / `抖音发布文案.md` | 交付给发布的脚本与文案（都由 `build_story.py` 生成，和成片同源） |

## 用同一套流程做下一部

```bash
python3 production/new_topic.py --slug <slug> --title "<片名>" --branch <分支>
```

脚手架以 `production/rabies1885/` 为参考开出新目录（45 镜 × 4 秒骨架、内容与引擎分离的
`build_story.py` / `render.py` / `script_table.py`、检验工具链、四份 marker 触发的工作流：
生成 / 出片 / 听检 / **全帧视觉 QC**），然后照 [`新题目开工手册.md`](新题目开工手册.md) 的 12 步走。
参考项目只被读取、不被修改，有测试守着。本片是照这份手册做的第二部，并回补了两处流水线改动
（`GRADE` 调色常量、`WINDOWS` 的 `None` 处理），见 `制作过程.md` §9。

## 闸门（任何一道不过都不许出片）

1. `generate.py --validate` —— 时间轴 45×4、提示词非空、配音文本与剧本逐字一致、配音 SHA-256；
2. `clause_times.py --check-cuts` —— 切点落在分句停顿窗内；`render.py::make_edl` —— 每个镜头只用一次、全部用到、EDL 无缝；
3. `render.py` 开头 —— 素材必须是 `results.json` 里 SHA-256 对得上的 Agnes 片段，不用图片/幻灯片顶替；
4. `build_audio.py` —— 整体电平 / 波峰因数 / 静音占比 / **逐段**解说电平；
5. `render.py` 收尾 —— 对**最终 mp4** 复测一遍；
6. `verbatim_check.py`（Actions）—— 成片转写与剧本的字错率逐章 ≤ 0.15；
7. `test_card_typography.py`（离线自检，**通用**）—— 真画片尾卡与信息卡，左右各 100 px 安全带里不许有字；
8. `audit_frame_distortions.py`（Actions）—— 成片 5400/5400 帧解码：黑帧 / 冻结 / 时序突变 / 人脸 / 手部；
   **它是分诊，不是签收**；
9. 人工语义复核 —— 逐张看完候选帧；自动审计量不到的（文字溢出、构图语义、整体亮度观感）只能人看。

## 出片方式

本地：`bash production/run_project.sh <slug> [skip_asr] [成片文件名]`。
Actions：在分支上写 marker 文件并 push——`production/<slug>/GEN_REQUEST`（生成）/ `RENDER_REQUEST`（出片）/
`VERBATIM_REQUEST`（听检）/ `VISUAL_QC_REQUEST`（全帧 QC）/ `RELEASE_UPLOAD_REQUEST`（传 release）。
本片的四条工作流在 [`.github/workflows/lamkorwan-*.yml`](.github/workflows/)，成片与报告由工作流 commit 回分支。

```bash
python3 -m pip install -r production/requirements.txt   # 另需 ffmpeg 与中文字体（fonts-noto-cjk）
python3 -m pytest production/tests -q                   # 离线自检
```

## 仓库里还有什么

| 路径 | 内容 |
|---|---|
| [`抖音文案/`](抖音文案/) + [`电影解说工具包/upload_text_server.py`](电影解说工具包/upload_text_server.py) | 文案上传区：浏览器拖 txt / 直接粘贴 → 存进 `抖音文案/`（自动识别 GBK 等编码、带时间戳不覆盖） |
| [`新题目开工手册.md`](新题目开工手册.md) | 开工手册：12 步 + 闸门表 + 踩坑清单 + 文件地图 |
| [`production/new_topic.py`](production/new_topic.py) + [`production/templates/`](production/templates/) | 开新题目的脚手架与模板（四份工作流模板：生成 / 出片 / 听检 / 全帧 QC） |
| [`production/verbatim_check.py`](production/verbatim_check.py) / [`review_film.py`](production/review_film.py) | 逐字听检；黑帧 / 冻结帧 / 电平 / 语速审片初筛 |
| [`production/rabies1885/`](production/rabies1885/) | 上一部《狂犬病疫苗：一百四十年前那场赌局》（45 镜、写实动画）及其[制作过程](production/rabies1885/制作过程.md)；成片 `交付/狂犬病疫苗_一百四十年前那场赌局_三分钟_带声音.mp4` |
| [`production/gilgo/`](production/gilgo/) | 更早的参考实现《吉尔戈海滩：披萨盒里的凶手》（38+7 镜、手绘 2D 风） |
| [`production/dahlia/`](production/dahlia/) | 更早的《黑色大丽花：消失的六天》（30 镜 × 6 秒、带档案照片） |
| [`电影解说工具包/`](电影解说工具包/) | 更早的一套工具；`render.py` 的配乐 `generate_horror_bgm.py` 在这里 |
| [`runner/`](runner/) + [`转私有与自托管Runner手册.md`](转私有与自托管Runner手册.md) | 本地出片机：一键安装注册、自检、卸载；转私有的正确顺序与 `RUNNER_LABEL` 开关 |
