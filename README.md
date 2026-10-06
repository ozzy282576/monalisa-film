# 蒙娜丽莎的雨夜 / MONA LISA IN THE RAIN

> 林过云抖音动画项目 - 基于挪威722事件工作流
> 15片段 x 12秒 = 3分钟 | 每片段200次重试 | 串行执行 | 严格QC QA | 无瑕疵成片

## 项目简介

本项目不是《羔羊医生》式的剥削片，而是从女性视角重述1982年香港雨夜屠夫案的艺术动画短片，适配抖音9:16竖屏。

**核心**：动画视频非图片轮播，通过访问 Agnes 生成12秒视频片段，串行15个片段，拼接3分钟成片，生成后仔细畸变检查、QC QA校验，最终出无瑕疵成片。

**伦理**：尊重受害者陈凤兰、陈云洁、梁秀云、梁惠心，无血腥、无裸露、无分尸，风格化动画，纪念性质。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
# ffmpeg通过imageio-ffmpeg自动安装
```

### 2. 配置Agnes

```bash
# 真实API模式 (需要key)
export AGNES_API_KEY="your_agnes_api_key"
# 修改 config/agnes_config.json -> mock_mode: false

# Mock模式 (本地动画生成，用于测试QC流程)
# 默认即为Mock模式，无需key，直接运行
```

### 3. 运行完整流水线 (15片段串行，每片段200次重试)

```bash
python scripts/run_pipeline.py --mock
# 或指定片段测试
python scripts/run_pipeline.py --start 1 --end 3 --mock
```

### 4. 查看结果

```bash
output/final/monalisa_lam_3min_douyin_final.mp4  # 最终成片
output/final/final_qc_report.txt                 # QC报告
output/final/PIPELINE_REPORT.md                  # 流水线报告
output/qc_reports/                               # 每片段QC详情
output/clips/                                    # 所有尝试的片段
```

---

## 架构

基于挪威722事件验证的流程：

```
config/
  agnes_config.json      # Agnes配置，15片段，200重试，串行
  scenes.json            # 15片段剧本，12秒每段
  qc_thresholds.json     # QC阈值

src/
  agnes_client/
    client.py            # Agnes客户端，支持真实API+Mock动画生成
    models.py            # 数据模型
  qc/
    distortion.py        # 畸变检查 - 光流异常、模糊、图片轮播检测
    flicker.py           # 闪烁检查
    continuity.py        # 连续性SSIM
    nsfw.py              # 血腥裸露合规
    qa_report.py         # 综合QA
  scenes/
    norway_722_reference.py  # 挪威722工作流参考
    lin_guoyun_scenes.py     # 林过云15场景
  pipeline/
    generator.py         # 单片段200次重试生成器
    stitcher.py          # 15片段拼接3分钟
    orchestrator.py      # 主流水线串行15片段

scripts/
  run_pipeline.py        # 一键运行
  test_agnes.py          # 单片段测试
  generate_douyin_final.py # 抖音元数据

docs/                    # 电影企划文档
  00_项目概述.md
  01_案件研究_林过云.md
  ...
```

---

## 15片段分镜 (3分钟)

| Clip | 标题 | 旁白 | 动画要点 |
|------|------|------|----------|
| 01 | 雨夜香港1982 | 1982年，香港，雨季。 | 霓虹，湿街，雨 |
| 02 | 夜班出租车 | 一辆夜班出租车，亮着空车牌。 | 仪表盘，雨刷 |
| 03 | 阿兰 | 阿兰，22岁，今晚想早点回家。 | 电话亭，蒙娜丽莎微笑 |
| 04 | 暗房红光 | 照片必须经由别人的手，才能被看见。 | 显影液，红光 |
| 05 | 城门河报纸 | 城门河发现了东西，但没人在意。 | 报纸，雨窗 |
| 06 | 阿洁 | 阿洁，31岁，包里总有一个菠萝包。 | 便利店，菠萝包 |
| 07 | 女法医地图 | 雨夜、出租车、夜归女性，连成了一张网。 | 地图，红线 |
| 08 | 阿云 | 阿云，29岁，刚拿到驾照。 | 驾照，天台 |
| 09 | 后视镜凝视 | 后视镜是一个取景器。 | 后视镜，凝视 |
| 10 | 阿心 | 阿心，17岁，想拍下所有美好的东西。 | 相机，青春 |
| 11 | 冲印店发现 | 那卷菲林，颜色不对。 | 震惊，手抖 |
| 12 | 雨停逮捕 | 1982年8月18日，雨停了。 | 安静逮捕 |
| 13 | 四幅蒙娜丽莎 | 她们不是标本，她们是人。 | 黏土重建 |
| 14 | 空车开走 | 那辆车开走了，但雨还在下。 | 空车，尾灯 |
| 15 | 尾声 | 谨以此片纪念想回家的女性。 | 名字，黑屏雨 |

---

## QC QA 流程 (无瑕疵成片)

每个片段生成后立即进行5项检查，200次重试直到通过：

1. **畸变检查** (`distortion.py`)
   - 光流异常比 < 0.15
   - 清晰度 > 50
   - 检测图片轮播 (frame_diff < 1.0)
   - 肢体畸变

2. **闪烁检查** (`flicker.py`)
   - 亮度方差 < 30
   - 闪烁频率 < 0.1

3. **连续性** (`continuity.py`)
   - SSIM > 0.85
   - 场景跳变 <=1

4. **NSFW合规** (`nsfw.py`)
   - 红色像素 (血腥) < 0.25
   - 肤色像素 (裸露) < 0.5
   - 禁止电锯、尸体等

5. **抖音合规**
   - 1080x1920 9:16
   - 24fps
   - 11.5-12.5秒

综合分数 >=0.85 且全部通过才算成功。200次后取最佳。

---

## 挪威722事件工作流复用

本项目复用挪威722抖音项目的成功经验：

- 串行15片段避免Agnes API限流 (5并发限制)
- 200次重试：前50次粗生成，后150次精调seed+prompt
- 光流检测畸变优于姿态估计
- 2帧交叉淡化拼接
- 立即QC不积压

详见 `src/scenes/norway_722_reference.py`

---

## 抖音发布

```bash
python scripts/generate_douyin_final.py
```

标题：`蒙娜丽莎的雨夜 | 1982年香港雨夜，四个想回家的女孩`

标签：`#林过云 #雨夜屠夫 #香港奇案 #女性安全 #蒙娜丽莎的雨夜`

封面：雨夜出租车+四位女性剪影

---

## 开发

```bash
# 测试单片段
python scripts/test_agnes.py

# 测试QC
python -m src.qc.qa_report

# 查看分镜
python -m src.scenes.lin_guoyun_scenes
```

---

## 许可证与伦理

- 本项目仅用于纪念与安全教育，禁止用于血腥猎奇传播
- 所有女性角色为风格化动画，尊重不色情
- 片尾设纪念基金意向，捐夜班女性安全NGO

For Fung-lan, Wan-kit, Sau-wan, Wai-sum.

---

*基于 arena/7d72cae2-monalisa-film 分支 | 2026-10-06*
