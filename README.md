# 挪威七月二十二日｜180 秒 AI 情景重现

当前制作分支：`arena/01a0f777-monalisa-film`。

- 文案与镜头：[docs/分镜文案.md](docs/分镜文案.md)
- 核查来源与 QC / QA 门槛：[docs/制作与核查.md](docs/制作与核查.md)
- 从旧制作分支找回的原手册：[docs/ORIGINAL_HANDBOOK.md](docs/ORIGINAL_HANDBOOK.md)
- Agnes 分镜输入：[storyboard.json](storyboard.json)

## 当前流水线：每段 50 次，耗尽则继续下一段

用户最新要求：第 01 段耗尽 50 次仍失败则继续第 02 段，以此类推至第 15 段。每次明确失败后等 75 秒，保持串行，已有视频保留。当前从运行 36876593240 恢复，第 01 段额度已用完，实际继续第 02 段。

每段独立 Actions job，用 needs 连接，绝不并发；每段结束上传 `checkpoint-XX`（状态与累计原片）。全链结束才判断是否到齐 15 段，到齐才批量 QC 和选择性重做。缺失片段保持未完成，不能把工作流成功误称视频成功。401/403 或提交结果不明仍停止整个链。

本轮不会清零旧批次或循环开启新 50 次。单个 job 最长 350 分钟，遇到超时需从最新 checkpoint 恢复。流水线正常轮转最多需要十几小时，仅等待时间就约 15.6 小时（从全新 15 段全部耗尽计算）。

触发文件 `RUN_AGNES`；当前入口固定恢复旧运行 36876593240。后续恢复必须改成最新 checkpoint 所属运行与 artifact 名称，不要从旧状态反复启动。

Workflow: https://github.com/ozzy282576/monalisa-film/actions/workflows/agnes-film.yml

密钥只由 runner Secret 注入。当前分支固定 `arena/01a0f777-monalisa-film`。

## 后续

拿到原片后逐镜完整观看与抽帧审核，修正不合格镜头；按实际画面定稿、中文同一男声配音、句级字幕及 12 秒精确对齐，最后才输出 180 秒最终 MP4。未完成项一律保持 pending。

## 本地检查

```sh
python -m unittest discover -s tests -v
python -m py_compile scripts/generate.py scripts/make_story.py
```
