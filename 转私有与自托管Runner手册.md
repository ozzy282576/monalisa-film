# 转到私有仓库 + 自托管 Runner 手册

**这份手册解决两件事**：① 让仓库里的东西不再被外人看到；② 转私有之后渲染还能跑，
而且不再受 2000 分钟/月的限制。

一句话结论：**内容要藏 → 必须转私有；转私有还要不限量跑渲染 → 自托管 runner。**
这两件事必须按顺序做，顺序反了会有一段时间把你自己的电脑暴露出去（见第 0 节）。

---

## 0. 先纠正两个常见误解

### 误解一："把东西放到分支，别人就看不到了"

不成立。公开仓库里**所有分支、所有提交、所有 Actions 日志**对全世界可见。
实测（无任何登录凭证）：

| 操作 | 结果 |
|---|---|
| `GET /repos/32r4e2q-hub/desktop-tutorial/branches` | 返回全部 30+ 个 `arena/...` 分支名 |
| 下载某个非默认分支的 tar.gz | HTTP 200，整包下载成功 |
| 打开 `/actions` 页面 | 匿名可见 |

默认分支只是"仓库首页默认展示哪一支"，不是权限。分支下拉框就在首页右上角。

### 误解二："转私有 + 无限跑 Actions"

也不成立。免费账号的额度是这样的：

| 仓库可见性 | runner | 计费 |
|---|---|---|
| 公开 | GitHub-hosted | **免费、不计分钟** |
| 私有 | GitHub-hosted | **2000 分钟/月**，用完就停 |
| 私有 | **自托管** | **不计分钟**（目前） |

出片一次 6~90 分钟，2000 分钟大约只够 20 次左右出片。所以要么公开换额度，要么把
机器换成你自己的——**自托管 runner 是目前唯一"内容藏起来 + 渲染不限量"的组合**。

> 关于自托管计费的一个诚实说明：GitHub 曾在 2025-12 宣布 2026-03-01 起对私有仓库的
> 自托管用量收 $0.002/分钟（理由是"编排层成本"），社区反弹后**已推迟、至今未生效**，
> 官方现行文档仍写明 self-hosted runners 免费。这件事随时可能变，所以下面第 4 节教你
> 怎么核对。真收起来也就是"自托管 ≈ 现在的 2000 分钟额度"，不会更糟。

---

## ⚠️ 顺序不能换：先转私有，再装 runner

> **当前进度（2026-09-20 核对）**：`gh api repos/32r4e2q-hub/desktop-tutorial` 返回
> `"private": true` —— **① 已经完成**，现在可以安全地装 runner 了。
> 第 1 节保留着，是为了将来要把仓库改回公开时知道怎么反向操作。

GitHub 官方安全文档明确警告：**自托管 runner 几乎不应该用于公开仓库**——
任何人都能 fork 仓库、提一个 PR，让工作流在你自己的电脑上执行任意代码
（本仓库的 `.github/workflows/ci-tests.yml` 正好是 `on: pull_request` 触发）。

所以：

```
① 转私有 ✅已完成  →  ② 装自托管 runner  →  ③ 设置 RUNNER_LABEL 变量  →  ④ 跑一次出片验证
```

顺序反了（先装 runner 后转私有），中间那段时间你的电脑对任何 fork PR 敞开。

### 🚀 最短路径（第 2、3 节的一键版）

234 行手册里真正要动手的只有下面几句——都写在 `runner/setup-runner.sh` 里了。
**在你的 Linux / WSL2 机器上**（Windows 原生跑不了，见 2A.1）：

```bash
cd desktop-tutorial
bash runner/setup-runner.sh                # 装依赖 → 下 runner → 预下模型 → 注册 → 装服务
bash runner/selfcheck.sh                   # 只读自检：确认真的可以出片了
```

要连开关一起拨（gh 已登录且是仓库 admin）：`bash runner/setup-runner.sh --set-switch`。
细节、选项、回滚见 [`runner/README.md`](runner/README.md)——本手册下面各节是**原理与手工步骤**，
脚本干的就是这些事，出问题时照着某一节自己走一遍即可。

