#!/usr/bin/env bash
# Agent Lab 环境初始化:安装 OpenCode + 根据 Codespaces Secrets 自动写入 API 配置
set -u

echo "=== [1/3] 安装 OpenCode ==="
# 加超时:装不上也要让容器起来,不能把用户卡在 "Setting up your codespace"
if command -v timeout >/dev/null 2>&1; then
  timeout 300 bash -c 'curl -fsSL --max-time 120 https://opencode.ai/install | bash' || \
    echo "  !! 安装超时或失败,稍后可在终端手动重试(见末尾提示)"
else
  curl -fsSL --max-time 120 https://opencode.ai/install | bash || true
fi

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

if [ -n "${OPENROUTER_API_KEY:-}" ]; then
  # OpenRouter 是 OpenCode 内置 provider:不要覆盖 npm / baseURL,
  # 只补模型进选择器,其余模型由内置目录自动带出来。
  #
  # 免费模型阵容经常变动,写死 slug 迟早 404。
  # 所以这里在开机时用你的 key 查一次官方模型表,自动筛出当前所有 :free 模型。
  # 查不到(离线/超时)就退回一份保守的静态清单。
  OR_MODELS=""
  if command -v python3 >/dev/null 2>&1; then
    OR_MODELS="$(curl -fsSL --max-time 20 \
        -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
        https://openrouter.ai/api/v1/models 2>/dev/null \
      | python3 -c '
import json,sys
try:
    data=json.load(sys.stdin).get("data",[])
except Exception:
    sys.exit(1)
free=[]
for m in data:
    mid=m.get("id","")
    if not mid.endswith(":free"):
        continue
    p=m.get("pricing",{}) or {}
    def z(k):
        try: return float(p.get(k,0) or 0)==0.0
        except (TypeError,ValueError): return False
    if not (z("prompt") and z("completion")):
        continue
    ctx=m.get("context_length") or 0
    free.append((ctx,mid,(m.get("name") or mid)))
if not free:
    sys.exit(1)
# 上下文长的排前面,通常更适合 agent 干活
free.sort(key=lambda t:-t[0])
lines=[]
for ctx,mid,name in free[:25]:
    label=name.replace("(free)","").strip() or mid
    if ctx:
        label="%s [%dk]" % (label, ctx//1000)
    lines.append("        %s: { \"name\": %s }" % (json.dumps(mid), json.dumps(label)))
print(",\n".join(lines))
' 2>/dev/null)"
  fi

  if [ -n "$OR_MODELS" ]; then
    OR_COUNT="$(printf '%s\n' "$OR_MODELS" | grep -c ':free')"
    echo "  + OpenRouter:已抓取 ${OR_COUNT} 个当前可用的 :free 模型"
  else
    OR_MODELS='        "deepseek/deepseek-chat-v3.1": { "name": "DeepSeek V3.1" },
        "qwen/qwen3-coder": { "name": "Qwen3 Coder" },
        "anthropic/claude-sonnet-4.5": { "name": "Claude Sonnet 4.5" },
        "google/gemini-2.5-flash": { "name": "Gemini 2.5 Flash" }'
    echo "  + OpenRouter:未能抓取免费模型列表(网络/额度),已退回静态清单"
  fi

  # 轮询/兜底:把抓到的免费模型编成 fallback 链,第一个 429 或挂了就自动换下一个。
  # 注意这不增加额度(额度是账号级共享),只是让某个模型被挤爆时任务还能继续。
  OR_ROUTE=""
  if command -v python3 >/dev/null 2>&1; then
    OR_ROUTE="$(printf '%s\n' "$OR_MODELS" | python3 -c '
import sys,json,re
ids=re.findall(r"^\s*\"([^\"]+)\"\s*:", sys.stdin.read(), re.M)
print(json.dumps(ids[:6]) if ids else "")
' 2>/dev/null)"
  fi

  OR_FIRST="$(printf '%s\n' "$OR_MODELS" | sed -n 's/^[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"

  add_provider '"openrouter": {
      "options": {
        "apiKey": "'"${OPENROUTER_API_KEY}"'",
        "models": '"${OR_ROUTE:-[]}"',
        "route": "fallback"
      },
      "models": {
'"${OR_MODELS}"'
      }
    }'
  echo "    (免费额度是账号级共享:未充值 50 次/天、充过 \$10 则 1000 次/天,均 20 次/分钟)"
fi

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

if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  add_provider '"deepseek": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "DeepSeek",
      "options": {
        "baseURL": "https://api.deepseek.com",
        "apiKey": "'"${DEEPSEEK_API_KEY}"'"
      },
      "models": {
        "deepseek-chat": { "name": "DeepSeek V3" },
        "deepseek-reasoner": { "name": "DeepSeek R1" }
      }
    }'
  echo "  + DeepSeek 官方 API 已配置"
fi

if [ -n "${GEMINI_API_KEY:-}" ]; then
  add_provider '"gemini": {
      "npm": "@ai-sdk/google",
      "name": "Google Gemini",
      "options": {
        "apiKey": "'"${GEMINI_API_KEY}"'"
      },
      "models": {
        "gemini-2.0-flash": { "name": "Gemini 2.0 Flash" },
        "gemini-1.5-flash": { "name": "Gemini 1.5 Flash" }
      }
    }'
  echo "  + Google Gemini API 已配置"
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
echo "=== [3/3] 启动 Web 触屏界面与快捷命令 ==="
cat > "$HOME/.local/bin/agent-web" << 'RUNNER'
#!/usr/bin/env bash
echo "正在启动 OpenCode Web UI (端口 4096)..."
if command -v opencode >/dev/null 2>&1; then
  opencode web --port 4096 --hostname 0.0.0.0
elif [ -x "$HOME/.local/bin/opencode" ]; then
  "$HOME/.local/bin/opencode" web --port 4096 --hostname 0.0.0.0
else
  echo "未找到 opencode 命令"
fi
RUNNER
chmod +x "$HOME/.local/bin/agent-web"

# 后台自动启动 OpenCode Web UI，无需在手机上敲终端命令
pkill -f "opencode web" 2>/dev/null || true
if [ -x "$HOME/.local/bin/opencode" ]; then
  nohup "$HOME/.local/bin/opencode" web --port 4096 --hostname 0.0.0.0 > /tmp/opencode-web.log 2>&1 &
  echo "  ✔ OpenCode 网页端已在后台启动 (端口 4096)"
  echo "  📱 手机使用提示：点击 VS Code 底部 'PORTS (端口)' 标签页 ➔ 4096 端口右侧地球图标，即可在 Safari 中打开极简触屏界面！"
fi

if [ -n "$providers" ]; then
  echo "  ✔ API 已就绪，可直接在 Web 界面下任务"
else
  echo "!! 没检测到任何 API Key Secret。"
  echo "   去 github.com → Settings → Codespaces → Secrets 添加"
  echo "   (OPENROUTER_API_KEY / SILICONFLOW_API_KEY / SENSENOVA_API_KEY / GROQ_API_KEY 任选一或多个),"
  echo "   然后在 Codespace 里重建容器(Ctrl+Shift+P → Dev Containers: Rebuild Container)。"
fi
