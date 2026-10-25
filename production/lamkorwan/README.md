# 雨夜屠夫林过云：一卷菲林里的四条人命

三分钟横版（16:9 · 1920×1080 · 30 fps · 180 秒）中文悬疑解说短片，抖音横屏观看版本。
**画面是写实 3D 动画情景重现（Agnes Video V2.0 生成的视频镜头），不是图片轮播、不是幻灯片。**

案件：一九八二年二月至七月，香港四名夜归女子坐上同一辆夜班的士后遇害；破案的关键，
是凶手自己送去冲印店的一卷菲林。

---

## 一句话流程

```
用户上传的 40 镜文案（抖音文案/）
  └─> build_story.py       唯一内容源：791 字解说 / 45 镜 / 7 张信息卡 / 字幕高亮 / 发布文案
        └─> TTS（voice-00）→ tighten_pauses.py → clause_times.py → generate.py --validate   ← 闸门一
              └─> GEN_REQUEST → Actions 生成 38 个 Agnes 镜头 → results.json + qa/ 接触表
                    └─> 复审接触表（露脸 / 畸变 / 伪文字 / 换场 → {"only":"Sxx"} 重做）
                          └─> CUTS 按分句停顿重对 → clause_times.py --check-cuts               ← 闸门二
                                └─> RENDER_REQUEST → 成片 + delivery/ 报告                    ← 闸门三
                                      └─> VERBATIM_REQUEST（逐字听检）· VISUAL_QC_REQUEST（全帧 QC）
                                            └─> gh release + RELEASE_UPLOAD_REQUEST
```

## 本片规格

| 项 | 值 |
|---|---|
| 成片 | 1920×1080 · 30 fps · 180.0 秒 · 5400 帧 |
| 分镜 | **45 镜 × 4 秒规划网格** = 38 个 Agnes 写实 3D 动画镜头（7 s · 24 fps · 1080p）+ 7 张信息卡 + 片尾卡；每镜只出现一次 |
| 解说 | 6 段 · **796 字**（含标点）· TTS 原始 183.53 s → 收紧停顿后 174.34 s（只剪静音不动字）· 整体变速 **1.038** |
| 字幕 | 分句字幕，切换点来自 `audio/clause-times.json`；**字号 60 px**（模板默认 43，按用户「字幕要大一些」调大），关键词描黄 |
| 画面风格 | 写实 3D CGI 情景重现：1982 年香港雨夜、霓虹、旧款的士；**全片常驻「AI动画情景重现 · 非新闻影像」**，法庭/搜查/证物镜头另有更具体的标签 |
| 事实依据 | 每条都指到 [`史实核对.md`](史实核对.md) 的来源；来源冲突处用不会写错的写法 |

## 内容边界（红线）

- 不展示遗体、血腥或侵害过程；不重演作案；杀害方式只写「勒死」这一层。
- 凶嫌只以背影、剪影、手出现；四名受害者不以任何人像出现，只用信息卡致意。
- 不出现可读文字、报刊版面、可辨识真人面孔；中文姓名与日期一律后期添加。
- 判决表述：四项谋杀罪名成立、判处死刑；一九八四年八月由港督会同行政局赦免死刑、改判终身监禁；
  **不说「已释放／已出狱」**（来源冲突见 `史实核对.md` 第二节）。

## 文件说明

