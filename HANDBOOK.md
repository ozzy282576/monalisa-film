# 出片手册：Agnes 分镜动画 + 男声解说成片

以后按这个模式再出片：先写分镜 → GitHub Actions 串行调 Agnes 出真实动画 → 抽帧质检不过就重做 → 语速统一的解说铺满每段画面 → 一句一条字幕烧录 → 合成成片。

本仓库第一部成片：《蒙娜丽莎失窃案》（约 3 分 04 秒，15 段 × 12.26 秒，1280×720）。

成片：`out/monalisa_theft_narrated.mp4`  
无解说拼接：`out/monalisa_theft.mp4`  
分镜：`storyboard.json`  
下载（当前分支）：https://github.com/ozzy282576/monalisa-film/raw/arena/01a0e83e-monalisa-film/out/monalisa_theft_narrated.mp4

---

## 1. 模式一句话

**不要 Ken Burns 静帧。** 每一镜都是 Agnes Video 生成的真动画。本地只负责质检、解说、字幕、拼接。API Key 只放在 GitHub Secret，禁止提交进仓库。

---

## 2. 工具链

| 环节 | 工具 | 用途 |
|------|------|------|
| 分镜脚本 | `storyboard.json` | id / 秒数 / 英文画面 prompt / 中文旁白草稿 |
| 视频生成 | Agnes **Video 2.5 Flash**（`agnes-video-2.5-flash`） | 720P，4–12 秒，text 模式 |
| 调度 | GitHub Actions `agnes-film.yml` | 有 `AGNES_API_KEY` 的 runner 上串行出片 |
| 生成脚本 | `generate_clips.py` | 创建任务、轮询、下载、机器 QC、失败重试、每镜 push |
| 无声拼接 | `scripts/assemble.py` | ffmpeg concat `clips/01–15.mp4` |
| 抽帧质检 | ffmpeg + 人工看图 | 畸变、黑边、冻帧、道具错误（如摘帽叠帽） |
| 解说 | 同一男声 TTS（本片 `voice-02`，中文） | 每段字数接近，自然时长贴 12.26 秒 |
| 字幕 | SRT，一句一条 | ffmpeg `subtitles` + Noto Sans CJK SC 烧录 |
| 合成 | ffmpeg | 画面对齐、音频 aac、libx264 |

### Agnes API（现行）

- 创建：`POST $AGNES_BASE_URL/videos`（runner 里走 `https://apihub.agnes-ai.com`）
- 轮询：`https://apihub.agnes-ai.com/agnesapi?video_id=&model_name=agnes-video-2.5-flash`
- 鉴权：`Authorization: Bearer $AGNES_API_KEY`
- 尺寸：Flash **只有 720P**
- `seconds`：字符串 `"4"`–`"12"`
- 模式：text / keyframe / reference；本片全部 **text**
- 文档：https://wiki.agnes-ai.com/en/docs/agnes-video-25-flash  
- 注意：v2.0 已退役，不要再用

### GitHub Secret

- 名称必须是 **`AGNES_API_KEY`**（已有就 Update，不要再 New 一个同名）
- 位置：Settings → Secrets and variables → Actions
- **永远不要**写进 `.env` 提交、不要写进 workflow 明文、不要出现在 commit

---

## 3. 仓库结构

```
storyboard.json              # 15 镜：prompt + 旁白草稿
generate_clips.py            # Agnes 串行生成 + QC + 最多 50 次重试
scripts/assemble.py          # 无声 concat
.github/workflows/agnes-film.yml
clips/01.mp4 … 15.mp4        # 过检动画（真运动，非静帧）
out/monalisa_theft.mp4       # 无解说成片
out/monalisa_theft_narrated.mp4
out/narration.srt
work/tasks.json              # 每镜任务状态
work/progress.md             # 机器进度（pass ≠ 画面合格）
HANDBOOK.md                  # 本手册
```

---

## 4. 出片流水线（下次照抄）

### A. 写分镜

1. 目标时长：约 3 分钟 → **15 段 × 12 秒**（Flash 上限 12 秒）。
2. 每段 `storyboard.json`：
   - `id`：两位数字 `"01"`…
   - `seconds`：`"12"`
   - `title`：中文场次名
   - `prompt`：**英文**、写死时代、人物外貌、禁止项（No text, no extra fingers, no second Mona Lisa…）
   - `narration`：中文草稿（后期会按字数重写以对齐时长）
3. Prompt 要写清「不要出现什么」。本片翻车过的例子：
   - 08：卫兵摘帽后头上还有帽 → 必须写 **hats glued to heads, never a second hat, hands hold batons not hats**
   - 14：不要出现玻璃金字塔（1914 年没有）
   - 不要第二张蒙娜丽莎、不要现代汽车、不要可读英文字

### B. 用 Actions 生成（不要本机带 Key 跑）

