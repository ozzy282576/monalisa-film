# 挪威七月二十二日｜180 秒 AI 情景重现

当前制作分支：`arena/01a0f777-monalisa-film`。

- 文案与镜头：[docs/分镜文案.md](docs/分镜文案.md)
- 核查来源与 QC / QA 门槛：[docs/制作与核查.md](docs/制作与核查.md)
- 从旧制作分支找回的原手册：[docs/ORIGINAL_HANDBOOK.md](docs/ORIGINAL_HANDBOOK.md)
- Agnes 分镜输入：[storyboard.json](storyboard.json)

## 当前流水线：补生成缺失段与第 15 段

补生成队列 **01 → 07 → 11 → 12 → 13 → 15**，严格串行。新工作流与原流程共享 `agnes-film` concurrency group，不取消原任务，等待运行 36952484656 完成后从其最终 `raw-clips` 恢复。

只为缺失且耗尽额度的片段开启一次新 50 次额度；旧记录保留于 `prior_batches`。本轮批次 ID `missing-20261002-01`，恢复同一状态不会重复清零。失败后等 75 秒，50 次仍失败则继续下一段。成功文件不重做，第 15 段若已成功会自动跳过；有任务 ID 时只轮询原任务，不重复创建。

每段上传累计 `checkpoint-XX`。全部 15 段到齐才开始统一机器 QC 和选择性重做；缺失或人工审核未通过均不宣称成片完成。单 job 上限 350 分钟，超时需从最新 checkpoint 恢复。

触发文件 `RUN_AGNES`，当前入口恢复运行 36952484656。之后如需再补生成，必须改为最新运行及 artifact，且采用明确授权的新批次，不能重复从旧状态启动。

Workflow: https://github.com/ozzy282576/monalisa-film/actions/workflows/agnes-film.yml

密钥仅由 runner Secret 使用。分支固定 `arena/01a0f777-monalisa-film`。

## 后续

拿到原片后逐镜完整观看与抽帧审核，修正不合格镜头；按实际画面定稿、中文同一男声配音、句级字幕及 12 秒精确对齐，最后才输出 180 秒最终 MP4。未完成项一律保持 pending。

## 本地检查

```sh
python -m unittest discover -s tests -v
python -m py_compile scripts/generate.py scripts/make_story.py
```