> ⚠️ **注册这一步只能你自己做**：代理（GitHub App）对仓库没有 `administration` 权限，
> 实测 `POST /repos/…/actions/runners/registration-token` 返回 403，
> 写仓库变量同样是 403。所以**取 token、注册、设变量这三件事必须由你（仓库主）完成**，
> 脚本在你自己的机器上替你跑这些命令。这同时意味着你不必把 token 交给任何人。

---

## 1. 转私有（网页操作，约 2 分钟）

> 这一步 **2026-09-20 已确认完成**（仓库现为 private）。留着这一节是将来要改回公开时的反向说明。

1. 打开 <https://github.com/32r4e2q-hub/desktop-tutorial/settings>
2. 拉到页面**最底部**的 **Danger Zone**
3. **Change repository visibility** → **Make private** → 按提示输入仓库全名确认

转完立刻发生的变化：

- 首页、分支、提交历史、Issues、PR、**Actions 日志**都只对有权限的人可见；
- **Actions 会因为没有额度而停摆**——这是预期内的，第 3 步装好 runner 就恢复；
- 你的 Arena 代理（GitHub App）不受影响，仍然是同一个仓库、同一套权限。

**关于"已经露过"的部分**：公开期间别人下载走的副本收不回来，GH Archive 也永久记录了
"这个仓库曾经公开"这件事。转私有能阻止的是**以后**的访问，不是过去。所以：

- 仓库里有过真密钥的话，**先作废重发**，别指望转私有兜底（本仓库实测没扫到硬编码密钥，
  `AGNES_API_KEY` / `PIXAZO_API_KEY` 都走的 Secrets，做法是对的）；
- 目前 `forks: 0`、`stars: 0`，说明还没有人 fork 过——现在是收手成本最低的时候。

---

## 2A. 阶段一：**现在（仓库还公开）就能做**的准备 —— 安全，无任何风险

这一段可以立刻做，不影响正在跑的出片，也不碰仓库设置。装完软件、备好依赖，
转私有之后只需要 2 分钟注册。

### 2A.1 系统必须是 Linux（或 Windows 里的 WSL2）

这条不是偏好，是这套流水线的硬性要求：

- `production/dahlia/media.py` 会直接调 `sudo apt-get install fonts-noto-cjk`；
- `production/dahlia/render.py` 只认 `/usr/share/fonts/opentype/noto/...` 这些路径下的中文字体，
  找不到就直接拒绝渲染（`refusing to render missing glyphs`）；
- 出片脚本是 `bash production/run_project.sh`。

**Windows 原生（PowerShell）跑不通**，请用 **WSL2 里的 Ubuntu**（推荐）或一台 Linux 机器。
macOS 能改，但字体路径要你自己调，性价比低。

### 2A.2 装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip ffmpeg fonts-noto-cjk curl
ffmpeg -version | head -1                 # 有输出就行
fc-list | grep -i "Noto.*CJK" | head -3   # 能看到中文字体就行
```

### 2A.3 把 whisper 模型先下好（**这一步最关键**）

出片与听检都要转写，模型从 Hugging Face 下载。默认情况下模型落在**每次运行的 work 目录**里，
等于每个 job 重下几百 MB——在你家的网络上，这一步最容易把出片卡死。

所以把它指向一个常驻目录，只下一次：

```bash
mkdir -p ~/.cache/whisper
# 国内网络直连不上 Hugging Face 就加镜像：
export HF_ENDPOINT=https://hf-mirror.com
export WHISPER_CACHE_DIR=~/.cache/whisper

python3 -m pip install --user "faster-whisper>=1.1,<2"
python3 - <<'PY'
import os
from faster_whisper import WhisperModel
for size in ("base", "small"):          # base 用于对轨，small 用于逐字听检
    print("下载", size)
    WhisperModel(size, device="cpu", compute_type="int8",
                 download_root=os.environ["WHISPER_CACHE_DIR"])
