# 成片逐帧畸变 / 时序 QC

- 成片：`韩国雨衣杀手柳永哲_十个月，二十条人命_三分钟_带声音.mp4`
- SHA-256：`5bd4a3de7fe074581a0dd2bcba359ccc7a896c289620537888bfdc479cae0efa`
- 视频：1920×1080 / 30.000 fps / 180.000 秒
- 覆盖：解码并分析 **5400/5400 帧**；逐帧 MediaPipe 人脸/手检测；320x180 时序分析
- 自动状态：**REVIEW**（机器结果，不等同于无任何视觉瑕疵）

## 全片结果

- PTS 连续性异常：0
- 亮度低于 12 的帧：16（片头/片尾淡入淡出需按时间线解释）
- 非计划黑帧：2
- >1 秒近静止区段：0；其中非信息卡/片尾段：0
- 帧差/光流/亮度突变待复核窗口：5
- 人脸检测：逐帧总检测 733；达到复核阈值的候选 201
- 手部检测：逐帧总检测 945；超出宽松几何边界的 landmark 事件 128

## 镜头统计

| 镜头 | 类型 | 帧数 | 人脸检出 | 手检出 | 光流残差 P95 峰值 | 时序异常窗口 |
|---|---:|---:|---:|---:|---:|---:|
| S01 | agnes | 132 | 0 | 0 | 1.0108 | 1 |
| S02 | graphic | 76 | 0 | 0 | 186.8277 | 0 |
| S03 | agnes | 51 | 3 | 0 | 0.3178 | 0 |
| S04 | agnes | 83 | 0 | 0 | 1.1364 | 0 |
| S05 | agnes | 76 | 76 | 0 | 0.5402 | 0 |
| S06 | agnes | 111 | 108 | 185 | 0.6982 | 0 |
| S07 | agnes | 72 | 0 | 0 | 0.5093 | 0 |
| S08 | agnes | 129 | 0 | 0 | 2.0061 | 0 |
| S09 | agnes | 145 | 0 | 0 | 0.5334 | 0 |
| S10 | agnes | 83 | 2 | 0 | 3.3386 | 0 |
| S11 | graphic | 105 | 55 | 0 | 228.0495 | 0 |
| S12 | agnes | 115 | 0 | 0 | 1.5382 | 0 |
| S13 | agnes | 124 | 0 | 125 | 4.5705 | 1 |
| S14 | agnes | 71 | 0 | 0 | 0.9955 | 0 |
| S15 | agnes | 154 | 3 | 0 | 1.5767 | 0 |
| S16 | agnes | 91 | 0 | 0 | 0.6013 | 0 |
| S17 | agnes | 93 | 0 | 0 | 0.9115 | 0 |
| S18 | graphic | 128 | 4 | 0 | 270.0901 | 0 |
| S19 | agnes | 110 | 7 | 0 | 0.7032 | 0 |
| S20 | agnes | 123 | 70 | 0 | 0.3623 | 0 |
| S21 | agnes | 89 | 0 | 0 | 0.4359 | 0 |
| S22 | agnes | 86 | 0 | 0 | 1.0233 | 0 |
| S23 | agnes | 108 | 0 | 0 | 0.5891 | 0 |
| S24 | agnes | 121 | 2 | 0 | 0.9321 | 0 |
| S25 | graphic | 91 | 0 | 0 | 164.8038 | 0 |
| S26 | agnes | 122 | 0 | 0 | 1.8091 | 0 |
| S27 | agnes | 92 | 106 | 92 | 0.7371 | 0 |
| S28 | agnes | 129 | 29 | 0 | 2.0831 | 0 |
| S29 | agnes | 56 | 0 | 0 | 0.9101 | 0 |
| S30 | agnes | 128 | 0 | 0 | 0.7267 | 0 |
| S31 | agnes | 176 | 89 | 0 | 2.269 | 0 |
| S32 | agnes | 103 | 70 | 206 | 0.3575 | 0 |
| S33 | agnes | 78 | 0 | 0 | 0.7501 | 0 |
| S34 | agnes | 156 | 0 | 0 | 1.002 | 0 |
| S35 | agnes | 168 | 48 | 12 | 0.3238 | 0 |
| S36 | graphic | 35 | 0 | 0 | 148.3282 | 0 |
| S37 | agnes | 148 | 0 | 0 | 1.4828 | 0 |
| S38 | agnes | 202 | 0 | 165 | 2.0459 | 0 |
| S39 | agnes | 136 | 9 | 0 | 1.9448 | 0 |
| S40 | agnes | 160 | 0 | 160 | 3.4806 | 1 |
| S41 | graphic | 195 | 45 | 0 | 200.0972 | 0 |
| S42 | agnes | 116 | 0 | 0 | 0.6215 | 0 |
| S43 | graphic | 136 | 7 | 0 | 186.6884 | 0 |
| S44 | agnes | 122 | 0 | 0 | 2.2431 | 0 |
| S45 | agnes | 261 | 0 | 0 | 1.072 | 1 |
| END | graphic | 114 | 0 | 0 | 0.6018 | 1 |

## 复核文件

- 全 45 镜 + 片尾画面中帧：`work/raincoat2004/final-frame-audit/contacts/shot-midpoints.jpg`
- 逐帧指标 CSV：`work/raincoat2004/final-frame-audit/frame-metrics.csv`
- 候选异常原始分辨率帧：`['work/raincoat2004/final-frame-audit/suspect-frames/frame_00000_t000.000.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00001_t000.033.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00002_t000.067.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00003_t000.100.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00004_t000.133.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00005_t000.167.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00006_t000.200.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00007_t000.233.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00008_t000.267.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00009_t000.300.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00010_t000.333.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00340_t011.333.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00341_t011.367.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00342_t011.400.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00343_t011.433.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00344_t011.467.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00345_t011.500.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00346_t011.533.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00347_t011.567.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00348_t011.600.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00349_t011.633.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00350_t011.667.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00351_t011.700.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00352_t011.733.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00353_t011.767.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00354_t011.800.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00355_t011.833.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00356_t011.867.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00357_t011.900.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00358_t011.933.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00359_t011.967.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00360_t012.000.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00361_t012.033.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_00362_t012.067.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01179_t039.300.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01180_t039.333.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01181_t039.367.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01182_t039.400.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01183_t039.433.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01184_t039.467.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_01185_t039.500.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04297_t143.233.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04298_t143.267.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04299_t143.300.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04300_t143.333.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04301_t143.367.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04302_t143.400.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04303_t143.433.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_04304_t143.467.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05280_t176.000.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05281_t176.033.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05282_t176.067.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05283_t176.100.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05284_t176.133.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05285_t176.167.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05286_t176.200.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05287_t176.233.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05288_t176.267.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05289_t176.300.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05290_t176.333.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05291_t176.367.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05292_t176.400.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05293_t176.433.jpg', 'work/raincoat2004/final-frame-audit/suspect-frames/frame_05294_t176.467.jpg']`
- 手部动态接触表：`work/raincoat2004/final-frame-audit/contacts/hands-S06.jpg`
- 手部动态接触表：`work/raincoat2004/final-frame-audit/contacts/hands-S13.jpg`
- 手部动态接触表：`work/raincoat2004/final-frame-audit/contacts/hands-S27.jpg`
- 手部动态接触表：`work/raincoat2004/final-frame-audit/contacts/hands-S32.jpg`
- 手部动态接触表：`work/raincoat2004/final-frame-audit/contacts/hands-S38.jpg`
- 手部动态接触表：`work/raincoat2004/final-frame-audit/contacts/hands-S40.jpg`

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
