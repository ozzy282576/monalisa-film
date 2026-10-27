#!/usr/bin/env bash
# 只读自检：这台机器现在能不能当自托管 runner？（不改任何东西，随时可以跑）
#
#   bash runner/selfcheck.sh
#
# 出片跑到一半才失败最费时间，所以先把能查的都查一遍：
# 系统 → 依赖 → 字体 → runner 服务 → 模型缓存 → 磁盘 → 仓库可见性。
# 退出码 0 = 可以出片；1 = 有必须修的问题（看 ✗ 那几行）。
set -uo pipefail

REPO="${REPO:-32r4e2q-hub/desktop-tutorial}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
MODEL_CACHE="${MODEL_CACHE:-$HOME/.cache/whisper}"

if [ -t 1 ]; then
  C_RESET=$'\033[0m'; C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_BAD=$'\033[31m'
else
  C_RESET=""; C_OK=""; C_WARN=""; C_BAD=""
fi

FAILS=0; WARNS=0
ok()   { printf '  %s✓%s %s\n'   "$C_OK"   "$C_RESET" "$*"; }
warn() { printf '  %s!%s %s\n'   "$C_WARN" "$C_RESET" "$*"; WARNS=$((WARNS+1)); }
bad()  { printf '  %s✗%s %s\n'   "$C_BAD"  "$C_RESET" "$*"; FAILS=$((FAILS+1)); }
head1() { printf '\n%s%s%s\n' "$C_OK" "$*" "$C_RESET"; }
have() { command -v "$1" >/dev/null 2>&1; }

echo "自检：$REPO 的自托管 runner —— 主机名 $(hostname)，$(date '+%F %T')"

# ---------------------------------------------------------------- 1. 系统
head1 "1. 系统"
OS="$(uname -s)"
case "$OS" in
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then ok "Linux / WSL2"
    else ok "Linux $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"; fi
    [ -d /run/systemd/system ] && ok "systemd 在位（runner 能装成服务）" \
      || warn "没有 systemd（WSL2 默认如此）：runner 只能挂在后台进程上，重启后要手动 ./run.sh"
    ;;
  Darwin) warn "macOS：出片脚本认的是 Linux 字体路径，中文渲染多半会拒绝出片" ;;
  MINGW*|MSYS*|CYGWIN*) bad "Windows 原生 shell 跑不了这套流水线，请用 WSL2 的 Ubuntu" ;;
  *) bad "不支持的系统：$OS" ;;
esac
ok "架构 $(uname -m)"

# ---------------------------------------------------------------- 2. 依赖
head1 "2. 出片需要的命令"
for c in git curl python3 ffmpeg ffprobe; do
  if have "$c"; then
    case "$c" in
      ffmpeg|ffprobe) ok "$c $("$c" -hide_banner -version 2>/dev/null | head -1 | awk '{print $3}')" ;;
      python3)        ok "python3 $(python3 -V 2>&1 | awk '{print $2}')" ;;
      git)            ok "git $(git --version | awk '{print $3}')" ;;
      *)              ok "$c 在位" ;;
    esac
  else
    bad "$c 不在 PATH 里（一行装齐：sudo apt-get install -y git curl python3 python3-venv python3-pip ffmpeg fonts-noto-cjk）"
  fi
done

# ---------------------------------------------------------------- 3. 字体
head1 "3. 中文字体"
if have fc-list && fc-list | grep -qi "Noto.*CJK"; then
  ok "Noto CJK 在位：$(fc-list | grep -i 'Noto.*CJK' | head -1 | cut -d: -f1)"
else
  bad "没有 Noto CJK —— 渲染会直接报 refusing to render missing glyphs
        sudo apt-get install -y fonts-noto-cjk"
fi

# ---------------------------------------------------------------- 4. runner 本体
head1 "4. runner 本体（$RUNNER_DIR）"
if [ -x "$RUNNER_DIR/config.sh" ]; then
  ok "config.sh 在位"
  if [ -f "$RUNNER_DIR/.runner" ]; then
    NAME="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("agentName","?"))' "$RUNNER_DIR/.runner" 2>/dev/null || echo '?')"
    ok "已注册，GitHub 上的名字：$NAME"
  else
    warn "还没注册 —— bash runner/setup-runner.sh"
  fi
else
  warn "runner 没装 —— bash runner/setup-runner.sh"
fi

RUNNING=0
if pgrep -f "Runner.Listener" >/dev/null 2>&1; then RUNNING=1; fi
if [ "$RUNNING" = 1 ]; then
  ok "进程在跑（Runner.Listener，pid $(pgrep -f 'Runner.Listener' | head -1)）"