print("好了：", os.environ["WHISPER_CACHE_DIR"])
PY
```

跑完 `~/.cache/whisper` 里应该有模型文件（small 约 500 MB）。之后每次出片直接复用。

### 2A.0 想省事就跑脚本

上面 2A.1~2A.4 四段（系统要求、装依赖、预下模型、下安装包）已经全部写进
`bash runner/setup-runner.sh --no-register`（只装软件、不注册）。
手动做也行，照着下面走一遍大概 20 分钟，其中下模型最久。

### 2A.4 先把 runner 安装包放在手边（**先别注册**）

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o runner.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-linux-x64-2.337.0.tar.gz
echo "70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613  runner.tar.gz" | sha256sum -c -
tar xzf runner.tar.gz
```

> 版本号是 2026-08-26 发布的 v2.337.0。之后可能更新；以
> <https://github.com/32r4e2q-hub/desktop-tutorial/settings/actions/runners/new>
> 页面上给出的命令为准（那个页面同时给出华氏校验和）。

### ⚠️ 这里就是分界线

**注册（`./config.sh`）必须等到仓库转成私有之后再做。** 原因见前面那一节：
自托管 runner 挂在公开仓库上，任何 fork 的 PR 都能在你机器上执行任意代码，
而本仓库的 `ci-tests.yml` 正好是 `on: pull_request` 触发的。
软件先装好没关系，**别把 token 填进 `config.sh`**。

---

## 2B. 阶段二：**转私有之后**再注册（约 2 分钟）

> 仓库已经是私有的了，所以这一段现在就能做。**推荐直接跑**
> `bash runner/setup-runner.sh`（gh 没登录/不是 admin 时它会给你页面地址，
> 让你自己复制 token 后不回显粘贴）。下面是手工版，脚本做的正是这几步。

1. 打开 <https://github.com/32r4e2q-hub/desktop-tutorial/settings/actions/runners/new>
2. 选 **Linux / x64**，页面上会生成一段**带一次性 token 的命令**——直接照抄那一段
   （不要抄别人文章里的版本号，也**不要把 token 发给任何人**，包括不要发进任何聊天框）
3. 在 2A.4 那个目录里执行 `./config.sh --url ... --token ...`，一路回车即可
4. 别只跑 `./run.sh`，装成系统服务，这样重启后自动回来：

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status      # 看到 active (running) 就成了
```

5. 回到 Runners 页面确认它是**绿色 Idle**

---

## 3. 打开开关（网页操作，约 1 分钟）

工作流里的 `runs-on` 已经统一改成：

```yaml
runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
```

- **没设这个变量** → 一切照旧，跑 GitHub 的机器（行为与现在完全一样）；
- **设了这个变量** → 全部 9 个工作流一起切到你自己的机器。

设置位置：<https://github.com/32r4e2q-hub/desktop-tutorial/settings/variables/actions>
→ **New repository variable**

| Name | Value |
|---|---|
| `RUNNER_LABEL` | `self-hosted` |

`self-hosted` 是每个自托管 runner 都有的标签，一个 runner 就够用。
要精确指定某一台，就在注册时给它起个名字（比如 `home-rig`），这里填 `home-rig`。

**再顺手加两个**（都是可选，但强烈建议——国内网络直接决定出片卡不卡）：

| Name | Value | 作用 |
|---|---|---|
| `WHISPER_CACHE_DIR` | `/home/你的用户名/.cache/whisper` | 模型只下一次，之后每个 job 复用（对应 2A.3 预下载的目录） |
| `HF_ENDPOINT` | `https://hf-mirror.com` | 连不上 huggingface.co 时走镜像 |
| `HF_HUB_DISABLE_XET` | `1` | **用镜像时必须设**：HF 新的 Xet 存储会绕过 `HF_ENDPOINT` 直连 `cas-server.xethub.hf.co`，被 401 拒绝（实测报错 `CAS Client Error: ... 401 Unauthorized`），关掉它才走普通下载路径 |

三个变量都**不设也不影响正确性**：不设就是"跑 GitHub 机器、模型每 job 重下、走官方地址"，
行为和切 runner 之前完全一样。

---

## 4. 跑一次验证

Actions → **解说短片出片** → Run workflow → `project` 填 `dahlia`
（**重跑已经交付过的片子要填 `film_name: 黑色大丽花_三分钟_带声音.mp4`**，
留空会在 `交付/` 里多出一个 48 MB 的副本）。

