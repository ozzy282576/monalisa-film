# 黑色大丽花：消失的六天

三分钟中文解说短片：23 条 Agnes Video V2.0 情景重现素材 + 档案照片 + 资料图解，
六段中文解说、中文硬字幕、原创程序配乐，全程在 GitHub Actions 上自动出片。

**完整制作过程（含"第一版没声音"的定位与修复）见 [`制作过程.md`](制作过程.md)。**

---

## 当前状态：有声版已成片

成片已由 Actions 渲染并 **commit 进本分支**：

**`交付/黑色大丽花_三分钟_带声音.mp4`**（48.1 MB，SHA-256 `4129ae6b…`）
→ 在线播放/下载：https://github.com/32r4e2q-hub/desktop-tutorial/blob/main/交付/黑色大丽花_三分钟_带声音.mp4

出片运行：[run 34348339183](https://github.com/32r4e2q-hub/desktop-tutorial/actions/runs/34348339183)（11 分 31 秒，success）。
23 条素材全部按 SHA-256 取回，**没有重新生成、没有消耗额度**。

### 交付实测（在最终 mp4 上测得，不是中间文件）

```
整体：−21.09 dBFS RMS   峰值 −1.52 dBFS   静音占比 1.1%（片头 + 片尾 1.5 秒淡出）
逐段：N01 −21.12  N02 −21.17  N03 −20.91  N04 −20.61  N05 −20.19  N06 −20.85 dBFS
规格：1920×1080 / 30fps / 5400 帧 / AAC 48kHz 立体声 / 48.1 MB / 完整解码通过
```

---

## 上一版为什么没声音

上一版成片（`黑色大丽花_三分钟_初版.mp4`）**没有声音**。原因不是素材缺失，而是：

- 旧版音频**整条依赖一串 ffmpeg 滤镜链**（`adelay → amix → sidechaincompress → loudnorm`）合成；
- 成品校验**只查容器字段**（有 AAC 48kHz 双声道音轨、能解码就算过），**从不测电平**；
- 因此一条听得见或听不见的音轨都能一路绿灯出片。

已修：

- `build_audio.py` —— 混音搬进 numpy，解说按精确采样点落轨、配乐用本地包络闪避、响度用显式 RMS 目标 + 峰值上限归一，**同输入逐位可复现**；
- 静音闸门 —— 整体电平、波峰因数、静音占比、**逐段解说电平**任一项不达标即报错；
- `render.py` —— 封装完成后对**最终 mp4** 再测一遍，不达标直接失败；
- `production/tests/test_dahlia_audio.py` —— 用标准音 / 纯静音 / 半段静音三种信号验证闸门有效。

本地用真实配音实测：整体 **−21.1 dBFS RMS**、峰值 −1.5 dBFS、静音占比 0.6%，六段解说均在 −20～−21 dBFS。

## 出片

重跑这一部（或任何一部）都用**仓库共用的**出片流程，不再用本目录里的老模板：

```bash
# 本地
bash production/run_project.sh dahlia false 黑色大丽花_三分钟_带声音.mp4

# GitHub Actions：Actions → 「解说短片出片」→ project 填 dahlia、
# film_name 填 黑色大丽花_三分钟_带声音.mp4、skip_asr 视网络勾选
```

`film_name` 一定要填原片名：留空会用 `story.json` 的标题（「黑色大丽花：消失的六天」）
当文件名，`交付/` 里就会多出一个 48 MB 的副本。

素材**不会重新生成**：`fetch_sources.py` 按 `results.json` 的 SHA-256 回填 23 条已生成素材，哈希不符即报错。

> 本目录里的 `dahlia-audio.workflow.yml` / `ai-shots.workflow.yml` 是**历史模板**（pin 在旧分支
> `arena/01a085be-desktop-tutorial` 上，那个分支还留着当时的代码）。新片子走
> `production/commentary-render.workflow.yml`，别再复制这两个。

## 成品规格

| 项目 | 结果 |
|---|---|
| 时长 | 180.000 秒（30fps / 5400 帧） |
| 分辨率 | 1920×1080 |
| 视频编码 | H.264 |
| 音频 | AAC 48kHz 双声道（实测 −21.1 dBFS RMS / 峰值 −1.5 dBFS） |
| 结构 | 6 段解说 / 35 个剪辑片段 / 23 条 AI 素材 / 6 张资料卡 / 1 张档案照片 |

## 事实边界

- AI 素材只作**情景重现**，画面上永久标注「AI情景重现 · 非历史影像」，不冒充历史现场影像。
- 伊丽莎白·肖特本人**只用 1947 年警方调查通告的档案照片**，不用 AI 生成的脸冒充本人。
- 指纹为**示意图**，标注「非原始证物图像」。
- 案件按 FBI 公开资料**仍未侦破**，片中不指认凶手。

## 目录

| 路径 | 作用 |
|---|---|
| `story.json` / `screenplay.md` | 分镜计划、解说词、提示词、事实边界与来源 |
| `results.json` | 每条 AI 素材回执（请求哈希、SHA-256、CDN 地址） |
| `generate.py` / `agnes_video.py` / `throttle.py` | 只调指定模型、75 秒节流、断点续跑 |
| `fetch_sources.py` | 按哈希回填已生成素材 |
| `audio/` | 6 段解说录音 + 文字/哈希回执 |
| `assets/` | 档案肖像与来源说明 |
| `qa/` / `visual-review.json` | 素材抽样检查图 |
| `render.py` | 剪辑、字幕、烧录、封装、成品实测 |
| `build_audio.py` | 确定性混音 + 静音闸门 |
| `align_audio.py` | 本地 ASR 对轨，不足则回退并标注 |
| `delivery/` | 技术报告、音频实测报告、字幕、EDL、抽样图 |
| `delivery/reproducibility-2026-09-10.json` | 换机器复现实测（与云端记录逐项差 0.00 dB） |
| `delivery/frozen-triage-calibration.json` | 冻结帧复核阈值的标定数据 |
| `review/` | 审片记录：2026-09-09 首审、2026-09-10 复核 |
| `制作过程.md` | 完整制作过程 |

## 尚未完成

- **逐字听检**：闸门证明"有声且电平正常"，不证明配音念的字与剧本一字不差；N03/N05/N06 的 ASR 匹配度偏低，字幕为审定剧本 + 停顿估算，仍需人工听一遍。
- **构图/字幕错字/AI 畸变**：`review_film.py` 只把抽样帧摆到人面前，判断仍要人看片。
  （"35 处画面冻结"这个旧flag已经在 2026-09-10 定性完毕：13 处设计内静帧 + 22 处阈值误报，真缺陷 0 处，见 `review/复核-2026-09-10.md`。）
- 中间产物走 Actions artifact / 本地 `work/`，**不进 Git**；仓库只保存输入、小尺寸检查图、成片与制作元数据。
