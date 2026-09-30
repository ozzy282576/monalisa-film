#!/usr/bin/env bash
# Bring the workspace back to a playable state after it has been reset.
#
# The sandbox workspace is periodically reset to the initial commit. Everything
# that matters lives on the branch, and the finished film is committed too, so
# recovery is mechanical — this script just does it in one step instead of five.
#
#   bash tools/resume.sh            # restore + install deps + serve on :8000
#   bash tools/resume.sh --no-serve # restore + install deps only
#
set -euo pipefail

BRANCH="${BRANCH:-arena/01a0efe7-monalisa-film}"
PORT="${PORT:-8000}"
SERVE=1
[[ "${1:-}" == "--no-serve" ]] && SERVE=0

cd "$(dirname "$0")/.."
echo "==> workspace: $(pwd)"

# 1. Restore. The remote branch is the source of truth; a reset workspace is
#    discarded, and the film comes back with it.
echo "==> restoring $BRANCH from origin"
git fetch origin --quiet
git reset --hard "origin/$BRANCH" --quiet
echo "    HEAD $(git log --oneline -1)"

# 2. Dependencies. Neither survives a reset.
echo "==> installing python deps"
python3 -m pip install --break-system-packages --quiet pillow numpy

if [[ -f package.json && ! -x node_modules/@ffmpeg-installer/linux-x64/ffmpeg ]]; then
  echo "==> installing npm deps (ffmpeg / ffprobe)"
  npm install --silent --no-audit --no-fund
fi
# The npm ffprobe ships without the execute bit.
chmod +x node_modules/@ffprobe-installer/linux-x64/ffprobe 2>/dev/null || true
chmod +x node_modules/@ffmpeg-installer/linux-x64/ffmpeg 2>/dev/null || true

# 3. Sanity-check the deliverable rather than assuming it restored.
FILM="renders/noire-1080x1920.mp4"
if [[ -f "$FILM" ]]; then
  echo "==> film present: $FILM ($(du -h "$FILM" | cut -f1))"
else
  echo "!!  $FILM missing — run: python3 scripts/run_noire_video.py --mode render" >&2
fi

if [[ "$SERVE" == "1" ]]; then
  echo "==> serving web/ on 0.0.0.0:$PORT  (Ctrl-C to stop)"
  exec python3 tools/serve_video.py --root web --port "$PORT"
fi