else
  warn "进程没在跑：cd $RUNNER_DIR && sudo ./svc.sh start   （没装服务就 nohup ./run.sh &）"
fi

if [ -d /run/systemd/system ] && have systemctl; then
  if systemctl list-units --type=service --all 2>/dev/null | grep -q "actions.runner"; then
    SVC="$(systemctl list-units --type=service --all 2>/dev/null | awk '/actions.runner/{print $1; exit}')"
    STATE="$(systemctl is-active "$SVC" 2>/dev/null || echo unknown)"
    [ "$STATE" = active ] && ok "服务 $SVC 是 active（重启后自动回来）" \
      || warn "服务 $SVC 现在是 $STATE：cd $RUNNER_DIR && sudo ./svc.sh start"
  else
    warn "没有 actions.runner.* 服务（还没装服务，或注册时用了 --no-service）"
  fi
fi

# ---------------------------------------------------------------- 5. 模型缓存
head1 "5. whisper 模型缓存（$MODEL_CACHE）"
if [ -d "$MODEL_CACHE" ]; then
  SIZE="$(du -sh "$MODEL_CACHE" 2>/dev/null | awk '{print $1}')"
  ok "目录在，占 $SIZE"
  for m in base small; do
    if [ -d "$MODEL_CACHE/models--Systran--faster-whisper-$m" ] || \
       find "$MODEL_CACHE" -maxdepth 3 -iname "*$m*" -print -quit 2>/dev/null | grep -q .; then
      ok "$m 已缓存（出片不用重下）"
    else
      warn "$m 没缓存 —— 每个 job 都要现下几百 MB。
        预下载：cd 仓库 && bash runner/setup-runner.sh --no-deps --no-register"
    fi
  done
else
  warn "缓存目录不存在，模型会每个 job 重下一次（慢，且容易超时）"
fi

# ---------------------------------------------------------------- 6. 磁盘
head1 "6. 磁盘"
FREE_GB="$(df -Pk "$HOME" | awk 'NR==2 {printf "%d", $4/1024/1024}')"
[ "${FREE_GB:-0}" -ge 15 ] && ok "家目录余量 ${FREE_GB} GB" \
  || warn "家目录只剩 ${FREE_GB} GB：成片 48 MB + 模型 600 MB + work/ 中间产物，建议留 15 GB 以上"
if [ -d "$RUNNER_DIR/_work" ]; then
  ok "_work 目录占 $(du -sh "$RUNNER_DIR/_work" 2>/dev/null | awk '{print $1}')（清：rm -rf $RUNNER_DIR/_work/*）"
fi

# ---------------------------------------------------------------- 7. 仓库
head1 "7. 仓库"
if have gh && gh auth status >/dev/null 2>&1; then
  PRIVATE="$(gh api "repos/$REPO" --jq '.private' 2>/dev/null)" || PRIVATE=""
  case "$PRIVATE" in true|false) ;; *) PRIVATE="" ;; esac   # gh 报错时错误 JSON 也会走 stdout
  case "$PRIVATE" in
    true)  ok "$REPO 是私有的 —— 自托管 runner 挂上去是安全的" ;;
    false) bad "$REPO 是**公开**的！先把它转私有，否则任何 fork PR 都能在这台机器上执行代码" ;;
    *)     warn "查不到可见性（gh 账号对这个仓库没读权限）—— 自己确认：https://github.com/$REPO/settings" ;;
  esac
  # 注意：gh 报错时错误 JSON 也会走 stdout，所以必须看退出码，不能只看有没有输出
  LABEL="$(gh api "repos/$REPO/actions/variables/RUNNER_LABEL" --jq .value 2>/dev/null)" || LABEL=""
  if [ -n "$LABEL" ]; then ok "RUNNER_LABEL=$LABEL —— 工作流已经指向你的机器"
  else warn "还没设 RUNNER_LABEL，工作流仍在跑 GitHub 的机器（吃 2000 分钟额度）" ; fi
else
  warn "gh 没装/没登录，跳过仓库检查（不影响出片）"
fi

# ---------------------------------------------------------------- 结论
printf '\n'
if [ "$FAILS" -gt 0 ]; then
  printf '%s✗ 有 %d 项必须修（看上面的 ✗），修完再出片。%s\n' "$C_BAD" "$FAILS" "$C_RESET"
  exit 1
fi
if [ "$WARNS" -gt 0 ]; then
  printf '%s✓ 可以出片，但有 %d 条提醒（看上面的 !）。%s\n' "$C_WARN" "$WARNS" "$C_RESET"
  exit 0
fi
printf '%s✓ 全部通过 —— 这台机器可以接出片任务。%s\n' "$C_OK" "$C_RESET"
