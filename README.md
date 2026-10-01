# 挪威七月二十二日｜180 秒 AI 情景重现

当前制作分支：`arena/01a0f777-monalisa-film`。

- 文案与镜头：[docs/分镜文案.md](docs/分镜文案.md)
- 核查来源与 QC / QA 门槛：[docs/制作与核查.md](docs/制作与核查.md)
- 从旧制作分支找回的原手册：[docs/ORIGINAL_HANDBOOK.md](docs/ORIGINAL_HANDBOOK.md)
- Agnes 分镜输入：[storyboard.json](storyboard.json)

## 当前流水线：先出齐 15 段，再校验

上次运行 36865885084 已失败。本轮从其 artifact 恢复状态，先串行下载 15 段原片，全部到齐后批量机器 QC，仅重做不合格片段。每段成功即上传 `raw-clip-XX`，更方便实时看进度。人工畸变、配音、字幕和同步审核尚未完成。

本轮根据用户“继续生成”授权，耗尽的旧批次保存在 `prior_batches` 后开启新一批最多 50 次；其余状态继续恢复。明确 HTTP 401/403 拒绝会停止，不反复重试无效权限。失败和片间均等待 75 秒；不并发创建任务。

push 更新 `RUN_AGNES` 可触发当前分支工作流。当前重启固定恢复上次运行 36865885084；下一次恢复必须通过 `resume_run` 选择最新运行，或修改工作流中的恢复 ID 后再 push。不要从旧状态重复启动。

Workflow: https://github.com/ozzy282576/monalisa-film/actions/workflows/agnes-film.yml

仅使用当前分支 `arena/01a0f777-monalisa-film`，密钥仍由 runner 的 AGNES_API_KEY Secret 注入，无须导出。手动 Actions 调度接口曾返回 403；push 触发已在上一轮验证可用。同一时间只运行一个任务。

## 后续

拿到原片后逐镜完整观看与抽帧审核，修正不合格镜头；按实际画面定稿、中文同一男声配音、句级字幕及 12 秒精确对齐，最后才输出 180 秒最终 MP4。未完成项一律保持 pending。

## 本地检查

```sh
python -m unittest discover -s tests -v
python -m py_compile scripts/generate.py scripts/make_story.py
```
