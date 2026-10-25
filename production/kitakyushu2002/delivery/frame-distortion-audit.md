# 成片逐帧畸变 / 时序 QC

- 成片：`北九州监禁案_逃出魔窟的少女，七条人命背后的秘密_三分钟_带声音.mp4`
- SHA-256：`435ff39b05aad74d5bae55f030e0a1c4bbf58732b745c589d548cff3ecf66005`
- 视频：1920×1080 / 30.000 fps / 180.000 秒
- 覆盖：解码并分析 **5400/5400 帧**；逐帧 MediaPipe 人脸/手检测；320x180 时序分析
- 自动状态：**REVIEW**（机器结果，不等同于无任何视觉瑕疵）

## 全片结果

- PTS 连续性异常：0
- 亮度低于 12 的帧：13（片头/片尾淡入淡出需按时间线解释）
- 非计划黑帧：0
- >1 秒近静止区段：6；其中非信息卡/片尾段：6
- 帧差/光流/亮度突变待复核窗口：14
- 人脸检测：逐帧总检测 940；达到复核阈值的候选 687
- 手部检测：逐帧总检测 976；超出宽松几何边界的 landmark 事件 121

## 镜头统计

| 镜头 | 类型 | 帧数 | 人脸检出 | 手检出 | 光流残差 P95 峰值 | 时序异常窗口 |
|---|---:|---:|---:|---:|---:|---:|
| S01 | agnes | 142 | 1 | 0 | 1.762 | 1 |
| S02 | graphic | 129 | 0 | 0 | 210.1358 | 0 |
| S03 | agnes | 100 | 0 | 0 | 0.3369 | 0 |
| S04 | agnes | 144 | 0 | 9 | 0.9584 | 0 |
| S05 | agnes | 112 | 0 | 0 | 1.657 | 0 |
| S06 | agnes | 158 | 0 | 0 | 0.8234 | 0 |
| S07 | agnes | 150 | 0 | 121 | 1.8855 | 0 |
| S08 | agnes | 180 | 0 | 0 | 0.0741 | 0 |
| S09 | agnes | 184 | 184 | 0 | 0.8676 | 0 |
| S10 | graphic | 109 | 34 | 0 | 175.6739 | 0 |
| S11 | agnes | 105 | 0 | 12 | 0.1882 | 0 |
| S12 | agnes | 101 | 7 | 101 | 6.1809 | 2 |
| S13 | agnes | 131 | 0 | 0 | 0.1555 | 0 |
| S14 | agnes | 61 | 0 | 0 | 0.1202 | 0 |
| S15 | agnes | 142 | 0 | 0 | 0.401 | 0 |
| S16 | agnes | 57 | 0 | 0 | 0.0359 | 0 |
| S17 | graphic | 84 | 33 | 0 | 190.7023 | 0 |
| S18 | agnes | 69 | 12 | 0 | 0.0517 | 0 |
| S19 | agnes | 67 | 0 | 0 | 0.1181 | 0 |
| S20 | agnes | 111 | 0 | 47 | 3.4475 | 2 |
| S21 | agnes | 121 | 0 | 83 | 2.5864 | 1 |
| S22 | agnes | 96 | 69 | 0 | 0.0739 | 0 |
| S23 | agnes | 154 | 0 | 0 | 0.4824 | 0 |
| S24 | agnes | 115 | 0 | 0 | 0.0795 | 0 |
| S25 | agnes | 86 | 0 | 0 | 0.2047 | 0 |
| S26 | agnes | 61 | 0 | 0 | 0.1112 | 0 |
| S27 | agnes | 84 | 84 | 168 | 0.2718 | 0 |
| S28 | agnes | 125 | 0 | 0 | 0.7682 | 0 |
| S29 | agnes | 153 | 0 | 0 | 0.8601 | 0 |
| S30 | graphic | 189 | 24 | 0 | 250.3645 | 0 |
| S31 | agnes | 88 | 0 | 0 | 0.0826 | 0 |
| S32 | graphic | 103 | 21 | 0 | 255.5656 | 3 |
| S33 | agnes | 75 | 75 | 0 | 0.0855 | 0 |
| S34 | agnes | 161 | 161 | 227 | 1.6736 | 0 |
| S35 | agnes | 106 | 106 | 32 | 0.2575 | 0 |
| S36 | agnes | 110 | 110 | 176 | 2.9854 | 2 |
| S37 | agnes | 26 | 0 | 0 | 0.1068 | 0 |
| S38 | graphic | 123 | 19 | 0 | 194.3723 | 0 |
| S39 | agnes | 180 | 0 | 0 | 0.2311 | 0 |
| S40 | graphic | 108 | 0 | 0 | 190.4718 | 0 |
| S41 | agnes | 109 | 0 | 0 | 0.0604 | 0 |
| S42 | agnes | 91 | 0 | 0 | 0.1602 | 1 |
| S43 | agnes | 139 | 0 | 0 | 0.3067 | 0 |
| S44 | agnes | 166 | 0 | 0 | 0.1562 | 0 |
| S45 | agnes | 181 | 0 | 0 | 10.823 | 1 |
| END | graphic | 114 | 0 | 0 | 0.6534 | 1 |

