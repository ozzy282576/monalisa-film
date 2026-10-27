#!/usr/bin/env bash
# 出片前的本地冒烟测试（手册第 8 步）：用假素材把整条 render.py 跑通，1–5 分钟，不烧 Agnes 额度。
#
#   bash production/raincoat2004/tools/smoke_render.sh            # 960×540 快速版
#   bash production/raincoat2004/tools/smoke_render.sh 1280 720   # 指定输出尺寸
#
# 它做的事（与本片真实出片完全同一条代码路径）：
#   1. 造 38 个 7 秒假片段（ffmpeg testsrc2，24 fps 1080p），文件名与镜头号一一对应；
#   2. 按 generate.request_hash() 与文件 SHA-256 伪造一份 **放在 /tmp 的** results.json
#      （绝不碰仓库里的真 results.json —— 真的那份由 Actions 写回）；
#   3. 跑 render.py --skip-asr：CUTS/EDL 唯一性断言、7 张信息卡与片头片尾卡排字、
#      六段配音混音、字幕时间轴、成品技术校验与「成品必须可听」闸门。
#
# 依赖：ffmpeg（没有时用 imageio-ffmpeg 自带的静态版）、python 包 numpy/pillow(/av)。
set -euo pipefail
cd "$(dirname "$0")/../../.."
W=${1:-960}
H=${2:-720}
WORK=/tmp/raincoat-smoke

if ! command -v ffmpeg >/dev/null 2>&1; then
  FF="$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"
  mkdir -p /tmp/ffshim && ln -sf "$FF" /tmp/ffshim/ffmpeg
  export PATH="/tmp/ffshim:$PATH"
fi
mkdir -p "$WORK/fake" "$WORK/work"
rm -f "$WORK/fake"/*.mp4

python3 - "$WORK" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
work = Path(sys.argv[1]); fake = work / 'fake'
sys.path.insert(0, 'production/raincoat2004')
import generate
project = json.loads(Path('production/raincoat2004/story.json').read_text())
shots = [s for s in project['shots'] if s['kind'] == 'agnes']
for shot in shots:
    out = fake / f"{shot['id']}.mp4"
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=1920x1080:rate=24', '-t', '7', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(out)], check=True)
receipts = {}
for shot in shots:
    path = fake / f"{shot['id']}.mp4"
    receipts[shot['id']] = {
        'id': shot['id'], 'status': 'completed',
        'request_hash': generate.request_hash(project, shot),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes': path.stat().st_size,
        'video_url': f'https://example.invalid/{shot["id"]}.mp4',
        'reused_existing_asset': False,
    }
(work / 'results.json').write_text(json.dumps(
    {'project': project['title'], 'model': 'agnes-video-v2.0', 'shots': receipts},
    ensure_ascii=False, indent=2) + '\n')
print(f'假素材 {len(shots)} 镜 + 伪造 results.json 就绪')
PY

python3 production/raincoat2004/render.py \
  --sources "$WORK/fake" --work "$WORK/work" --output "$WORK/out.mp4" \
  --results "$WORK/results.json" --skip-asr --width "$W" --height "$H"

echo
echo "冒烟测试通过：$WORK/out.mp4"
echo "技术报告：$WORK/work/technical-report.json ；字幕：$WORK/work/captions.srt ；接触表：$WORK/work/final-contact.jpg"
