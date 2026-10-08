# 蒙娜丽莎失窃案 · 动画短片

Agnes Video 2.5 Flash 生成的约 3 分钟成片（15 段真动画 + 男声解说 + 一句一条字幕）。

**成片下载：** [out/monalisa_theft_narrated.mp4](https://github.com/ozzy282576/monalisa-film/raw/arena/01a0e83e-monalisa-film/out/monalisa_theft_narrated.mp4)

**出片手册（工具链 / 质检 / 解说规则 / 下一片怎么开）：** [HANDBOOK.md](HANDBOOK.md)

## 抖音

- **题目：** 蒙娜丽莎，是被一个工人偷走的
- **简介：** 1911 年，卢浮宫一个装镜框的意大利工人，把蒙娜丽莎连框取下，卷进罩衫，大摇大摆走出门。没有警报，没有追捕。两年后，这张世界最贵的脸，才在佛罗伦萨被打开。
- **向读者提一句：** 如果今天再丢一次，你觉得还能找回来吗？

## 快速开始（下一片）

1. 仓库 Settings → Secrets → Actions 确认已有 `AGNES_API_KEY`（不要再 New，不要提交 Key）
2. 改 `storyboard.json`
3. 只开一个 workflow：**Generate Mona Lisa film (Agnes)**
4. 按手册抽帧质检，不合格重做；**先对照实际画面写解说**，再等长配音、烧字幕
