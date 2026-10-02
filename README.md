# 挪威七月二十二日｜180 秒 AI 情景重现

当前制作分支：`arena/01a0f777-monalisa-film`。

- 文案与镜头：[docs/分镜文案.md](docs/分镜文案.md)
- 核查来源与 QC / QA 门槛：[docs/制作与核查.md](docs/制作与核查.md)
- 从旧制作分支找回的原手册：[docs/ORIGINAL_HANDBOOK.md](docs/ORIGINAL_HANDBOOK.md)
- Agnes 分镜输入：[storyboard.json](storyboard.json)

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
