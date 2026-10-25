#!/usr/bin/env bash
# runner 看门狗：Runner.Listener 不在了就把它拉回来。
#
# 为什么需要它（2026-09-20 实测）：
#   这台机器上的 runner 是「没有 systemd，退回后台进程」的方式跑的
#   （`setsid nohup ./run.sh &`）。它**会静默死掉**：run.log 里
#     2026-09-20 02:51:15Z: Listening for Jobs
#     2026-09-20 07:57:46Z: Listening for Jobs      ← 中间空了 5 小时，是重连
#   这 5 小时里派发的出片任务全卡在
#     "Waiting for a runner to pick up this job..."
#   而人不会盯着看 —— 一条 3 分钟出片能这么干等 6 小时。
#
# 怎么用（Windows + WSL，没有 systemd 也能自启）：
#   PowerShell（每 5 分钟检查一次，开机/登录后也自动跑）：
#     schtasks /create /tn "runner-watchdog" /sc minute /mo 5 /f ^
#       /tr "C:\Windows\System32\wsl.exe -d Ubuntu -u runner -- /home/runner/watchdog.sh"
#   （PowerShell 里上面的 ^ 要换成反引号续行，或者写成一行）
#
# 设计要点：
#   * 用 pgrep 数监听器进程，不是数 run.sh —— run.sh 只是壳，
#     壳在而监听器死掉的情况同样接不到任务；
#   * 匹配模式是 bin/Runner.Listener 而不是光写 Runner.Listener：
#     pgrep -f 比的是整条命令行，任何**提到**这个名字的进程（比如你自己开个
#     终端敲 grep Runner.Listener、或者看门狗被包在别的脚本里）都会算命中，
#     于是看门狗判断"还活着"、什么都不做 —— 而它存在的唯一意义就是别误判。
#     真实进程的命令行一定含 bin/Runner.Listener（run.sh 里就是 ./bin/Runner.Listener run）；
#   * 只在**动手重启**时写 watchdog.log，避免每天 288 行心跳把日志淹了；
#     想知道它有没有在跑，看 .watchdog-heartbeat 的时间戳；
#   * 用 flock 防重入：万一某次启动慢，下一个 5 分钟的点不会叠上来；
#   * 启动后回查一次（默认 15 秒），没起来就记一行失败，别装作没事。
set -uo pipefail

RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
LOG="${WATCHDOG_LOG:-$RUNNER_DIR/watchdog.log}"
HEARTBEAT="$RUNNER_DIR/.watchdog-heartbeat"
WAIT_SECONDS="${WATCHDOG_WAIT:-15}"

log() { printf '%s %s\n' "$(date -Is)" "$*" >>"$LOG"; }
say() { printf '%s %s\n' "$(date -Is)" "$*"; }

mkdir -p "$RUNNER_DIR" || { say "看门狗：建不了 $RUNNER_DIR"; exit 1; }

# 防重入：同一时刻只允许一个看门狗在跑
if command -v flock >/dev/null 2>&1; then
  exec 9>"$RUNNER_DIR/.watchdog.lock" || exit 1
  flock -n 9 || { say "看门狗：上一次还在跑，这次跳过"; exit 0; }
fi

date -Is >"$HEARTBEAT" 2>/dev/null || true

if [ ! -f "$RUNNER_DIR/.runner" ]; then
  # 没注册过就直接说清楚，别每 5 分钟去踹一次 run.sh
  log "runner 没有注册（缺 $RUNNER_DIR/.runner），看门狗什么都不做"
  say "看门狗：runner 还没注册（缺 .runner）"
  exit 1
fi

RUNNER_PATTERN='bin/Runner\.Listener'

if pgrep -f "$RUNNER_PATTERN" >/dev/null 2>&1; then
  [ "${WATCHDOG_VERBOSE:-0}" = "1" ] && log "runner 活着，不动它"
  exit 0
fi

log "runner 不在了，重新启动（setsid nohup ./run.sh）"
say "看门狗：runner 不在了，正在重新启动"
cd "$RUNNER_DIR" || { log "进不去 $RUNNER_DIR"; exit 1; }
# 必须 setsid：不然看门狗自己退出时，这个子进程会跟着被带走，
# 于是「拉起来了」只是假象（这正是 setup-runner.sh 早期踩过的坑）。
# 9>&- 也要有：上面 flock 用的 fd 9 会被子进程继承，runner 活得越久，
# 锁就被它攥得越久 —— 之后每次看门狗检查都会以为「上一次还在跑」而跳过。
setsid nohup ./run.sh >>"$RUNNER_DIR/run.log" 2>&1 </dev/null 9>&- &

for waited in $(seq 1 "$WAIT_SECONDS"); do
  sleep 1
  if pgrep -f "$RUNNER_PATTERN" >/dev/null 2>&1; then
    log "重新启动成功（等待 ${waited}s 后看到监听器进程）"
    say "看门狗：runner 已重新上线"
    exit 0
  fi
done

log "重新启动失败：等了 ${WAIT_SECONDS}s 仍没有监听器进程，看 run.log"
say "看门狗：启动失败，看 $RUNNER_DIR/run.log"
exit 1
