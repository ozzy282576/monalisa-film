# 本地 runner（自托管出片机）· 三分钟上手

> ### 🪟 用 Windows？先花一分钟做这三步（PowerShell 原生跑不了这套流水线）
>
> 第 1 步：**确认 WSL 里是 Ubuntu**（`wsl` 默认丢出来的可能是 Alpine：官方 runner
> 只发 glibc 构建，出片脚本还写死 `apt` + `fonts-noto-cjk` —— musl 系的 Alpine 跑不通）：
>
> ```powershell
> wsl --install -d Ubuntu    # 从没装过 WSL：先跑这句，按提示重启一次
> wsl -d Ubuntu              # 已装过 WSL 就直接进 Ubuntu，别用裸 wsl（怕默认是别的发行版）
> ```
>
> 第 2 步：**WSL 里装 gh**（仓库是私有的，clone 前必须先有 gh）。下面每一行
> **单独复制、单独回车**——整段一起粘会把换行揉成一团、跑出莫名其妙的错。
> 已经装过 gh 就跳过这几行：
>
> ```bash
> sudo apt-get update -qq
> sudo apt-get install -y -qq curl
> sudo mkdir -p -m 755 /etc/apt/keyrings
> curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
> sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
> echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
> sudo apt-get update -qq
> sudo apt-get install -y -qq gh
> ```
>
> 第 3 步：**登录并 clone**（还是一行一条）：
>
> ```bash
> gh auth login            # 选 GitHub.com → HTTPS → Login with a web browser（输入页面给的 8 位码）
> gh repo clone 32r4e2q-hub/desktop-tutorial
> cd desktop-tutorial
> ```
>
> 然后直接跳到下面「一、在你自己的机器上跑一句」。
> 注意：**仓库要 clone 到 WSL 的 Linux 家目录里**（`cd ~` 再 clone），
> 别放在 `C:\Users\...` 下——`/mnt/c` 的磁盘 IO 慢好几倍，出片会明显变久。
> 后面所有命令都在 WSL 里跑，不再回 PowerShell。

这台文件夹里的东西只为一件事服务：**把出片从 GitHub 的机器上搬到你自己的机器上**。
仓库已经转成私有了，所以不再有 2000 分钟/月的额度焦虑——自托管的分钟数不计费。

完整背景、原理、为什么顺序不能反，见仓库根目录的
[`转私有与自托管Runner手册.md`](../转私有与自托管Runner手册.md)。
**这里只给最短路径。**

---

## 一、在你自己的机器上跑一句

机器要求是 **Linux 或 WSL2 里的 Ubuntu**（Windows 原生跑不了：出片脚本是 bash +
`apt` + Linux 字体路径；**Alpine 之类的 musl 版也不行**——官方 runner 只有 glibc 构建，
脚本一开头就会把它拦下）。打开终端：

```bash
gh repo clone 32r4e2q-hub/desktop-tutorial      # 仓库是私有的，用 gh（已登录）才 clone 得下来
cd desktop-tutorial                             # 已经有仓库就：git pull
bash runner/setup-runner.sh
```

> 脚本**不依赖仓库文件**：装在哪个目录、从哪个目录跑都行（仓库里、`~/` 下、甚至 PowerShell 里
> `wsl bash runner/setup-runner.sh` 都行）。它自己会下 runner、装依赖、预下模型。

脚本会按顺序做 6 件事，每一步都可以单独跳过：

| 步骤 | 做什么 | 跳过用什么参数 |
|---|---|---|
| 0 | 认系统/架构/磁盘（Windows 原生直接拦下） | — |
| 1 | **查仓库是不是私有**（公开就拒绝注册） | —— 这条不能跳过 |
| 2 | 装 git / python3 / ffmpeg / Noto CJK 中文字体 | `--no-deps` |
| 3 | 下载 runner 安装包并**验校验和** | 已装过会自动跳过 |
| 4 | 预下载 whisper 模型 base + small（~600 MB） | `--no-models` |
| 5 | 注册到仓库（token 现场取，不落盘） | `--no-register` |
| 6 | 装成 systemd 服务；**没有 systemd 时**改成后台进程 + 装上**看门狗**（`~/watchdog.sh` + Windows 计划任务，5 分钟一轮） | `--no-service` |

想连开关一起拨（gh 已登录且是仓库 admin）：

```bash
bash runner/setup-runner.sh --set-switch
```

它会在确认 runner **online** 之后，把仓库变量一次设好：

| 变量 | 值 | 作用 |
|---|---|---|
| `RUNNER_LABEL` | `self-hosted` | 9 个工作流的 `runs-on` 一起切到你的机器 |
| `WHISPER_CACHE_DIR` | `~/.cache/whisper` | 模型只下一次，之后每个 job 复用 |
| `HF_ENDPOINT` / `HF_HUB_DISABLE_XET` | 仅 `--hf-mirror` 时才设 | 连不上 huggingface.co 时走镜像 |

---

## 二、验证

```bash
bash runner/selfcheck.sh     # 只读自检，不改任何东西；有 ✗ 就照提示修
```

然后 GitHub 上：

1. **Settings → Actions → Runners** 看到这台机器是绿色 **Idle**；
2. **Actions → 离线自检 → Run workflow** —— 日志开头会打印 `Runner name: <你的机器名>`；
3. 真出一次片：**Actions → 解说短片出片 → `project` 填 `dahlia`**；
4. 看 **Billing → Actions**：分钟数**没有**增加，说明真的跑在自己的机器上。

---

## 三、后悔了

| 想怎样 | 怎么做 |
|---|---|
| 临时借 GitHub 的机器 | 删掉仓库变量 `RUNNER_LABEL`，一切回到 `ubuntu-latest` |
| 机器休眠/关机时别排队 | 同上，或者把机器开着——自托管的代价就是"机器得醒着" |
| runner 半夜自己死了（任务卡在 Waiting for a runner） | 看门狗每 5 分钟自动拉回来；手动催一次：`~/watchdog.sh` |
| 彻底卸掉 | `bash runner/uninstall-runner.sh`（`--purge` 连目录一起删） |
| 仓库要改回公开 | **先卸掉 runner 再改公开**，顺序不能反 |

---

## 关于 token 的一句话

注册 token / remove token 都只从 GitHub **现场取一次**（1 小时有效），
脚本拿到就用、用完 `unset`，**不写文件、不打日志、不进 Git**。
gh 自动取不到时，脚本会给你确切的页面地址，让你自己复制、以不回显方式粘贴。

**不要把 token 贴进任何聊天框**（包括和我对话时）——
这也是为什么我（代理）没法替你注册：GitHub App 没有 `administration` 权限，
既取不到注册 token 也写不了仓库变量。注册这一步只能在你自己的机器上完成。

---

## 文件

| 文件 | 作用 |
|---|---|
| `setup-runner.sh` | 一键安装 + 注册 + 装服务（幂等，可反复跑） |
| `selfcheck.sh` | 只读自检：系统 / 依赖 / 字体 / 服务 / 模型 / 磁盘 / 仓库，退出码 0 才可出片 |
| `uninstall-runner.sh` | 反注册 + 停服务 + 可选删目录 |
| `watchdog.sh` | 没有 systemd 时的保活：监听器不在就拉起来；`setup-runner.sh` 会装到 `~/` 并挂计划任务 |
