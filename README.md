# monalisa-film · 悬案档案

抖音横版（1920×1080 · 24fps · ~3 分钟）真实案件纪录片短视频生产线。

## 本片：EP.02 《雨夜屠夫 · 林过云案（1982 香港）》

成片：`output/lin_guoyun_1982_rainy_night_butcher_1080p.mp4`

### 管线（全程序化动画，非图片轮播）

1. **旁白** — TTS 六段（`audio/narration/s1..s6.mp3`），时间轴由实测音频时长驱动（`src/timeline.js`）。
2. **配乐** — `src/music.py` 用 numpy/scipy 合成黑暗氛围配乐：drone、心跳、riser、sting、boom，并按事件表自动对点。
3. **画面** — `src/render.js` + `src/scenes.js` 用 @napi-rs/canvas 逐帧程序化渲染六场动画：
   雨夜街头/菲林标题切片、受害者证据卡与出租车连线、暗房显影与拘捕、搜屋证物标签与时间轴、
   法庭天平/陪审团计票/死刑印章、的士挡风玻璃雨滴与终幕标题；叠加雨、雾、胶片颗粒、
   扫描线、暗角、震屏、白闪转场；中文字幕逐句同步。
4. **中文字体** — @fontsource Noto Sans/Serif SC 按 unicode-range 子集逐字选面渲染（`src/textkit.js`），
   `tools/coverage.js` 校验全片无缺字（无豆腐块）。
5. **合成** — `src/assemble.js`：raw RGBA 帧流 → libx264，再与旁白/配乐混音（adelay 对点 + loudnorm -14 LUFS）。
6. **QC/QA** — `tools/qa.py`：容器/流规格、时长对轴、逐秒亮度/方差（无死黑/无冻帧）、白闪计数、
   缺字校验、音频峰值/静默段/响度，全部 PASS 才收片。

### 复建命令

```bash
npm run render    # 渲染全部帧并编码 build/video_silent.mp4
npm run music     # 合成 build/music.wav
npm run assemble  # 混音封装成片 output/*.mp4
npm run qa        # 质量校验
```

## 仓库结构

```
assets/plates/   AI 生成的场景底图（6 张）
audio/narration/ 六段旁白
src/             渲染器 / 场景 / 时间轴 / 字体引擎 / 配乐 / 合成
tools/           覆盖率与 QA
output/          成片
```
