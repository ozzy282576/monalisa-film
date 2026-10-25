# 北九州监禁案：逃出魔窟的少女，七条人命背后的秘密

三分钟横版（16:9 · 1920×1080 · 30 fps · 180 秒）中文悬疑解说短片，抖音横屏观看版本。
**画面是写实 3D CGI 动画情景重现（智谱 CogVideoX-Flash 免费档生成的视频镜头，不是图片轮播）。**

案件：一九九六至二〇〇二年，日本北九州市小仓北区一间普通公寓。松永太与内缘妻子绪方纯子
监禁、支配绪方的家人等多名受害者，七人死亡（包括两名孩子）；二〇〇二年三月，一名十七岁少女
深夜逃出、向祖父家求助，案件才曝光；二〇〇五年九月一审双双死刑，二〇〇七年二审改判绪方无期，
二〇一一年十二月最高裁终审确定。

- slug：`kitakyushu2002`　出片分支：`arena/44a8fff6-desktop-tutorial`　成片文件名：`北九州监禁案_逃出魔窟的少女，七条人命背后的秘密_三分钟_带声音.mp4`
- 规格：45 镜 = **38 个 CogVideoX 动态镜头 + 7 张信息卡**，每镜只出现一次
- 内容源：用户上传的 30 镜文案稿 `抖音文案/20261017-011840_粘贴的文案_20261017-011840.txt` 为骨架，
  事实按 [`史实核对.md`](史实核对.md) 的 10 条公开来源重写（口径冲突处见该文件第三节）

## 一句话流程

```
用户上传的 30 镜文案稿（抖音文案/20261017-011840_粘贴的文案_20261017-011840.txt）
  └─> build_story.py       唯一内容源：解说词 / 45 镜 / 7 张信息卡 / 字幕高亮 / 发布文案
        └─> TTS（voice-00，用户试听选定）→ tighten_pauses.py → clause_times.py → generate.py --validate  ← 闸门一
              └─> COGVIDEOX_GEN_REQUEST → Actions 跑 CogVideoX-Flash 免费档生成 38 镜 → results.json + qa/ 接触表
                    └─> 复审接触表（露脸 / 畸变 / 伪文字 / 换场 → {"only":"Sxx"} 重做）
                          └─> CUTS 按分句停顿重对（tools/plan_cuts.py）→ clause_times.py --check-cuts      ← 闸门二
                                └─> RENDER_REQUEST → 成片 + delivery/ 报告                               ← 闸门三
                                      └─> VERBATIM_REQUEST（逐字听检）· VISUAL_QC_REQUEST（全帧 QC）
                                            └─> face_cast.py check-frames（露脸闸门）→ 人工语义签收
```

## 本片与模板（`production/kanghosun2009`）的关系

引擎（`render.py` / `build_audio.py` / `generate_cogvideox.py` / QC 工具链）由该项目的
模板移植而来，路径、分支名、片名已全部替换；**内容、分镜、角色谱、来源全部重写**。
生成侧只走智谱 CogVideoX-Flash 免费档（`model_policy.COGVIDEOX_MODEL`），不调用 Agnes、不产生费用。

## 本片规格

| 项 | 值 |
|---|---|
| 成片 | 1920×1080 · 30 fps · 180.0 秒 · 5400 帧 |
| 分镜 | **45 镜 × 4 秒规划网格** = 38 个 CogVideoX-Flash 动态镜头 + 7 张信息卡 + 片尾卡；每镜只出现一次 |
| 解说 | 6 段 · 766 字（含标点）· voice-00（用户试听选定）· 原始 178.12s → 收紧静音（只剪静音不动字）· 变速比 1.060 |
| 字幕 | 分句字幕，切换点来自 `audio/clause-times.json`（DP 分句对时间）；关键词描黄；字号 60 px |
| 切点 | `CUTS` 由 plan_cuts 排骨架后**按逐句语义手工精排**（kanghosun v5 同款做法），45/45 切点 0.00 偏差落在分句停顿窗内；`clause_times.py --check-cuts` 全绿 |
| 画面风格 | 写实 3D CGI 情景重现：一九九六至二〇一一年间的北九州小仓公寓、雨夜街巷、日本警局、木装修法庭与拘置所高墙；全片常驻「AI动画情景重现 · 非新闻影像」 |
| 露脸 | 5 个虚构匿名角色：C1 松永太（情景重现替身，非本人容貌）/ C2 绪方纯子（替身，非本人容貌）/ C3 老刑警 / C4 检察官 / C5 法官。每人一条 face token + 一个 seed，**同一角色跨镜头逐字节复用**；受害者与逃脱少女全程背影、剪影或手 |
| 事实依据 | 每条都指到 [`史实核对.md`](史实核对.md) 的来源（10 条公开报道） |
| 生成成本 | 智谱 CogVideoX-Flash 免费档，**零费用**（每约 60 秒一镜，38 镜一轮约 45 分钟） |

## 内容边界（红线）

- 不展示遗体、血腥或虐待过程：监禁与暴力只通过环境、光影与人物反应暗示（忽明忽暗的灯、紧握的手、关上的门）。
- **不做真实人物的肖像还原**：松永太与绪方纯子由虚构匿名角色 C1 / C2 扮演，片内标签与片尾卡写明「非本人容貌」；
  受害者与逃脱少女全程不给可辨识面容（只有背影、剪影与物件）。
- 不美化犯罪者：落点是七名受害者与「被剥夺的选择」。
- 判决表述：二〇〇五年九月二十八日一审双双死刑；二〇〇七年九月二十六日二审绪方改判无期；
  二〇一一年十二月十二日最高裁终审确定；日本未执行死刑，松永现羁押于福冈拘置所。

## 文件说明

| 文件 | 作用 |
|---|---|
| `build_story.py` | **唯一内容源**（解说词 / 45 镜提示词 / 信息卡 / 片头片尾卡 / 发布文案）；面容 token 用 `{C1}`…`{C5}` 占位符从 `cast.json` 注入 |
| `cast.json` + `cast/*.png` | 角色谱与定妆照（露脸模式）：face token、seed、公开 URL、露脸镜头登记 |
| `story.json` / `screenplay.md` | 时间轴、剧本与逐镜提示词（由 `build_story.py` 写出） |
| `audio/` | 六段配音（`raw/` 原始 → `N0x.mp3` 收紧后）、`clause-times.json`、`manifest.json` |
| `generate_cogvideox.py` | 智谱 CogVideoX-Flash 生成引擎（免费档；SHA-256 收据、断点续跑、历史收据复用、QA 接触表） |
| `render.py` | 剪辑引擎；本片只改 `CUTS`（由 plan_cuts.py 写入）与 `WINDOWS` / `TIGHTER_CROPS`（看片后的镜头修正） |
| `results.json` / `qa/` | 每个镜头的回执（请求哈希、SHA-256、CDN 地址）与接触表 |
| `delivery/` | 技术报告、EDL、字幕时间轴、混音实测、听检、全帧 QC、人脸接触表 |
| `史实核对.md` | 逐句事实 → 公开来源；来源冲突的处理方式 |
| `抖音脚本.md` / `抖音发布文案.md` | 由 `build_story.py --script / --publish` 生成的发布用文档 |

## 本地命令

```bash
python3 production/kitakyushu2002/build_story.py --script    # 生成抖音脚本.md（时间轴取自真实 EDL）
python3 production/face_cast.py check-prompts --project production/kitakyushu2002
python3 production/kitakyushu2002/generate_cogvideox.py --validate
bash production/run_project.sh kitakyushu2002                # 出片（Actions 上由 RENDER_REQUEST 触发）
```
