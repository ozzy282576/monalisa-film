#!/usr/bin/env bash
# One-time setup: python deps + a bundled ffmpeg binary.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "== 手绘故事视频 · 环境安装 =="

if command -v python3 >/dev/null; then
  echo "→ python3 $(python3 -V 2>&1 | awk '{print $2}')"
else
  echo "缺少 python3（需要 3.10+）" >&2; exit 1
fi

echo "→ 安装 Python 依赖 (numpy, Pillow)"
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo "→ 安装 ffmpeg（通过 npm 分发的静态二进制）"
if command -v npm >/dev/null; then
  npm install --silent --no-audit --no-fund
  chmod +x node_modules/@ffprobe-installer/linux-x64/ffprobe 2>/dev/null || true
else
  echo "  未找到 npm；如系统已有 ffmpeg，可用 FFMPEG=/path/to/ffmpeg 指定" >&2
fi

if [ ! -f assets/fonts/MaShanZheng-Regular.ttf ]; then
  echo "缺少手写字体 assets/fonts/MaShanZheng-Regular.ttf" >&2; exit 1
fi

echo "→ 自检"
python3 tests/test_pipeline.py

echo
echo "完成。下一步：bash examples/build-demo.sh"