| 文件 | 作用 |
|---|---|
| `build_story.py` | **唯一内容源**（解说词 / 45 镜提示词 / 信息卡 / 片头片尾卡 / 发布文案） |
| `story.json` / `screenplay.md` | 由 `build_story.py` 写出的时间轴与剧本 |
| `audio/manifest.json` | 六段配音的逐字文本与 SHA-256（与 story.json 逐字一致，`generate.py` 守着） |
| `audio/raw/` → `audio/N0x.mp3` | TTS 原始配音 → 收紧停顿后的渲染音轨 |
| `render.py` | 剪辑引擎；本片只改了 `CUTS`（按分句停顿重对）与字幕字号 |
| `results.json` / `qa/` | 每个 Agnes 镜头的回执（请求哈希、SHA-256、CDN 地址）与 14 帧接触表 |
| `delivery/` | 技术报告、EDL、字幕时间轴、对轨报告、混音实测、听检与全帧 QC 结果 |
| `史实核对.md` | 逐句事实 → 公开来源；来源冲突的处理方式 |
| `抖音脚本.md` / `抖音发布文案.md` | 由 `build_story.py --script / --publish` 生成的发布用文档 |

## 出片闭环（本仓库的分支）

四条工作流固定到 `arena/050152c3-desktop-tutorial`，由 marker 文件 push 触发：

```bash
echo '{"workers":2}'            > production/lamkorwan/GEN_REQUEST       # 生成 38 镜
echo "render $(date -u +%FT%TZ)" > production/lamkorwan/RENDER_REQUEST    # 出片
echo "verbatim $(date -u +%FT%TZ)" > production/lamkorwan/VERBATIM_REQUEST # 逐字听检
echo "visual-qc $(date -u +%FT%TZ)" > production/lamkorwan/VISUAL_QC_REQUEST # 全帧视觉 QC
```

## 当前状态（已出片，只剩人工签收）

> **终版成片已交付**：`交付/雨夜屠夫林过云_一卷菲林里的四条人命_三分钟_带声音.mp4`，
> SHA-256 `b57ad26f7d520bb1d5066daa9a257d9c87651e3f9c0b99b80fa736fae9d20804`
> （1920×1080 / 30 fps / 180.0 秒 / 5400 帧 / 70,250,059 bytes；含第二轮复审后的五个重做镜头，最末一个改动是 S32 第六版）。
> Release `lamkorwan-v1` 的资产已按这个 SHA 上传。**剩下最后一步：你完整看一遍。**

| 闸门 | 状态 | 证据 / 下一步 |
|---|---|---|
| 事实、脚本、发布文案 | 已完成 | `build_story.py` 唯一内容源；逐句对照见 [`史实核对.md`](史实核对.md) |
| 配音、分句和切点 | 已完成 | 6 段共 796 字；收紧后 174.34 秒；`clause_times.py --check-cuts` 全过 |
| 结构与音频哈希 | 已完成 | `generate.py --validate`：180 秒计划、45 镜、38 Agnes / 7 信息卡、音频哈希一致 |
| 镜头复审（生成期三轮） | 已完成 | S02 / S21 各重做两轮；记录见 `delivery/AI辅助视觉复核-2026-10-06.md` |
| 首版成片复检 → 8 镜重做 | 已完成 | S08 / S12 / S15 / S17 / S25 / S30 / S34 / S35 换构图重做并重渲 |
| 手机可读性提亮 | 已完成 | `render.py` 的 `GRADE`：暗部 22–28/255 → 51–55/255；黑帧 559 → 1（转场压黑） |
| 结尾镜头匀速化 | 已完成 | S45 重新生成（原素材中段近静止 1 秒），新素材全程在动 |
| 逐字听检 | 已完成 | 六章 CER 0.018–0.081（同一成片重复跑有小幅波动，上限 0.15）；报告自带成片 `film_sha256` |
| 全帧视觉 QC | 已完成（自动） | 5400/5400 帧解码；冻结段 0；人脸候选 0；手部事件 12 处逐张看过 |
| Release 资产 | 已完成 | `lamkorwan-v1` → `lamkorwan-rainy-night-butcher-3min-1080p.mp4` |
| 人工语义视觉签收 | **等你完整看片** | `visual-qc-summary.json` 的 `human_semantic_visual_review` 仍写死为 `pending`（机器不替人签收） |

每一步的实测数字与返工过程都写进 [`制作过程.md`](制作过程.md)。
