# Agent Lab — 苹果手机免费跑 AI Agent 的全套环境

**GitHub Codespaces(免费 120 核时/月)+ OpenCode(开源 agent)+ 你自己的 API Key。**
手机 Safari 打开即用:不需要电脑、不需要越狱、不需要付费、不需要绑卡。

> **本仓库已经装好了。** 环境文件就在本仓库根目录的 `.devcontainer/`(`devcontainer.json` + `setup.sh`),
> 所以下面的**第 1、2 步你已经不用做了**,直接跳到 **第 3 步:添加 API Key**。
> 第 1、2 步的内容保留在下面,是为了以后你想把这套环境搬到别的仓库时照抄。
>
> 💡 **想要更简洁好操作、不敲命令的手机界面？**
> 如果觉得在手机浏览器里操作 Codespaces 终端和虚拟键盘较为繁琐，可以参考我们整理的图形化替代方案：
> 详见 [《界面简洁、手机好操作的 AI Agent 替代方案精选》](UI_ALTERNATIVES.md)（含 Bolt.new 极简建站、LobeChat 苹果质感 PWA、Chatbox App Store 直装等）。

## 工作原理

- iPhone 只是"窗口",真正干活的是 GitHub 免费送的云端 Linux 机器(2 核)
- OpenCode 是开源 AI agent:自己读代码 → 写代码 → 跑命令 → 修 bug,循环执行
- API 用你自己的(硅基流动 / 日日新 / Groq),额度就是 API 那边的额度,Codespaces 不限你调用

---

## 一次性设置(手机上约 10 分钟)

### 第 1 步:建仓库(本仓库已完成,可跳过)

Safari 打开 github.com 并登录 → 右上角 **+** → **New repository**
名称填 `agent-lab`,选 **Private**,其他都不动 → **Create repository**

### 第 2 步:放入两个文件(本仓库已完成,可跳过)

在仓库页点 **Add file → Create new file**,共做两次。

**文件 1**:文件名输入 `.devcontainer/devcontainer.json`(输入完 `devcontainer/` 会自动变成文件夹),内容粘贴:

```json
{
  "name": "agent-lab",
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
  "postCreateCommand": "bash .devcontainer/setup.sh"
}
```

**文件 2**:再次 Add file → Create new file,文件名 `.devcontainer/setup.sh`,内容粘贴:

```bash
#!/usr/bin/env bash
# Agent Lab 环境初始化:安装 OpenCode + 根据 Codespaces Secrets 自动写入 API 配置
set -u

echo "=== [1/3] 安装 OpenCode ==="
curl -fsSL https://opencode.ai/install | bash || true

# 确保 opencode 在 PATH 里(不管安装器把它放哪)
OC_BIN="$(command -v opencode 2>/dev/null || true)"
if [ -z "$OC_BIN" ]; then
  for p in "$HOME/.opencode/bin/opencode" "$HOME/.local/bin/opencode" "$HOME/bin/opencode"; do
    [ -x "$p" ] && OC_BIN="$p" && break
  done
fi
if [ -z "$OC_BIN" ]; then
  OC_BIN="$(find "$HOME" -maxdepth 4 -type f -name opencode 2>/dev/null | head -n1)"
fi
if [ -n "$OC_BIN" ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$OC_BIN" "$HOME/.local/bin/opencode"
  grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  echo "  ✔ OpenCode 就绪: $OC_BIN"
else
  echo "  !! 未找到 opencode,请手动执行: curl -fsSL https://opencode.ai/install | bash"
fi

echo ""
echo "=== [2/3] 写入 API 配置(读取 Codespaces Secrets)==="
mkdir -p "$HOME/.config/opencode"

providers=""

add_provider() {
  if [ -z "$providers" ]; then
    providers="$1"
  else
    providers="${providers},
    $1"
  fi
}

if [ -n "${SILICONFLOW_API_KEY:-}" ]; then
  add_provider '"siliconflow": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "SiliconFlow",
      "options": {
        "baseURL": "https://api.siliconflow.cn/v1",
        "apiKey": "'"${SILICONFLOW_API_KEY}"'"
      },
      "models": {
        "deepseek-ai/DeepSeek-V3.1": { "name": "DeepSeek V3.1" },
        "Qwen/Qwen3-Coder": { "name": "Qwen3 Coder" }
      }
    }'
  echo "  + SiliconFlow(硅基流动)已配置"
fi

if [ -n "${SENSENOVA_API_KEY:-}" ]; then
  add_provider '"sensenova": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "SenseNova",
      "options": {
        "baseURL": "https://token.sensenova.cn/v1",
        "apiKey": "'"${SENSENOVA_API_KEY}"'"
      },
      "models": {
        "sensenova-6.7-flash-lite": { "name": "SenseNova 6.7 Flash-Lite" },
        "deepseek-v4-flash": { "name": "DeepSeek V4 Flash" }
      }
    }'
  echo "  + SenseNova(日日新)已配置"
fi

if [ -n "${GROQ_API_KEY:-}" ]; then
  add_provider '"groq": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Groq",
      "options": {
        "baseURL": "https://api.groq.com/openai/v1",
        "apiKey": "'"${GROQ_API_KEY}"'"
      },
      "models": {
        "llama-3.3-70b-versatile": { "name": "Llama 3.3 70B" },
        "openai/gpt-oss-120b": { "name": "GPT-OSS 120B" }
      }
    }'
  echo "  + Groq 已配置"
fi

cat > "$HOME/.config/opencode/opencode.json" <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    ${providers}
  }
}
EOF
echo "  配置文件位置: ~/.config/opencode/opencode.json"

echo ""
echo "=== [3/3] 完成 ==="
if [ -n "$providers" ]; then
  echo "在终端运行 opencode,然后用 /models 选模型,直接下任务。"
else
  echo "!! 没检测到任何 API Key Secret。"
  echo "   去 github.com → Settings → Codespaces → Secrets 添加"
  echo "   (SILICONFLOW_API_KEY / SENSENOVA_API_KEY / GROQ_API_KEY 三选一或多个),"
  echo "   然后在 Codespace 里重建容器(Ctrl+Shift+P → Dev Containers: Rebuild Container)。"
fi
```