跑起来后确认三件事：

1. 日志里 checkout 的路径像是你自己机器上的目录；
2. 任务在跑的时候，看 GitHub 的 **Billing → Actions** 页面，分钟数**没有增加**；
3. `交付/` 目录里成片照常被 commit 回来。

---

## 5. 常见坑

1. **HF 连不上，ASR / 逐字听检卡住**
   模型要从 `huggingface.co` 下载，国内网络常常连不上。两个变量要**一起**设：

   ```bash
   HF_ENDPOINT=https://hf-mirror.com
   HF_HUB_DISABLE_XET=1
   ```

   只设镜像还不够：HF 新的 Xet 存储会绕过 `HF_ENDPOINT` 直连
   `cas-server.xethub.hf.co`，返回 401。2026-09-18 在本机实测到的报错是
   `RuntimeError: Task error: File reconstruction error: CAS Client Error: ... 401 Unauthorized`。
   两个变量都已透传进 `commentary-render.yml` / `verbatim-check.yml`。

2. **`pip install` 慢到像卡死**
   GitHub 上装依赖走的是国外 PyPI。在本机（runner 那台机器）设一次国内镜像，
   之后**每次出片装的 Python 依赖都会走它**：

   ```bash
   pip3 config --global set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
   ```
   （实测不设的话速度只有 3.9 kB/s，一个 39 MB 的包要下一小时，直接超时失败。）

3. **机器连不上 GitHub 本身**
   给 runner 配代理：在 runner 目录下建 `.env`，写 `HTTPS_PROXY=http://...` / `HTTP_PROXY=http://...`，
   然后 `sudo ./svc.sh stop && sudo ./svc.sh start`。

4. **电脑休眠/关机时点了出片**
   任务会一直排队等着（直到超时）。自托管 runner 的代价就在这里：**机器得是开着的**。

5. **磁盘**
   `work/` 下的中间产物、`work/*/model-cache` 的 whisper 模型（small 约 500 MB）、
   成片 48 MB 都会留在本机，记得偶尔清一下。

6. **私有仓库的 artifact 存储也有额度**（Free 账号 500 MB，与 Packages 共享）
   出片工作流会把成片当 artifact 传一份（现已改为保留 7 天、失败不算失败）。
   2026-09-18 实测：仓库里积了 **3.1 GB** 老 artifact（反复重渲染的成片副本），
   出片跑到最后报 `Failed to CreateArtifact: Artifact storage quota has been hit`。

   处理办法（按顺序）：

   - 跑一次 **Actions → 清理旧 artifact**（本仓库自带的工作流，第一次填
     `days=0`、`keep_newest=1`：每个名字只留最新的一个）；
   - **注意重算延迟**：GitHub 对存储用量的重算是 6~12 小时（有人等到 24~72 小时），
     删完不会立刻恢复上传；
   - 把 Settings → Actions → General 的 **Artifact and log retention** 调成 7 天。
     这个设置**只影响新上传的**，不会清理已有 artifact；
   - 成片本来就 commit 回 `交付/`，artifact 只是顺手的下载入口——所以
     `commentary-render.yml` 里那一步已经 `continue-on-error: true`，
     配额满了也不会让一次成功的渲染显示成失败。

   ⚠️ 删 artifact 前先确认成片有没有别处留存：有些项目的成片**只存在于 artifact 里**
   （炸弹客那条分支就没把成片 commit 进 `交付/`），删了就找不回来了。

7. **别再把这个 runner 挂回公开仓库**
   任何时候想把仓库改回公开，先去 Settings → Actions → Runners 把 runner 删掉。

---

## 6. 一页速查

