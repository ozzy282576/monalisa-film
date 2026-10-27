# D.B. Cooper：雨夜里消失的名字

三分钟横屏中文解说短片。由 `production/new_topic.py` 从参考项目 `production/dahlia/`
开出；参考实现只被复制、未被修改，本片所有编辑都发生在这个目录里。

- slug：`dbcooper`
- 出片分支：`arena/01a099c4-desktop-tutorial`
- 成片目标文件名：`DB库珀劫机案_三分钟_带声音.mp4`（1920×1080 / 30fps / 180s）

## 针对上一版两个问题的设计（2026-09-13 重做）

上一版被指出「运镜总是从远到近飞入、解说跟画面对不上」。本片的对策全部落在
`story.json` 与 `render.py` 里，可逐条核对：

1. **运镜多样化**：25 个 AI 镜头分配了 **19 种不同运镜**（横向移、焦点转移、固定、
   跟拍、微距缓推/缓拉、摇、俯拍固定、升/降、拉远、过肩、舷窗 POV、航拍环绕、
   航拍横移、环绕），每镜的 `story.json` 里都有 `camera` 字段写明技巧，
   英文提示词里也写死了该镜头的具体运动（`Camera: ...`）。
   全片只有 1 个镜头是「推向主体」（S06 微距缓推纸条），
   另有 3 个拉远、3 个升降、1 个环绕——不再是单一飞入。
2. **解说与画面对应**：
   - 先写解说稿，再把 30 镜按解说句段逐一对位（每镜 `purpose` 写明它承担哪句解说）；
   - `render.py` 的 `CUTS` 不是均匀 6 秒一切，而是**在真实配音上逐段测出的自然停顿处**
     （`audio/N01-N06.mp3` 的停顿分析，单位是各段配音的原始秒数）——
     每一刀都落在话题切换的停顿上，说到哪、画面就是哪；
   - 信息卡只在该章说到具体数字时出现（S03 人物描述、S08 条件、S20 搜救结果、
     S23 1980 发现、S27 案件状态），卡面文字与此刻的解说内容一致。
3. **无畸变**：
   - 负向提示词覆盖 deformed hands / extra fingers / warped face / morphing /
     distorted anatomy / fast zoom / whip pan 等；
   - 劫机者一律背影/过肩/手部入画（身份未证实，红线禁止用 AI 脸冒充），
     其余真实岗位人物（机组、空姐、银行员工）同样不露正脸；
   - 出片后按手册第 8 步审片：`production/review_film.py` 自动抓黑帧/冻结帧/亮度/电平，
     对照表 `qa/Sxx.jpg` **人工逐镜看**，严重畸变或穿帮的镜头用
     `generate.py --payload '{"only":"Sxx","workers":1}'` 重新生成后再出片。
   - `render.py` 的窗口/变速闸门（factor ≤ 1.33）防止用慢动作掩盖坏素材。

## 事实边界（详见 screenplay.md 与 story.json 的 principles/sources）

- 有来源的事实才写（FBI 官方页、Britannica、Wikipedia、KIRO 7、CBS News，共 5 条来源）；
- AI 画面全部标注「AI情景重现 · 非历史影像」；
- 不指认任何嫌疑人，DNA/指纹只陈述「未得出名字」；
- 不渲染炸弹、爆炸、伤亡；电线与红火柴只作静态道具；
- 中文姓名、日期、字幕一律后期添加。

## 当前状态（2026-09-13）

| 步骤 | 状态 |
|---|---|
| 剧本 / 分镜 / 事实核查 | ✅ `story.json`（25 Agnes + 5 信息卡）+ `screenplay.md` |
| 配音 | ✅ 六段 mp3（voice-00，用户试听选定），`audio/manifest.json` 带 SHA-256 |
| 闸门一 `generate.py --validate` | ✅ 通过（时间轴、提示词、配音哈希全部一致） |
| CUTS 对轨 | ✅ 按真实停顿对齐，32 个编辑段，0 缝隙/重叠，变速比 ≤1.33 |
| Agnes 素材生成 | ⬜ 待 Actions 触发（沙箱连不上 Agnes API） |
| 渲染混音 + 闸门二/三 | ⬜ 素材齐后由「解说短片出片」工作流完成 |
| 审片 / 逐字听检 | ⬜ 出片后做 |

## 出片步骤（在 GitHub Actions 上）

1. **生成素材**：仓库主把 `dbcooper-agnes.workflow.yml` 逐字节复制为
   `.github/workflows/dbcooper-gen.yml`（代理没有 workflows 权限），
   然后在 Actions 触发「DB库珀 · Agnes生成」。25 个镜头 × 75 秒节流 ≈ 30 分钟；
   `results.json` 与 `qa/` 抽帧会自动 commit 回本分支（可逐镜检查）。
2. **出片**：Actions 触发「解说短片出片」（`.github/workflows/commentary-render.yml`，
   已存在），`project` 填 `dbcooper`，`film_name` 填 `DB库珀劫机案_三分钟_带声音.mp4`。
   它按 SHA-256 回填素材（不重新生成）、渲染混音、复测电平，并把成片与报告
   commit 回本分支的 `交付/` 与 `delivery/`。
3. **审片**：`python3 production/review_film.py --film 交付/DB库珀劫机案_三分钟_带声音.mp4
   --project production/dbcooper --work work/dbcooper/review`；
   逐字听检：「逐字听检」工作流填 `dbcooper`。

## 目录

| 路径 | 作用 |
|---|---|
| `story.json` | 分镜计划：30 镜 × 6 秒 / 6 章 × 30 秒，含 `camera` 运镜字段与 5 条来源 |
| `screenplay.md` | 解说稿 + 事实边界 + 分镜表 + 运镜策略说明 |
| `audio/N01-N06.mp3` | 六段配音（voice-00），`manifest.json` 记录文件名/SHA-256/逐字文本 |
| `generate.py` | Agnes 生成（75 秒节流、断点续跑）+ `--validate` 闸门 |
| `fetch_sources.py` | 按 `results.json` 的 SHA-256 回填素材，不重新生成 |
| `render.py` | 剪辑（CUTS 已按真实停顿对齐）、字幕、信息卡、混音、成品复测 |
| `build_audio.py` | numpy 混音 + 静音闸门 |
| `dbcooper.workflow.yml` | 本项目专属的出片工作流模板（备用） |
| `dbcooper-agnes.workflow.yml` | 本项目专属的 Agnes 生成工作流模板（需复制到 .github/workflows/） |
| `results.json` | 生成回执（生成后出现）：请求哈希、SHA-256、CDN 地址 |
| `qa/` | 每镜抽帧回执（生成后出现），人工审片用 |
| `delivery/` | 出片后的实测报告 |
