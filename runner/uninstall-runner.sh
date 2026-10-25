#!/usr/bin/env bash
# 反注册这台机器上的 runner：停服务 → 从 GitHub 上摘掉 → 可选删目录。
#
#   bash runner/uninstall-runner.sh              # 停 + 摘掉（保留 ~/actions-runner）
#   bash runner/uninstall-runner.sh --purge      # 连目录一起删（models/工作区没了，会重下）
#
# 什么时候需要：仓库要改回公开、机器要送人、或者 runner 名字/标签想重来一次。
# 只摘掉不清目录是最常用的：重新注册只要再跑一次 setup-runner.sh。
set -euo pipefail

REPO="${REPO:-32r4e2q-hub/desktop-tutorial}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
PURGE=0
ASSUME_YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)  REPO="${2:?--repo 缺值}"; shift 2 ;;
    --dir)   RUNNER_DIR="${2:?--dir 缺值}"; shift 2 ;;
    --purge) PURGE=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    -h|--help) sed -n '/^   bash runner\/uninstall-runner.sh/,/^   bash runner\/uninstall-runner.sh --purge/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "不认识的参数：$1" >&2; exit 1 ;;
  esac
done

if [ -t 1 ]; then C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_RESET=$'\033[0m'; else C_OK=""; C_WARN=""; C_RESET=""; fi
ok()   { printf '  %s✓%s %s\n' "$C_OK" "$C_RESET" "$*"; }
warn() { printf '  %s!%s %s\n' "$C_WARN" "$C_RESET" "$*"; }

[ -d "$RUNNER_DIR" ] || { echo "$RUNNER_DIR 不存在，没什么可卸的。"; exit 0; }
cd "$RUNNER_DIR"

echo "卸载 $RUNNER_DIR 里的 runner（仓库 $REPO）"
if [ "$ASSUME_YES" = 0 ]; then
  read -r -p "  确定吗？[y/N] " reply || reply=""
  case "$reply" in y|Y|yes|YES) ;; *) echo "算了，没动。"; exit 0 ;; esac
fi

# 1) 停服务
if [ -x ./svc.sh ] && (systemctl list-units --type=service --all 2>/dev/null | grep -q "actions.runner"); then
  sudo ./svc.sh stop >/dev/null 2>&1 || true
  sudo ./svc.sh uninstall >/dev/null 2>&1 || true
  ok "systemd 服务已停并移除"
else
  pkill -f "Runner.Listener" >/dev/null 2>&1 || true
  ok "后台进程已停"
fi

# 2) 摘掉注册（需要一个 remove token，同样是 1 小时有效、现场取）
TOKEN=""
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  TOKEN="$(gh api -X POST "repos/$REPO/actions/runners/remove-token" --jq .token 2>/dev/null || echo "")"
fi
if [ -n "$TOKEN" ]; then
  ./config.sh remove --token "$TOKEN" >/dev/null 2>&1 && ok "已从 GitHub 摘掉" \
    || warn "摘除失败。手动来：https://github.com/$REPO/settings/actions/runners → 这台机器右边点 Remove"
  unset TOKEN
else
  warn "拿不到 remove token（gh 没登录或不是 admin）。手动摘：
        https://github.com/$REPO/settings/actions/runners → 这台机器 → Remove
        只想让任务别跑到这台机器上，把仓库变量 RUNNER_LABEL 删掉也就够了。"
fi

# 3) 可选删目录
if [ "$PURGE" = 1 ]; then
  rm -rf "$RUNNER_DIR"
  ok "目录已删（下次要跑就重新 bash runner/setup-runner.sh，模型和依赖会重下）"
else
  echo "  目录留着：$RUNNER_DIR（要连锅端：--purge）"
fi

cat <<TXT

如果仓库要改回公开，**先确认这台 runner 已经从页面上消失**再改：
https://github.com/$REPO/settings/actions/runners
TXT
