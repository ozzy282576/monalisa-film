# 成片逐帧畸变 / 时序 QC

- 成片：`狂犬病疫苗_一百四十年前那场赌局_三分钟_带声音.mp4`
- SHA-256：`f0b224cd1195f5c87413bf398be7c169311fe325ebf45fb74e3e548cb560042b`
- 视频：1920×1080 / 30.000 fps / 180.000 秒
- 覆盖：解码并分析 **5400/5400 帧**；逐帧 MediaPipe 人脸/手检测；320x180 时序分析
- 自动状态：**REVIEW**（机器结果，不等同于无任何视觉瑕疵）

## 全片结果

- PTS 连续性异常：0
- 亮度低于 12 的帧：14（片头/片尾淡入淡出需按时间线解释）
- 非计划黑帧：0
- >1 秒近静止区段：1；其中非信息卡/片尾段：0
- 帧差/光流/亮度突变待复核窗口：9
- 人脸检测：逐帧总检测 158；达到复核阈值的候选 0
- 手部检测：逐帧总检测 1319；超出宽松几何边界的 landmark 事件 265

## 镜头统计

| 镜头 | 类型 | 帧数 | 人脸检出 | 手检出 | 光流残差 P95 峰值 | 时序异常窗口 |
|---|---:|---:|---:|---:|---:|---:|
| S01 | agnes | 122 | 11 | 31 | 2.0292 | 0 |
| S02 | agnes | 53 | 0 | 10 | 8.449 | 0 |
| S03 | agnes | 123 | 23 | 12 | 5.2792 | 1 |
| S04 | agnes | 41 | 0 | 0 | 1.1245 | 0 |
| S05 | agnes | 59 | 0 | 1 | 7.2709 | 2 |
| S06 | agnes | 95 | 0 | 0 | 1.9674 | 0 |
| S07 | graphic | 125 | 15 | 0 | 196.7075 | 0 |
| S08 | agnes | 192 | 0 | 0 | 1.5463 | 0 |
| S09 | agnes | 147 | 0 | 0 | 1.3692 | 0 |
| S10 | agnes | 192 | 45 | 56 | 1.4344 | 0 |
| S11 | agnes | 138 | 25 | 0 | 1.6655 | 0 |
| S12 | agnes | 120 | 3 | 0 | 2.0137 | 0 |
| S13 | graphic | 104 | 0 | 0 | 180.6624 | 0 |
| S14 | agnes | 59 | 4 | 0 | 2.208 | 0 |
| S15 | agnes | 167 | 0 | 0 | 1.0135 | 0 |
| S16 | agnes | 57 | 0 | 0 | 1.4159 | 0 |
| S17 | agnes | 110 | 1 | 156 | 1.3909 | 0 |
| S18 | agnes | 119 | 0 | 247 | 2.6745 | 0 |
| S19 | agnes | 70 | 1 | 0 | 1.1376 | 0 |
| S20 | agnes | 78 | 0 | 0 | 0.6581 | 0 |
| S21 | graphic | 76 | 0 | 0 | 124.2979 | 0 |
| S22 | agnes | 88 | 0 | 0 | 0.4924 | 0 |
| S23 | agnes | 238 | 7 | 126 | 3.0219 | 0 |
| S24 | agnes | 36 | 0 | 0 | 0.7523 | 0 |
| S25 | agnes | 115 | 0 | 0 | 1.119 | 0 |
| S26 | agnes | 101 | 0 | 5 | 0.8904 | 0 |
| S27 | agnes | 63 | 0 | 12 | 1.4979 | 0 |
| S28 | graphic | 141 | 6 | 0 | 216.8278 | 0 |
| S29 | agnes | 63 | 0 | 0 | 0.4148 | 0 |
| S30 | agnes | 270 | 5 | 301 | 6.319 | 4 |
| S31 | agnes | 31 | 3 | 0 | 0.1311 | 0 |
| S32 | agnes | 94 | 1 | 0 | 2.1694 | 0 |
| S33 | agnes | 57 | 0 | 0 | 1.0786 | 0 |
| S34 | graphic | 83 | 0 | 0 | 151.9111 | 0 |
| S35 | agnes | 123 | 0 | 0 | 0.8224 | 0 |
| S36 | agnes | 71 | 8 | 0 | 0.5448 | 0 |
| S37 | agnes | 59 | 0 | 0 | 1.0111 | 0 |
| S38 | graphic | 302 | 0 | 0 | 251.0183 | 0 |
| S39 | agnes | 122 | 0 | 2 | 1.115 | 0 |
| S40 | agnes | 84 | 0 | 84 | 3.9656 | 0 |
| S41 | agnes | 83 | 0 | 0 | 1.378 | 0 |
| S42 | graphic | 204 | 0 | 0 | 196.6995 | 0 |
| S43 | agnes | 66 | 0 | 61 | 2.1047 | 0 |
| S44 | agnes | 213 | 0 | 215 | 7.3051 | 0 |
| S45 | agnes | 266 | 0 | 0 | 0.8681 | 1 |
| END | graphic | 180 | 0 | 0 | 0.3457 | 1 |

