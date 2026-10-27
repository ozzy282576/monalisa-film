# 韩国雨衣杀手柳永哲：十个月，二十条人命

三分钟横版（16:9 · 1920×1080 · 30 fps · 180 秒）中文悬疑解说短片，抖音横屏观看版本。
**画面是写实 3D CGI 动画情景重现（Agnes Video V2.0 生成的视频镜头，不是图片轮播、不是幻灯片）。**

案件：二〇〇三年九月至二〇〇四年七月，首尔二十人遇害；警方一直没能并案，
最后把他揪出来的，是一家按摩店老板记下来的一个电话号码。

本片由仓库根目录的 [`新题目开工手册.md`](../../新题目开工手册.md)（狂犬病模式）跑出来，
是继《雨夜屠夫林过云》之后**第二部露脸模式**的片子。

---

## 一句话流程

```
用户上传的 40 镜文案（抖音文案/20261007-020848_粘贴的文案_20261007-020848.txt）
  └─> build_story.py       唯一内容源：787 字解说 / 45 镜 / 7 张信息卡 / 字幕高亮 / 发布文案
        └─> TTS（voice-01）→ tighten_pauses.py → clause_times.py → generate.py --validate   ← 闸门一
              └─> GEN_REQUEST → Actions 生成 38 个 Agnes 镜头 → results.json + qa/ 接触表
                    └─> 复审接触表（露脸 / 畸变 / 伪文字 / 换场 → {"only":"Sxx"} 重做）
                          └─> CUTS 按分句停顿重对 → clause_times.py --check-cuts               ← 闸门二
                                └─> RENDER_REQUEST → 成片 + delivery/ 报告                    ← 闸门三
                                      └─> VERBATIM_REQUEST（逐字听检）· VISUAL_QC_REQUEST（全帧 QC）
                                            └─> face_cast.py check-frames（露脸闸门）
                                                  └─> 人工语义签收 → gh release + RELEASE_UPLOAD_REQUEST
```

## 本片规格

| 项 | 值 |
|---|---|
| 成片 | 1920×1080 · 30 fps · 180.0 秒 · 5400 帧 |
| 分镜 | **45 镜 × 4 秒规划网格** = 38 个 Agnes 写实 3D 动画镜头（7 s · 24 fps · 1080p）+ 7 张信息卡 + 片尾卡；每镜只出现一次 |
| 解说 | 6 段 · **787 字**（含标点）· TTS 原始 169.72 s → 收紧停顿后 160.04 s（只剪静音不动字）· 变速比 0.953 |
| 配音 | `voice-01`（男声、克制叙述；用户在试听后选定） |
| 字幕 | 分句字幕，切换点来自 `audio/clause-times.json`；关键词描黄；**字号 60 px**（模板默认 43，按用户「字幕大一点」调大），描边 3.2 |
| 画面风格 | 写实 3D CGI 情景重现：2003–2004 年首尔的雨夜、老式公寓、泥泞后山；**全片常驻「AI动画情景重现 · 非新闻影像」**，审讯/抓捕/搜查/法院/监狱镜头另有更具体的标签 |
| 露脸 | 3 个虚构匿名角色：C1 雨衣男（凶手）/ C2 老刑警 / C3 按摩店老板。每个角色一条 face token + 一个 seed，**同一角色跨镜头逐字节复用**；C1 / C2 / C3 的首次露脸镜头（S05 / S06 / S27）用定妆照做图生视频首帧 |
| 事实依据 | 每条都指到 [`史实核对.md`](史实核对.md) 的来源（8 条公开报道）；来源冲突处用不会写错的写法 |

## 内容边界（红线）

- 不展示遗体、血腥或作案过程；杀害方式只写到「钝器」这一层；奉元寺后山只出现雨、泥土、落叶、警戒线与工作人员背影。
- **不做任何真实人物的肖像还原**：凶手、刑警、店主都是 AI 生成的匿名角色，不是柳永哲本人或任何真实个人的容貌。
- 受害者不以可辨识面容出现（只给远景背影与物件）；不出现可读文字、报刊版面。
- 判决表述：二〇〇四年十二月十三日一审死刑、二〇〇五年六月最高法院维持；韩国自一九九七年起未再执行死刑，他至今仍在服刑。

## 文件说明

| 文件 | 作用 |
|---|---|
| `build_story.py` | **唯一内容源**（解说词 / 45 镜提示词 / 信息卡 / 片头片尾卡 / 发布文案）；面容 token 用 `{C1}` 占位符从 `cast.json` 注入，保证逐字节一致 |
| `cast.json` + `cast/*.jpg` | 角色谱与定妆照（露脸模式）：face token、seed、公开 URL、露脸镜头登记 |
| `story.json` / `screenplay.md` | 时间轴、剧本与逐镜提示词（由 `build_story.py` 写出） |
| `audio/` | 六段配音（`raw/` 原始 → `N0x.mp3` 收紧后）、`clause-times.json`、`manifest.json`（逐字文本 + SHA-256） |
| `render.py` | 剪辑引擎；本片只改了 `CUTS`（按分句停顿重对）与 `WINDOWS` / `TIGHTER_CROPS`（看片后的镜头修正） |
| `tools/smoke_render.sh` | 出片前的本地冒烟测试：38 个假片段 + 伪造 results.json，把整条 render.py 跑通 |
| `results.json` / `qa/` | 每个 Agnes 镜头的回执（请求哈希、SHA-256、CDN 地址）与 14 帧接触表 |
| `delivery/` | 技术报告、EDL、字幕时间轴、混音实测、听检、全帧 QC、人脸接触表与相似度分诊 |
| `史实核对.md` | 逐句事实 → 公开来源；来源冲突的处理方式 |
| `抖音脚本.md` / `抖音发布文案.md` | 由 `build_story.py --script / --publish` 生成的发布用文档（时间轴取自真实 EDL） |

## 出片闭环（本仓库的分支）

四份工作流固定在 `arena/ef74e893-desktop-tutorial`，由 marker 文件 push 触发：
`GEN_REQUEST` → `RENDER_REQUEST` → `VERBATIM_REQUEST` → `VISUAL_QC_REQUEST`；
Release 资产走通用的 `.github/workflows/release-upload.yml`。

```bash
python3 production/raincoat2004/build_story.py            # 内容 → story.json
python3 production/face_cast.py check-prompts --project production/raincoat2004   # 露脸静态闸门
python3 production/raincoat2004/generate.py --validate    # 计划与配音闸门
bash production/raincoat2004/tools/smoke_render.sh        # 出片前的本地冒烟测试
```
