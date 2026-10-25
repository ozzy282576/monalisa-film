# 交付件清单 · 雨夜屠夫林过云（三分钟横版）

**成片**：`交付/雨夜屠夫林过云_一卷菲林里的四条人命_三分钟_带声音.mp4`
**SHA-256**：`b57ad26f7d520bb1d5066daa9a257d9c87651e3f9c0b99b80fa736fae9d20804` · 70,250,059 bytes · 1920×1080 / 30 fps / 180.0 s / 5400 帧

> 认版本只看 SHA-256，不看文件名与大小（每次重渲 mp4 的创建时间戳都会变）。
> Release `lamkorwan-v1` 的资产与本目录成片字节一致。

| 文件 | 内容 | 绑定成片的方式 |
|---|---|---|
| `technical-report.json` | 规格 / 解码复测 / 混音实测 / 素材计数 | `sha256` 字段 = 上面的 SHA |
| `visual-qc-summary.json` | 全帧 QC 摘要（黑帧 / 冻结 / 人脸 / 时序窗） | `sha256` 字段 |
| `frame-distortion-audit.json` / `.md` | 5400 帧逐帧指标 + 汇总 | `sha256` 字段 |
| `verbatim-check.json` | 六章逐字听检（faster-whisper small，上限 CER 0.15） | `film_sha256` 字段（2026-10-06 起由 `production/verbatim_check.py` 写入） |
| `audio-report.json` / `final-audio-report.json` | 配音与混音测量 | 按制作批次（最终批次即本片） |
| `caption-timing.json` / `captions.srt` | 字幕时间轴（与成片同批生成） | 制作批次 |
| `alignment-report.json` / `narration-timing.json` | 分句对齐与旁白节奏 | 制作批次 |
| `edit-decision-list.json` | 45 段 EDL（每镜入出点与用途） | 制作批次 |
| `final-contact.jpg` / `visual-qc-shot-midpoints.jpg` | 45 段中点帧拼图 | 制作批次 |
| `AI辅助视觉复核-2026-10-06.md` | 两轮复审 + 出片后复检的逐镜记录 | 顶部写死 SHA |

**人工签收**：`visual-qc-summary.json` 的 `human_semantic_visual_review` 仍是 `pending`，
`technical-report.json` 的 `visual_review` 也是 `pending`——机器不替人签收，需要完整看一遍成片。
