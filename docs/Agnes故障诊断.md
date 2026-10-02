# Agnes 生成失败：已确认队列已满

诊断运行：https://github.com/ozzy282576/monalisa-film/actions/runs/36952148317

通过 GitHub runner 成功恢复上一轮 raw-clips 中的 state.json，并用 Check Run annotations 返回诊断结果，绕过本地无法下载 GitHub 日志/产物的问题。密钥未导出。

## 保存状态（确证）

片段 01：
- 当前批次 tries=50，status=create_rejected，http_code=503。
- prior_batches 中另有一个 tries=50，status=create_rejected，http_code=503 的旧批次。
- 没有 video_id；任务未被接纳，因此没有视频进入生成、下载或 QC。
- 历史累计 100 次创建尝试均未得到可用任务；每一批次终态错误码为 503。状态不是完整逐次日志，不能据此断言每一次错误码都相同。

## 单次受控复测

在确认没有进行中任务后，仅发送一次同参数创建请求，无循环重试。

HTTP 503，服务端错误：

> video queue is full, please retry later

诊断记录在 diagnostic-state artifact，status=create_rejected，没有创建成功的视频任务。历史两批次共 100 次创建尝试，加本次复测共 101 次；这不是 101 个生成任务。

## 结论与边界

当前可复现的阻塞原因是 Agnes 视频队列已满，而非画面 QC、字幕或配音。已有状态证明两批次均在第 01 段提交阶段耗尽额度。无法从该响应进一步判断是平台总队列、账户配额队列还是该模型队列，也无法推断何时恢复。

本地读取 GitHub 产物时的 EOF 是另一个下载连接问题，不是 Agnes 生成失败原因。GitHub runner 能读取 artifact 和调用服务。

本次没有重新启动整批生成。用户配置仍是每段每批最多 50 次、明确失败后间隔 75 秒；若要改变排队策略，需明确修改该配置。增加并发会违背用户要求，也不能解决满队列问题。
