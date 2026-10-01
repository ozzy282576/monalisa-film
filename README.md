# 挪威七月二十二日｜180 秒 AI 情景重现

当前制作分支：`arena/01a0f777-monalisa-film`。

- 文案与镜头：[docs/分镜文案.md](docs/分镜文案.md)
- 核查来源与 QC / QA 门槛：[docs/制作与核查.md](docs/制作与核查.md)
- 从旧制作分支找回的原手册：[docs/ORIGINAL_HANDBOOK.md](docs/ORIGINAL_HANDBOOK.md)
- Agnes 分镜输入：[storyboard.json](storyboard.json)

## 状态

已完成脚本重写、来源核查和串行任务调度代码。**尚无本片生成视频；没有做完畸变、配音、字幕、音画同步验收。**

2026-10-01：手动 workflow_dispatch 与读取 Secret 列表返回 HTTP 403，但本分支 push 已成功自动触发工作流，当前正在生成步骤。运行链接：https://github.com/ozzy282576/monalisa-film/actions/runs/36865885084 。不要重复启动；不需要导出、粘贴或重建现有 API Key。

## 启动

首次运行已经启动。只有原运行结束且确需恢复时，才在 Arena 重新连接 GitHub 以允许 Actions 操作，或者在 GitHub Actions 中手动运行已存在的 `agnes-film.yml`，**必须选择本分支** `arena/01a0f777-monalisa-film`（列表中可能仍显示旧工作流名称）。只启动一个运行。

现有仓库 Secret `AGNES_API_KEY` 由 runner 读取；不将密钥发送给代理。原分支和 main 均不修改。

Workflow: https://github.com/ozzy282576/monalisa-film/actions/workflows/agnes-film.yml

成功后在该次运行下载 `raw-clips` artifact：包含 15 个原片、逐镜机器 QC、六个时点的抽帧、可恢复任务状态。**该 artifact 不是最终有声成片。**

若运行超时或失败，从同一工作流 `resume_run` 填入原运行 ID，恢复 artifact 后继续；不要空状态反复运行。提交状态不明时需核对服务端任务，不能重发 POST。

## 后续

拿到原片后逐镜完整观看与抽帧审核，修正不合格镜头；按实际画面定稿、中文同一男声配音、句级字幕及 12 秒精确对齐，最后才输出 180 秒最终 MP4。未完成项一律保持 pending。

## 本地检查

```sh
python -m unittest discover -s tests -v
python -m py_compile scripts/generate.py scripts/make_story.py
```