1. 确认 Secret `AGNES_API_KEY` 已在仓库。
2. 只开 **一个** workflow：`Generate Mona Lisa film (Agnes)`。  
   **队列满或已有 in_progress 时禁止再开第二个。**
3. 规则（写进 `generate_clips.py`，不要改松）：
   - **一次只 create 一镜**
   - 上一镜 **complete 后再等 75 秒** 才 create 下一镜
   - 机器 QC 失败 → 同一 id 重试，默认 **最多 50 次**（`MAX_TRIES`）
   - 已 pass 的镜 **不要重做**，除非后来人工判定画面不合格再 `FORCE_REDO`
   - 每完成一镜就 commit/push `clips/{id}.mp4`，方便盯进度
4. 机器 QC（`generate_clips.py`）大致检查：
   - 文件 > 80KB
   - 时长约 9–14.5 秒
   - 能被 ffmpeg 打开
5. **`progress.md` 的 pass ≠ 画面合格。** 必须抽帧人工看。

### C. 抽帧质检（不过就重做，不准凑合拼接）

每镜用 ffmpeg 抽 1 / 3 / 5 / 7 / 9 / 11 秒关键帧，看：

- 是否真的在动（不是静图缓推）
- 人体：五指、脸不融化
- 道具：帽子、画、箱子数量对不对
- 时代错误：金字塔、汽车、玻璃罩
- 黑边、比例、冻帧

不合格：在状态里对该 id 设 **FORCE_REDO**，再跑 Actions（仍遵守「同时只有一个 job」）。  
本片 08 摘帽叠帽扛了多轮，最后靠改 prompt + 50 次重试才过。

### D. 解说（最容易把体验做差的一步）

硬性要求：

1. **同一把男声**，全程不要换声线。
2. **每段语速相同。** 不要用大幅 `atempo` 把 8 秒语音拉成 12 秒（会一镜快一镜慢）。
3. **不要用长静音垫** 把短解说撑满画面。
4. 做法：每段旁白 **字数接近**（本片约 70 字、三句左右），TTS 自然时长聚在 **12.0–12.5 秒**，再与 12.26 秒画面对齐。只允许 **±5% 以内** 的微调。
5. 画面一切，解说也切；解说说完画面不应再空转很久。
6. 字幕：**一句一条**，不要两行一起蹦出来。用 `。！？` 断句。

本片旁白最终以烧录进 `out/monalisa_theft_narrated.mp4` 为准；`storyboard.json` 里是早期草稿。

### E. 烧录与成片

```text
1. ffmpeg concat 15 段画面（-c copy）→ picture.mp4
2. 每段 VO 对齐 12.26s（禁止大静音、禁止大变速）
3. 混音：解说为主；若有垫乐，压到解说 1/6 左右
4. 一句一条 SRT
5. 烧字幕：Noto Sans CJK SC，白字黑边，底部
   ffmpeg -i picture.mp4 -i all.wav -vf subtitles=narration.srt:fontsdir=... 
          -c:v libx264 -crf 18 -c:a aac
6. 验收：总长约 150–210 秒；本片 00:03:03
```

成片大于 50MB 时 GitHub 会警告，仍可 raw 下载；长期建议 Git LFS。

---

## 5. 操作口令（和制作时一致）

| 你说 | 含义 |
|------|------|
| 继续 / 继续生成 / 跟进度 | 缺哪镜补哪镜，已 pass 不动 |
| 出无瑕疵的片 | 画面 fail 就 redo，不准 concat 凑数 |
| 打 50 次 | `MAX_TRIES=50` |
| 不要同时开两个 Actions | concurrency 已设，仍不要手动再 dispatch |
| 配解说和字幕 | 男声 + 一句一条 + 音画等长 |

---

## 6. 下一片怎么开

1. 复制本仓库或新建 repo，保留 `generate_clips.py` / workflow / assemble。
2. 重写 `storyboard.json`（15 镜或按 12 秒整数倍改数量）。
3. Secret 仍用 `AGNES_API_KEY`。
4. 改 workflow 的分支名（本片锁在 `arena/01a0e83e-monalisa-film`）。
5. 跑生成 → 抽帧 → 不合格 FORCE_REDO → 等长解说 → 烧字幕。
6. 不要把 Key、临时 `work/narr*` 垃圾、未过检废片推进 `main` 也没关系，但 **Key 绝对不能进 Git**。

---

## 7. 本片抖音用文案

**题目**  
蒙娜丽莎，是被一个工人偷走的

**简介（适合抖音，约 15 秒口播 / 封面文案）**  
1911 年，卢浮宫一个装镜框的意大利工人，把蒙娜丽莎连框取下，卷进罩衫，大摇大摆走出门。没有警报，没有追捕。两年后，这张世界最贵的脸，才在佛罗伦萨被打开。

**向读者提一句**  
如果今天再丢一次，你觉得还能找回来吗？
