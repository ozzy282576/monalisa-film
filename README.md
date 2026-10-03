# 挪威七月二十二日｜180 秒 AI 情景重现

当前制作分支：`arena/01a10095-monalisa-film`（接续自 `arena/01a0f777-monalisa-film`）。

- 文案与镜头：[docs/分镜文案.md](docs/分镜文案.md)
- 核查来源与 QC / QA 门槛：[docs/制作与核查.md](docs/制作与核查.md)
- 从旧制作分支找回的原手册：[docs/ORIGINAL_HANDBOOK.md](docs/ORIGINAL_HANDBOOK.md)
- Agnes 分镜输入：[storyboard.json](storyboard.json)

## 当前画面质检（2026-10-03）

15 段原片已齐。已从 runner 取回 30 张检查图，逐张审看每段 24 个采样点，共 360 张画面；机器报告已核验，但不能据此声称逐帧无瑕疵。

- 退回重做：**01、07、10、11、12、13**（异常人形/镜头方向/伪文字/错误旗徽/光照闪变/穿栏杆嫌疑）。
- 其余 9 段：仅保留候选，细节或连续动作检查未完成；**最终视觉放行 0 段**。
- 原片都是 12.25 秒，尚需精确归一到每段 12 秒；无最终有声成片。
- [逐段质检报告](review/逐段质检报告.md) / [机器可读记录](review/findings.json) / [原片抽帧](review/evidence/) / [针对性重做提示词](review/repair-plan.json)。
- 视觉修复用独立 RUN_VISUAL_REPAIR 触发；每段先备份原片和原状态，再生成候选。新版本最多 200 次创建、失败等 75 秒，严格串行。候选下载后还必须复核，不能自动视觉放行。

## 替换候选人工复核（2026-10-03，本轮新增）

已对 visual-repair-v1 的六段替换候选逐张复核（每段 24 个标注采样），记录在 [replacement-review-v1.json](review/replacement-review-v1.json) / [替换候选复核.md](review/替换候选复核.md)：

- **通过 5 段：01、10、11、12、13**（原缺陷均已消除，仅记轻微偏差）。
- **退回 1 段：07**——夹克带 THE NORTH FACE 商标、船体伪文字 GOCSNANL、渡轮挂蓝旗、人脸过清。已写 [repair-plan-v2.json](review/repair-plan-v2.json)。
- 放行清单见 [review/approval.json](review/approval.json)；保留的 9 段与 07 v2 仍 pending。

归一化/拼接工具（制作规范 §5）已落地并用真实 ffmpeg 验证：`scripts/normalize_assemble.py` 将每段精确归一到 12.000s/25fps/300 帧，15 段拼成 180.000s/4500 帧；**未集齐 15 段放行时拼接被硬门禁阻断**（见 tests/test_normalize.py）。

07 v2 重做工作流：`.github/workflows/visual-repair-v2.yml`（4 串行窗口、上限 200、证据页回提交），由本分支 `RUN_VISUAL_REPAIR_V2` 触发；本轮未创建该触发文件，故不会误启动。

## 当前流水线：剩余四段自动接续至 200 次

剩余队列 **11 → 12 → 13 → 15**，当前批次每段累计最多 **200 次创建请求**。不是每天清零重试，也不是在已用 50 次之外额外加 200 次。旧历史保留。

新运行等待 36999794025 结束，恢复最终 raw-clips；已有视频自动跳过，不取消正在生成的任务。每次明确失败后仍等 75 秒。每段拆成 4 个最多新增 50 次请求的串行窗口，依靠 checkpoint artifact 自动交接，全部严格串行。成功后保留视频，不必请求满额度。

正常重试与交接不需要用户逐次催。队列持续满时耗尽 200 次就继续下一段；不无限续批。认证失败、提交结果不明或 runner 超时等异常仍会安全停止，不能保证一定生成成功。

到齐 15 段后自动机器 QC；人工畸变审核和配音字幕同步仍另行验收。最后输出 raw-clips，中间 checkpoint-XX-window-N 均保留累计原片与状态。

本次恢复源固定为 36999794025。将来恢复必须选最新 checkpoint，禁止从旧状态重复请求。密钥只由 GitHub runner Secret 使用。

Workflow: https://github.com/ozzy282576/monalisa-film/actions/workflows/agnes-film.yml

## 后续

拿到原片后逐镜完整观看与抽帧审核，修正不合格镜头；按实际画面定稿、中文同一男声配音、句级字幕及 12 秒精确对齐，最后才输出 180 秒最终 MP4。未完成项一律保持 pending。

## 本地检查

```sh
python -m unittest discover -s tests -v
python -m py_compile scripts/generate.py scripts/make_story.py
```