## 复核文件

- 全 45 镜 + 片尾画面中帧：`work/kitakyushu2002/final-frame-audit/contacts/shot-midpoints.jpg`
- 逐帧指标 CSV：`work/kitakyushu2002/final-frame-audit/frame-metrics.csv`
- 候选异常原始分辨率帧：`['work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00000_t000.000.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00001_t000.033.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00002_t000.067.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00003_t000.100.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00004_t000.133.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00005_t000.167.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00006_t000.200.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00007_t000.233.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00008_t000.267.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00009_t000.300.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00010_t000.333.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00451_t015.033.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00452_t015.067.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00453_t015.100.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00454_t015.133.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00455_t015.167.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00456_t015.200.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00457_t015.233.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00458_t015.267.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00459_t015.300.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00460_t015.333.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00461_t015.367.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00462_t015.400.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00463_t015.433.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00464_t015.467.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_00465_t015.500.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01522_t050.733.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01523_t050.767.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01524_t050.800.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01525_t050.833.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01526_t050.867.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01527_t050.900.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01528_t050.933.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01529_t050.967.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_01530_t051.000.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02251_t075.033.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02252_t075.067.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02253_t075.100.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02254_t075.133.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02255_t075.167.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02256_t075.200.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02257_t075.233.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02258_t075.267.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02259_t075.300.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02418_t080.600.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02419_t080.633.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02420_t080.667.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02421_t080.700.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_02422_t080.733.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03686_t122.867.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03687_t122.900.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03688_t122.933.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03689_t122.967.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03690_t123.000.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03695_t123.167.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03696_t123.200.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03697_t123.233.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03698_t123.267.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03699_t123.300.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03700_t123.333.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03701_t123.367.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03702_t123.400.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03703_t123.433.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03704_t123.467.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03705_t123.500.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03706_t123.533.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03707_t123.567.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03708_t123.600.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03709_t123.633.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_03710_t123.667.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04087_t136.233.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04088_t136.267.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04089_t136.300.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04090_t136.333.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04091_t136.367.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04100_t136.667.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04101_t136.700.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04102_t136.733.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04103_t136.767.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04104_t136.800.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04792_t159.733.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04793_t159.767.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04794_t159.800.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04795_t159.833.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_04796_t159.867.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05280_t176.000.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05281_t176.033.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05282_t176.067.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05283_t176.100.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05284_t176.133.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05285_t176.167.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05286_t176.200.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05287_t176.233.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05288_t176.267.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05289_t176.300.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05290_t176.333.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05291_t176.367.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05292_t176.400.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05293_t176.433.jpg', 'work/kitakyushu2002/final-frame-audit/suspect-frames/frame_05294_t176.467.jpg']`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S07.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S11.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S12.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S20.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S21.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S27.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S34.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S35.jpg`
- 手部动态接触表：`work/kitakyushu2002/final-frame-audit/contacts/hands-S36.jpg`

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
