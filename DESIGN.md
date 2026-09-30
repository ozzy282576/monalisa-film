# 渲染契约

本文档是上游 `story-to-handdrawn-video` 的 `DESIGN.md` 在本仓库的等价物：
**渲染行为必须一致，渲染技术栈可以不同**。所有数值集中在
`scripts/handdrawn/contract.py`，其余模块只负责栅格化，不自行发明几何。

## 流程分工

Agent 与渲染器各管一段，边界刻意画得很清楚：

1. **Agent** 读故事、保留原措辞、按完整句子切拍、锁定角色一致性；
   选定内置配方或用参考图分析出画风档案。
2. **生图工具** 画每幕的母图。默认 `--text-mode font` 下母图
   **只出插画**；`--text-mode image2` 才把手写字一并画进去。
3. **本地脚本** 导入已确认的母图，派生出所选动画模式需要的素材。
   上传的整页图片从这一步进入，之后与生成母图走完全相同的处理。
4. **渲染器** 读 storyboard、套用时序与动效、导出静音 H.264。
   配音与 BGM 是可选的后期工作。

准备出图清单**不等于**出图。`--mode plan` 之后必须真的把图片放到
`output_master` 路径上，`--mode import` 才可能成功。

## 画布

- 正式输出：1080×1440，30fps，纯白底
- 预览输出：720×960，同比例同时序
- 字幕留在上部安全区
- 插画一律 `object-fit: contain`，**禁止用 cover 裁切**

`scaled()` 把设计坐标换算到输出画布，所以预览和正式成片是像素等比的，
不存在「预览好看、正式跑版」的问题。

### 排版常量（设计坐标系）

| 名称 | 值 |
| --- | --- |
| 字幕框 | `top 86 / left 96 / width 888 / height 288`，z-index 40 |
| 字幕文本框（字体回退分支） | `top 92 / left 104 / right 96` |
| 插画框 | `left 74 / right 74 / top 382 / bottom 42` |
| 图层 z-index | 线稿 10 · detail 20 · 彩色 30 · 字幕 40 |
| 单幕展示板 | contain 适配进 1024×1024 白底方板 |
| 字幕板 | contain 适配进 1536×512 |
| 叙事板 | contain 适配进 1536×512 |

## 动效

### 三层揭示（`transition: cut`，默认）

- 默认母图是「上方字幕 + 下方插画」的合成页；上传的整页也按同一套版面分析处理。
- 在观测到的内容分界处切开字幕与插画，各自按 contain/pad 保持比例。
- 线稿板从彩色板**本地派生**，两者共用同一画布、像素级对齐。
- 按 `文字 → bw_full → color` 从左到右揭示。这是**整层揭示**，
  不是逐根笔画的书写重建。
- 无法可靠切分的页面应当修改母图或改用整页模式，
  **不允许**为了凑一个坐标数字而把字或人裁断。

时序（speed 模式，`enable_detail=false`）：

| 图层 | 起始 | 时长 | 灰阶/色彩处理 |
| --- | --- | --- | --- |
| `text` | 0.00 | 0.22 | — |
| `bw_full` | 0.18 | 0.40 | `grayscale(1) contrast(1.72) brightness(1.12)` |
| `color` | 0.52 | 0.36 | `brightness(1.035) contrast(1.04)` |

quality 模式（`--enable-detail`）多一层 `detail`
（0.48 / 0.17，`grayscale(1) contrast(1.28) brightness(1.055)`），
其余参数为 0.16/0.32 与 0.65/0.23。

若一幕只有彩色板（`staticColor`），它以 1 帧的时长立即出现。

进度曲线是 smoothstep：`p → p²(3-2p)`，先加后减，不是线性。

揭示边缘是**严格竖直**的，来自 `clip-path: inset(0 N% 0 0)`。
手绘感由插画和手写字本身提供，不是靠抖动的遮罩——所以 `--wobble` 默认关闭，
开启时才在边缘叠加多频正弦扰动。

### 翻书（`transition: page-flip`）

- 显示完整、未裁切的母图作为静态页，随后从右下角卷起。
- 保留原有字幕、配色与构图；**不得**再加一层字幕、不得切分页面、
  不得引入黑白/上色阶段。
- 卷起的背面承载本页的**褪色影子**；底下露出下一页。
- 相邻页重叠，所以总时长 = Σ每页帧数 − 相邻重叠之和。

几何（`PageFlipScene`）：

```
curl         = sin(π · p)
bottomTop    = clamp(p / 0.78)            折页下边的推进
topProgress  = clamp((p − 0.28) / 0.72)   折页上边的推进
xTop         = W · (1 − topProgress)
xBottom      = W · (1 − bottomTop)
controlTop   = min(W, xTop    + W·0.19·curl)
controlBottom= min(W, xBottom + W·0.19·curl·0.78)
foldWidth    = 24 + W·0.20·curl
```

折页带由同族 Bezier 向外偏移得到；带内先画
`translateX(foldWidth·0.12) scaleX(1 − curl·0.04)` 变换过的本页，
再叠 `brightness(1.07+curl·0.08) saturate(0.62−curl·0.12)` 与透明度
`0.3+curl·0.32`，然后铺四档渐变 `#d5cfc4 → #f3efe7 → #fffef9 → #d8d0c3`，
再描边 `#b7ada0` 与一道白色高光。

重叠帧数 = `min(round(transition_sec · fps), floor(最短幕帧数 · 0.45))`，
即最长不超过最短一幕的 45%。

## 素材

- 生成母图与上传母图共用 `load_plates()`。
- 保留完整母图作为源；派生的字幕板与插画板各有自己的适配画布；
  线稿板与彩色板互相对齐。
- 线稿派生（本地，不额外消耗生图额度）：

  ```
  format=gray → eq=contrast=1.18:brightness=0.035
              → unsharp=5:5:0.55:5:5:0
  ```

- 母图只出插画时（`layout: full`），插画直接占满插画框；
  字幕由 `--text-mode font` 用真字形渲染，永远不会写错字。
- 选中的画风/配色会进入批次指纹，避免换了画风却复用旧图。

## 字幕

- 字号由 `fallbackFontSize` 推算：行数、最长行、852×306 的可写区域，
  夹在 48–82px 之间；行高 1.34，字距 0.025em，整体倾斜 −0.35°。
- 默认字体 MaShanZheng 是真实的毛笔字形库，字形覆盖率完整。
- `--text-mode image2` 保留上游行为：字幕由生图模型画进母图，
  导入时按 `(1 − 亮度)` 抽成墨迹 alpha 板。
  **此时必须人工核对中文字**，模型会写错字。

## 验证

`python3 tests/test_pipeline.py` 覆盖：

- 画布比例、预览尺寸
- cut 总帧数 = Σ时长；page-flip 按契约扣除重叠
- 分句保留原措辞、按完整句切分
- 327 项画风资产可检索
- 端到端 `plan → import → preview`，并断言输出分辨率与时长

机械检查**不能**证明字形正确、画风到位或参考图还原度——这些必须人眼看成片。
