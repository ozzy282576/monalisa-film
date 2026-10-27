#!/usr/bin/env bash
# 通用出片脚本：任何 production/<slug> 项目都能跑，不需要再改 .github/workflows/。
#
#   bash production/run_project.sh <slug> [skip_asr] [成片文件名]
#
# 例：bash production/run_project.sh dahlia
#     bash production/run_project.sh ripper1888 true
#
# 流程与参考项目一致：校验计划与配音来源 → 按 SHA-256 回填素材（不重新生成）
# → 剪辑 + 混音 + 成品复测 → 把成片与实测报告 commit 回**当前分支**。
set -euo pipefail

PROJECT="${1:?用法: production/run_project.sh <slug> [skip_asr] [成片文件名]}"
SKIP_ASR="${2:-false}"
DIR="production/$PROJECT"
WORK="work/$PROJECT"
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"

[ -d "$DIR" ] || { echo "没有这个项目：$DIR" >&2; exit 1; }
for f in generate.py fetch_sources.py render.py story.json; do
  [ -f "$DIR/$f" ] || { echo "缺少 $DIR/$f，这个项目还没开完（试试 production/new_topic.py）" >&2; exit 1; }
done

TITLE="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['title'])" "$DIR/story.json")"
SAFE_TITLE="$(python3 -c "
import re,sys
print(re.sub(r'[\\\\/:*?\"<>|]', '_', sys.argv[1]).strip() or 'untitled')
" "$TITLE")"
FILM="$WORK/${3:-$SAFE_TITLE.mp4}"

echo "=== 项目 $PROJECT / 分支 $BRANCH / 成片 $FILM ==="

echo "=== 1/5 校验计划与配音来源（闸门一）==="
python3 "$DIR/generate.py" --validate

echo "=== 2/5 按 SHA-256 回填已生成素材（不重新生成、不消耗额度）==="
python3 -u "$DIR/fetch_sources.py" --dest "$WORK/clips"

echo "=== 3/5 剪辑 + 混音 + 成品复测（闸门二、三）==="
EXTRA=()
[ "$SKIP_ASR" = "true" ] && EXTRA+=("--skip-asr")
python3 -u "$DIR/render.py" \
  --sources "$WORK/clips" --work "$WORK" --output "$FILM" ${EXTRA[@]+"${EXTRA[@]}"}

echo "=== 4/5 把成片与实测报告 commit 回 $BRANCH ==="
mkdir -p 交付 "$DIR/delivery"
cp "$FILM" "交付/$(basename "$FILM")"
for f in technical-report.json audio-report.json final-audio-report.json \
         alignment-report.json caption-timing.json narration-timing.json \
         edit-decision-list.json final-contact.jpg captions.srt; do
  [ -f "$WORK/$f" ] && cp "$WORK/$f" "$DIR/delivery/" || echo "skip $f"
done

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
# 提交成片前，先把上一个 job 残留在同一个 _work 目录里的 sparse-checkout 关掉。
# 离线自检（ci-tests）用 sparse-checkout 跳过 *.mp4 省 48 MB，它把 core.sparseCheckout
# 留在了 .git/config：成片 add 不进索引，一次成功的出片被判失败 —— 2026-09-20 实测
# 1080p/180s/音频三道闸门全过，却倒在第 4/5 步 commit 上，就是这个残留的锅。
git config --local core.sparseCheckout false 2>/dev/null || true
git add -f "交付/$(basename "$FILM")" "$DIR/delivery"
if git diff --cached --quiet; then
  echo "No changes to publish"
else
  git commit -m "Deliver the $PROJECT cut with measured audio"
  # 这一步必须扛住网络抖动：整场渲染（几十到 90 分钟）的成果全靠它推回去。
  # 2026-09-18 实测：这台机器的网络上，git 连 github.com 会偶发 133 秒超时
  # （"133182 ms: Connection timed out"），只推一次等于把成果交给运气。
  # 2026-09-20 实测：只推 5 次也不够 —— 5 次各自卡满 300 秒
  # （"Failed to connect to github.com port 443 after 299980 ms: Connection timed out"），
  # 25 分钟全用来等同一个连不上的 socket，一次渲染 180 秒、音频三道闸门全过、
  # 成片也 add/commit 好了的出片被判成失败。而同一分钟里 `curl https://github.com`
  # 返回 200 / 2.2 秒 —— 链路是通的，只是 git 那几次连接不走运。
  # 结论：**快失败、多试**，比「少试、慢失败」强：
  #   ① 先用 4 秒 TCP 探针确认 github.com:443 可达，不可达就跳过本轮，
  #      不把 300 秒交给 git 自己的 connect 超时；
  #   ② 推的时候加 lowSpeedLimit/lowSpeedTime：传输卡住 30 秒就让出这一轮；
  #   ③ 最多 40 轮、每轮间隔 15 秒 —— 总时长可控（十分钟量级），胜率远高于 5 轮。
  push_ok=false
  for attempt in $(seq 1 40); do
    if ! timeout 4 bash -c 'cat </dev/null >/dev/tcp/github.com/443' 2>/dev/null; then
      echo "第 $attempt/40 轮：github.com:443 暂时不可达，等 15 秒" >&2
      sleep 15
      continue
    fi
    if git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 push origin "HEAD:$BRANCH"; then
      push_ok=true
      break
    fi
    echo "推送失败（第 $attempt/40 轮），等 15 秒重试……" >&2
    sleep 15
  done
  if [ "$push_ok" != true ]; then
    echo "成片与实测报告都已生成，但 40 轮都没能推回 $BRANCH（网络问题）。" >&2
    echo "成片在本次运行的 artifact 里，重跑一次即可；报告在 $DIR/delivery/。" >&2
    exit 1
  fi
  echo "PUBLISHED_COMMIT $(git rev-parse HEAD)"
fi

echo "=== 5/5 实测摘要 ==="
ls -la "$FILM"
python3 - "$DIR/delivery/final-audio-report.json" "$DIR/delivery/technical-report.json" <<'PY'
import json, sys
from pathlib import Path
for name in sys.argv[1:]:
    path = Path(name)
    if not path.exists():
        print(f"{name} -> 缺失")
        continue
    data = json.loads(path.read_text())
    keep = ("duration_seconds", "duration", "rms_dbfs", "peak_dbfs", "silent_fraction",
            "sample_rate", "channels", "audio_codec", "video_codec", "width", "height",
            "frames", "bytes")
    print(name, "->", json.dumps({k: data[k] for k in keep if k in data}, ensure_ascii=False))
PY
echo "JOB_DONE"
