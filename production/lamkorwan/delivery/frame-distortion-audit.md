# 成片逐帧畸变 / 时序 QC

- 成片：`雨夜屠夫林过云_一卷菲林里的四条人命_三分钟_带声音.mp4`
- SHA-256：`b57ad26f7d520bb1d5066daa9a257d9c87651e3f9c0b99b80fa736fae9d20804`
- 视频：1920×1080 / 30.000 fps / 180.000 秒
- 覆盖：解码并分析 **5400/5400 帧**；逐帧 MediaPipe 人脸/手检测；320x180 时序分析
- 自动状态：**REVIEW**（机器结果，不等同于无任何视觉瑕疵）

## 全片结果

- PTS 连续性异常：0
- 亮度低于 12 的帧：14（片头/片尾淡入淡出需按时间线解释）
- 非计划黑帧：1
- >1 秒近静止区段：0；其中非信息卡/片尾段：0
- 帧差/光流/亮度突变待复核窗口：4
- 人脸检测：逐帧总检测 223；达到复核阈值的候选 0
- 手部检测：逐帧总检测 101；超出宽松几何边界的 landmark 事件 12

## 镜头统计

| 镜头 | 类型 | 帧数 | 人脸检出 | 手检出 | 光流残差 P95 峰值 | 时序异常窗口 |
|---|---:|---:|---:|---:|---:|---:|
| S01 | agnes | 109 | 0 | 0 | 0.5443 | 1 |
| S02 | agnes | 61 | 0 | 0 | 1.0691 | 0 |
| S03 | agnes | 127 | 0 | 0 | 1.0319 | 0 |
| S04 | agnes | 109 | 10 | 0 | 0.9369 | 0 |
| S05 | graphic | 70 | 15 | 0 | 224.7675 | 0 |
| S06 | agnes | 100 | 0 | 0 | 1.6317 | 0 |
| S07 | agnes | 74 | 0 | 0 | 1.1708 | 0 |
| S08 | agnes | 170 | 2 | 0 | 0.7293 | 0 |
| S09 | graphic | 104 | 15 | 0 | 170.2119 | 0 |
| S10 | agnes | 120 | 0 | 0 | 0.3569 | 0 |
| S11 | agnes | 92 | 0 | 49 | 1.1678 | 0 |
| S12 | agnes | 122 | 0 | 0 | 0.7066 | 0 |
| S13 | agnes | 98 | 0 | 0 | 0.6477 | 0 |
| S14 | graphic | 109 | 0 | 0 | 194.1752 | 1 |
| S15 | agnes | 147 | 0 | 0 | 5.3445 | 0 |
| S16 | agnes | 120 | 0 | 0 | 0.5167 | 0 |
| S17 | agnes | 67 | 0 | 0 | 1.5597 | 0 |
| S18 | agnes | 107 | 0 | 0 | 1.1632 | 0 |
| S19 | agnes | 102 | 88 | 1 | 0.8744 | 0 |
| S20 | agnes | 67 | 0 | 0 | 0.7285 | 0 |
| S21 | agnes | 118 | 0 | 0 | 1.1185 | 0 |
| S22 | agnes | 70 | 2 | 0 | 0.9448 | 0 |
| S23 | agnes | 154 | 26 | 0 | 4.8953 | 0 |
| S24 | graphic | 121 | 0 | 0 | 209.9179 | 0 |
| S25 | agnes | 113 | 0 | 0 | 2.7978 | 0 |
| S26 | agnes | 99 | 28 | 0 | 0.6046 | 0 |
| S27 | agnes | 157 | 8 | 0 | 5.2252 | 0 |
| S28 | agnes | 83 | 0 | 0 | 0.8162 | 0 |
| S29 | agnes | 113 | 3 | 0 | 0.9709 | 0 |
| S30 | agnes | 197 | 0 | 0 | 1.5745 | 0 |
| S31 | graphic | 127 | 0 | 0 | 173.596 | 0 |
| S32 | agnes | 49 | 0 | 0 | 0.5879 | 0 |
| S33 | agnes | 113 | 0 | 0 | 0.7477 | 0 |
| S34 | agnes | 120 | 0 | 51 | 1.7842 | 0 |
| S35 | agnes | 130 | 0 | 0 | 4.4423 | 0 |
| S36 | agnes | 48 | 0 | 0 | 1.1784 | 0 |
| S37 | agnes | 82 | 0 | 0 | 0.5685 | 0 |
| S38 | agnes | 152 | 0 | 0 | 1.3905 | 0 |
| S39 | agnes | 148 | 0 | 0 | 1.7068 | 0 |
| S40 | agnes | 134 | 0 | 0 | 0.9441 | 0 |
| S41 | agnes | 167 | 0 | 0 | 1.1337 | 0 |
| S42 | graphic | 170 | 16 | 0 | 207.0206 | 0 |
| S43 | agnes | 129 | 0 | 0 | 0.8755 | 0 |
| S44 | graphic | 182 | 10 | 0 | 246.7772 | 0 |
| S45 | agnes | 235 | 0 | 0 | 0.7288 | 1 |
| END | graphic | 114 | 0 | 0 | 0.4499 | 1 |

## 复核文件

- 全 45 镜 + 片尾画面中帧：`work/lamkorwan/final-frame-audit/contacts/shot-midpoints.jpg`
- 逐帧指标 CSV：`work/lamkorwan/final-frame-audit/frame-metrics.csv`
- 候选异常原始分辨率帧：`['work/lamkorwan/final-frame-audit/suspect-frames/frame_00000_t000.000.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00001_t000.033.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00002_t000.067.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00003_t000.100.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00004_t000.133.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00005_t000.167.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00006_t000.200.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00007_t000.233.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00008_t000.267.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00009_t000.300.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_00010_t000.333.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_01455_t048.500.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_01456_t048.533.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_01457_t048.567.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_01458_t048.600.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_01459_t048.633.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03695_t123.167.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03696_t123.200.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03697_t123.233.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03698_t123.267.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03699_t123.300.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03700_t123.333.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03701_t123.367.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03702_t123.400.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03703_t123.433.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03704_t123.467.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03705_t123.500.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03706_t123.533.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03707_t123.567.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03708_t123.600.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03709_t123.633.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_03710_t123.667.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05280_t176.000.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05281_t176.033.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05282_t176.067.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05283_t176.100.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05284_t176.133.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05285_t176.167.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05286_t176.200.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05287_t176.233.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05288_t176.267.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05289_t176.300.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05290_t176.333.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05291_t176.367.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05292_t176.400.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05293_t176.433.jpg', 'work/lamkorwan/final-frame-audit/suspect-frames/frame_05294_t176.467.jpg']`
- 手部动态接触表：`work/lamkorwan/final-frame-audit/contacts/hands-S11.jpg`
- 手部动态接触表：`work/lamkorwan/final-frame-audit/contacts/hands-S34.jpg`

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
