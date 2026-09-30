# 上色指令记录（11 13 15 16 17 19 20 21 22 23）

用户否决了双色阶/黑白方案，要求**全彩**。已上色的 13 幕（01–10、12、14、18）
走的是"上色"而非"重画"：构图、动作、人脸、墨线全部锁死，只加颜色。
重画会让 23 幕的人物连续性崩掉——AI 每次重绘都会挪动门框、窗户和手的位置。

下面 10 幕仍是**纯灰阶**（有色像素占比 0.00%，见 `scripts/noire/inspect_frames.py`），
需要在下一轮配额里按同样的方式上色。

| 幕 | 调色 | 画面 | 上色要点 |
|----|------|------|----------|
| 11 | c_night | 雨夜墙根／地上物件 | 墙＝深蓝黑砖＋冷湿高光；雨丝＝浅青；泥水＝褐＋冷蓝反光；草＝暗绿 |
| 13 | c_amber | 黑板＋粉笔手 | 黑板＝去饱和石板蓝绿（不要纯黑）；粉笔字＝暖白；木框＝琥珀棕 |
| 15 | c_amber | 特写手＋红叉 | 皮肤＝暖赭＋红褐暗部；背景＝暖棕黑；红叉保留为醒目红强调 |
| 16 | c_flat | 法医统计柱状图 | 纸＝暖米色；墨线＝暖褐；柱＝灰蓝＋暗赭；整体像影印卷宗，克制 |
| 17 | c_cold | 两人对峙 | 老者＝暖肤＋冷蓝暗部；年轻者＝蓝黑暗剪影＋暖轮廓光；房间＝深冷青 |
| 19 | c_rain | 雨夜抓捕 | 天空＝深靛＋紫白闪电；雨丝＝浅青；警灯红蓝；湿沥青反光 |
| 20 | c_cold | 杂物间拖把 | 杂物＝暖褐＋赭；光＝冷蓝白侧光；空气中有化学雾气；阴影＝深蓝黑 |
| 21 | c_warm | 法庭 | 木作＝暖红棕（桃花心木）＋琥珀；石柱＝暖灰＋金光；光尘＝金 |
| 22 | c_warm | 雨停日出 | 光柱＝暖金；地板＝蜜棕；人物＝深赭＋金轮廓光；远景＝柔和冷灰蓝 |
| 23 | c_flat | 全黑花字＋手铐 | 聚光＝暖琥珀白＋金色柔光；手铐＝抛光钢＋暖高光＋冷蓝反光；黑底带一丝深靛 |

## 共用的指令前缀

> Colourise this hand-drawn black-and-white ink illustration into a full-colour
> hand-drawn graphic-novel panel.
>
> **CRITICAL**: keep the composition, framing and every ink line EXACTLY as they
> are. Do not move, add or remove any element. Ink-and-paint only, not a redraw.

## 共用后缀

> Painted ink-and-wash, bold black linework preserved.
>
> No text, no lettering, no numbers, no watermark, no border.

## 配音仍缺的 12 幕

12 13 14 15 16 17 18 19 20 21 22 23 —— 文案见 `script.json` 的 `narration`
字段，音色沿用 `voice-00`，写入 `voice/NN.mp3`。渲染端会自动发现，无需维护
`media.voice`。