### 第 3 步:添加 API Key(⚠️ 必须在开 Codespace **之前**做)

github.com → 右上角头像 → **Settings** → 左侧 **Codespaces** → **Secrets** → **New secret**

名称必须严格一致(按你的 API 供应商选,几个都加也行):

| 你的 API | Secret 名称 | 值 |
|---|---|---|
| **OpenRouter** | **`OPENROUTER_API_KEY`** | 你的 key(`sk-or-v1-...`) |
| **DeepSeek 官方** | **`DEEPSEEK_API_KEY`** | 你的 key(`sk-...`) |
| **Google Gemini** | **`GEMINI_API_KEY`** | 你的 key(AI Studio 免费 Key) |
| 硅基流动 | `SILICONFLOW_API_KEY` | 你的 key |
| 日日新 | `SENSENOVA_API_KEY` | 你的 key |
| Groq | `GROQ_API_KEY` | 你的 key |

### 用 OpenRouter 免费模型(:free)要知道的事

开机时 `setup.sh` 会用你的 key 查一次 OpenRouter 官方模型表,
**自动筛出当前所有 `:free` 模型**(按上下文长度排序,取前 25 个)写进配置,
并编成 fallback 链——某个模型返回 429 或挂了会自动换下一个。
免费阵容经常变动,这样就不会出现写死 slug 结果 404 的情况。

⚠️ **但轮询不能突破额度,因为免费额度是"账号级"共享的**:

| 条件 | 每天 | 每分钟 |
|---|---|---|
| 从没充过值 | **50 次** | 20 次 |
| 一次性充过 $10(终身解锁,余额花光也保留) | **1000 次** | 20 次 |

- 50 次是**所有免费模型加起来**的总数,不是每个模型 50 次;同账号多开 key 也不增加
- **失败的请求照样扣额度**,所以别写疯狂重试的循环
- agent 干一个任务不是一次请求:读文件、改代码、跑命令、看结果,一轮轻松十几次调用。
  **50 次/天大概只够跑 1~2 个小任务**,想认真用建议一次性充 $10

想手动固定某个模型:编辑 `~/.config/opencode/opencode.json` 的
`provider.openrouter.models`,slug 用 OpenRouter 官网的格式(`厂商/模型名`,免费带 `:free`)。

保存时"仓库访问"选 **All repositories**(或指定 `desktop-tutorial`)。

### 第 4 步:启动

1. 回到仓库页,点绿色 **`<> Code`** → **Codespaces** 标签 → **Create codespace on main**（或当前分支）
2. 等 1–2 分钟，环境自动初始化完成；
3. **打开极简触屏界面（手机推荐，无需敲命令）**：
   - 在界面底部找到 **PORTS（端口）** 标签页；
   - 找到 `4096` 端口（标签为 `OpenCode Web UI`），点击其右侧的**地球图标（Open in Browser）**；
   - Safari 会在独立标签页中打开 OpenCode 官方 Web UI：图形化下拉选择模型、可视化查看代码改动、手机触摸键盘打字，体验就像 ChatGPT 网页一样清爽！
4. **（备选）传统终端方式**：
   - 如果想用终端：顶部菜单 ☰ → Terminal → New Terminal，输入 `opencode` 回车，`/models` 选模型直接下任务。

---

## 每天怎么用

- Safari 打开 **github.com/codespaces** → 点你的机器,直接回到上次的环境(文件、配置都保留)
- 建议:分享按钮 → **添加到主屏幕**,以后从桌面图标进入,像个 App
- 用完不用管:**30 分钟不动自动暂停**(不耗额度);想立刻停 → github.com/codespaces → 机器右侧 `···` → **Stop**

## 额度管理

- 免费:每月 **120 核时**(2 核机器 = 60 小时开机)+ 15GB 存储,**不用绑卡,用超只停不扣费**
- 查用量:Settings → Billing(看 Codespaces 的 Included quantities)
- 彻底删除:github.com/codespaces → Delete(释放存储额度)

## 常见问题

- **加了 Secret 但没生效?** Secret 必须在第一次创建 Codespace 之前加。后加的:在 Codespace 里按 `Ctrl+Shift+P`(外接键盘)→ **Dev Containers: Rebuild Container** 重建后生效
- **想换模型?** 编辑 `~/.config/opencode/opencode.json` 里的 models,模型 ID 必须和 API 控制台里完全一致;或改仓库里的 setup.sh 后重建
- **想加别的供应商?** OpenCode 内置 75+ 供应商:`opencode` → `/connect` 搜索(OpenAI / Anthropic / Groq 等直接粘 key)
- **429 Too Many Requests?** 免费层限速,等几分钟或 `/models` 换个模型
- **github.com 打不开?** 网络问题,挂梯子

## 试跑第一条任务

进入 opencode 后输入:

> 用 Python 写一个猜数字游戏,写完自己运行测试,有 bug 自己修

看它自己循环干活——这就是 agent。
