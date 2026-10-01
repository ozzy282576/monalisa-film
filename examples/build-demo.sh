#!/usr/bin/env bash
# 端到端示例：3 幕《蒙娜丽莎的一笑》→ 预览 + 正式成片
#
# 这条脚本用的是仓库内随附的示例母图（references/sample-pages/），
# 所以完全离线可跑；换成 Agent 生成或用户上传的图片走的是同一条链路。
set -euo pipefail

cd "$(dirname "$0")/.."
STORY="examples/story-monalisa.txt"
TITLE="蒙娜丽莎的一笑"
STYLE="colored-pencil-diary"

echo "== 1/5 规划分镜 =="
python3 scripts/run_story_video.py \
  --input "$STORY" --title "$TITLE" --style "$STYLE" --mode plan

BATCH=$(python3 -c "import json;print(json.load(open('.story-video/storyboard.plan.json'))['project']['batch'])")
echo "   批次目录：public/$BATCH"

echo "== 2/5 提供母图（此处直接复制示例页；实际流程由 Agent 生图） =="
mkdir -p "public/$BATCH"
cp references/sample-pages/01_master.png "public/$BATCH/01_master.png"
cp references/sample-pages/02_master.png "public/$BATCH/02_master.png"
cp references/sample-pages/03_master.png "public/$BATCH/03_master.png"

echo "== 3/5 导入并派生图层（彩色 / 本地线稿 / 字幕） =="
python3 scripts/run_story_video.py --mode import --force

echo "== 4/5 快速预览 720×960 =="
python3 scripts/run_story_video.py --mode preview --transition cut
cp renders/picture_silent-preview.mp4 renders/demo-cut-720x960.mp4

echo "== 5/5 正式成片 1080×1440 =="
python3 scripts/run_story_video.py --mode render --transition cut
cp renders/picture_silent.mp4 renders/demo-cut-1080x1440.mp4

echo "== 附加：翻书转场版本 =="
python3 scripts/run_story_video.py --mode render --transition page-flip
cp renders/picture_silent.mp4 renders/demo-pageflip-1080x1440.mp4

echo
echo "产物："
ls -la renders/*.mp4