| 我想…… | 怎么做 |
|---|---|
| **一句话搞定（推荐）** | 在自己的 Linux/WSL2 上 `bash runner/setup-runner.sh`，再 `bash runner/selfcheck.sh` |
| 只装软件、先不注册 | `bash runner/setup-runner.sh --no-register`（2A 的一键版） |
| 卸掉 / 仓库要改回公开 | `bash runner/uninstall-runner.sh`（`--purge` 连目录一起删）——**改公开前必须先卸** |
| 装完想确认能不能出片 | `bash runner/selfcheck.sh`，退出码 0 才行 |
| runner 会半夜自己死 / 任务卡在 "Waiting for a runner" | 没有 systemd 时 `setup-runner.sh` 会自动装看门狗（`~/watchdog.sh` + Windows 计划任务 `runner-watchdog`，5 分钟一轮）；手动催：`~/watchdog.sh` |
| 现在（还公开）就想动起来 | 做 **2A** 那一段：装依赖、预下模型、下好安装包；**注册留到转私有之后**（现已转私有） |
| 内容不再被外人看到 | 转私有（第 1 节）——分支做不到这件事 |
| 转私有后还能出片、还不限量 | 注册自托管 runner（2B）+ 设 `RUNNER_LABEL`（第 3 节） |
| 出片老卡在下模型 | 设 `WHISPER_CACHE_DIR` + 按 2A.3 预下载 |
| 临时不够用，想借 GitHub 的机器 | 把 `RUNNER_LABEL` 变量删掉，全部工作流回到 `ubuntu-latest`（吃 2000 分钟额度） |
| 只想让某几个工作流用自托管 | 别用仓库变量，直接在那个文件的 `runs-on:` 里写 `self-hosted`（会有测试提醒你这么干的目的） |
| ASR 模型下不下来 | 设 `HF_ENDPOINT=https://hf-mirror.com` |
| 核对自托管到底收不收费 | <https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions> 里的 "Free use of GitHub Actions" |

**永远不要**把 runner 的注册 token、PAT、API key 贴进任何聊天框（包括和我对话时）。
registration token 从 GitHub 页面复制、只填进 `./config.sh` 那一行就够了。

---

## 附：这次改了哪些文件

| 文件 | 改动 |
|---|---|
| `.github/workflows/*.yml`（9 个） | `runs-on` 统一改成 `${{ vars.RUNNER_LABEL \|\| 'ubuntu-latest' }}` |
| `production/*.workflow.yml`（3 个模板） | 同上；`commentary-render` 与 `verbatim-check` 增加 `HF_ENDPOINT` / `WHISPER_CACHE_DIR` 透传 |
| `production/verbatim_check.py`、`production/dahlia/align_audio.py` | 模型缓存目录支持 `WHISPER_CACHE_DIR` 覆盖（不设则与以前一致） |
| `production/tests/test_verbatim_check.py` | 新增 `ModelCacheTests` 钉住缓存目录的两种行为 |
| `production/dahlia/*.workflow.yml`、`production/dbcooper/*.workflow.yml`（5 个归档模板） | 同上，避免以后复制出去又写死 |
| `production/tests/test_workflows.py` | 新增 `test_no_workflow_hardcodes_a_github_hosted_runner`：谁再写死 `ubuntu-latest` 就红 |

没设 `RUNNER_LABEL` 之前，这些改动**不改变任何行为**——可以放心先合进 main。

---

## 附二：`runner/` 目录里有什么

| 文件 | 一句话 |
|---|---|
| [`runner/setup-runner.sh`](runner/setup-runner.sh) | 一键安装 + 注册 + 装服务；幂等，可反复跑；**仓库不是私有就拒绝注册** |
| [`runner/selfcheck.sh`](runner/selfcheck.sh) | 只读自检（系统/依赖/字体/服务/模型/磁盘/仓库），**退出码 0** 才算能出片 |
| [`runner/uninstall-runner.sh`](runner/uninstall-runner.sh) | 反注册 + 停服务，可选 `--purge` 删目录 |
| [`runner/watchdog.sh`](runner/watchdog.sh) | 没有 systemd 时的保活：监听器不在就 `setsid nohup ./run.sh` 拉起来；`setup-runner.sh` 会装到 `~/` 并挂成 Windows 计划任务 |
| [`runner/README.md`](runner/README.md) | 三分钟版最短路径（给不想读 200 行手册的时候） |
| `production/tests/test_runner_scripts.py` | 离线守着这三条脚本：语法、变量名一致、**公开仓库不许注册**、token 不许被打印 |