## 复核文件

- 全 45 镜 + 片尾画面中帧：`work/rabies1885/final-frame-audit/contacts/shot-midpoints.jpg`
- 逐帧指标 CSV：`work/rabies1885/final-frame-audit/frame-metrics.csv`
- 候选异常原始分辨率帧：`['work/rabies1885/final-frame-audit/suspect-frames/frame_00176_t005.867.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00177_t005.900.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00178_t005.933.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00179_t005.967.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00180_t006.000.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00181_t006.033.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00182_t006.067.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00381_t012.700.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00382_t012.733.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00383_t012.767.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00384_t012.800.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00385_t012.833.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00386_t012.867.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00388_t012.933.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00389_t012.967.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00390_t013.000.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00391_t013.033.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00392_t013.067.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00393_t013.100.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00394_t013.133.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00395_t013.167.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00396_t013.200.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_00397_t013.233.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03092_t103.067.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03093_t103.100.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03094_t103.133.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03095_t103.167.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03096_t103.200.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03097_t103.233.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03098_t103.267.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03099_t103.300.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03100_t103.333.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03101_t103.367.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03102_t103.400.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03103_t103.433.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03104_t103.467.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03105_t103.500.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03106_t103.533.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03107_t103.567.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03108_t103.600.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03109_t103.633.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03110_t103.667.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03111_t103.700.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03112_t103.733.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03113_t103.767.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03114_t103.800.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03115_t103.833.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03116_t103.867.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03117_t103.900.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03118_t103.933.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03119_t103.967.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03120_t104.000.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03121_t104.033.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03122_t104.067.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03123_t104.100.jpg', 'work/rabies1885/final-frame-audit/suspect-frames/frame_03124_t104.133.jpg']`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S01.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S02.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S03.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S10.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S17.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S18.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S23.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S27.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S30.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S40.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S43.jpg`
- 手部动态接触表：`work/rabies1885/final-frame-audit/contacts/hands-S44.jpg`

## 限制

自动检测会漏检遮挡、极小目标和模型本身识别不到的 AI 畸变；时序异常也可能是有意运镜、火焰、蒸汽或字幕变化。所以候选必须看原始分辨率前后帧，语义与解剖必须人工目检。没有候选不等于数学上证明‘完美无瑕疵’。

## 全部输出帧的视觉接触表

全片 5400 帧按时间顺序逐帧收录、没有抽样；46 张分镜头接触表，每格 160×90 像素。缩略图用于扫查，异常仍须查看原始分辨率。

- 清单：`../qa/final-frame-review/all-frames/manifest.json`

- [S01](../qa/final-frame-review/all-frames/S01-all-frames.jpg)
- [S02](../qa/final-frame-review/all-frames/S02-all-frames.jpg)
- [S03](../qa/final-frame-review/all-frames/S03-all-frames.jpg)
- [S04](../qa/final-frame-review/all-frames/S04-all-frames.jpg)
- [S05](../qa/final-frame-review/all-frames/S05-all-frames.jpg)
- [S06](../qa/final-frame-review/all-frames/S06-all-frames.jpg)
- [S07](../qa/final-frame-review/all-frames/S07-all-frames.jpg)
- [S08](../qa/final-frame-review/all-frames/S08-all-frames.jpg)
- [S09](../qa/final-frame-review/all-frames/S09-all-frames.jpg)
- [S10](../qa/final-frame-review/all-frames/S10-all-frames.jpg)
- [S11](../qa/final-frame-review/all-frames/S11-all-frames.jpg)
- [S12](../qa/final-frame-review/all-frames/S12-all-frames.jpg)
- [S13](../qa/final-frame-review/all-frames/S13-all-frames.jpg)
- [S14](../qa/final-frame-review/all-frames/S14-all-frames.jpg)
- [S15](../qa/final-frame-review/all-frames/S15-all-frames.jpg)
- [S16](../qa/final-frame-review/all-frames/S16-all-frames.jpg)
- [S17](../qa/final-frame-review/all-frames/S17-all-frames.jpg)
- [S18](../qa/final-frame-review/all-frames/S18-all-frames.jpg)
- [S19](../qa/final-frame-review/all-frames/S19-all-frames.jpg)
- [S20](../qa/final-frame-review/all-frames/S20-all-frames.jpg)
- [S21](../qa/final-frame-review/all-frames/S21-all-frames.jpg)
- [S22](../qa/final-frame-review/all-frames/S22-all-frames.jpg)
- [S23](../qa/final-frame-review/all-frames/S23-all-frames.jpg)
- [S24](../qa/final-frame-review/all-frames/S24-all-frames.jpg)
- [S25](../qa/final-frame-review/all-frames/S25-all-frames.jpg)
- [S26](../qa/final-frame-review/all-frames/S26-all-frames.jpg)
- [S27](../qa/final-frame-review/all-frames/S27-all-frames.jpg)
- [S28](../qa/final-frame-review/all-frames/S28-all-frames.jpg)
- [S29](../qa/final-frame-review/all-frames/S29-all-frames.jpg)
- [S30](../qa/final-frame-review/all-frames/S30-all-frames.jpg)
- [S31](../qa/final-frame-review/all-frames/S31-all-frames.jpg)
- [S32](../qa/final-frame-review/all-frames/S32-all-frames.jpg)
- [S33](../qa/final-frame-review/all-frames/S33-all-frames.jpg)
- [S34](../qa/final-frame-review/all-frames/S34-all-frames.jpg)
- [S35](../qa/final-frame-review/all-frames/S35-all-frames.jpg)
- [S36](../qa/final-frame-review/all-frames/S36-all-frames.jpg)
- [S37](../qa/final-frame-review/all-frames/S37-all-frames.jpg)
- [S38](../qa/final-frame-review/all-frames/S38-all-frames.jpg)
- [S39](../qa/final-frame-review/all-frames/S39-all-frames.jpg)
- [S40](../qa/final-frame-review/all-frames/S40-all-frames.jpg)
- [S41](../qa/final-frame-review/all-frames/S41-all-frames.jpg)
- [S42](../qa/final-frame-review/all-frames/S42-all-frames.jpg)
- [S43](../qa/final-frame-review/all-frames/S43-all-frames.jpg)
- [S44](../qa/final-frame-review/all-frames/S44-all-frames.jpg)
- [S45](../qa/final-frame-review/all-frames/S45-all-frames.jpg)
- [END](../qa/final-frame-review/all-frames/END-all-frames.jpg)

人工逐帧视觉复核状态：**PENDING**。自动结果或缩略接触表都不等于无瑕疵。
