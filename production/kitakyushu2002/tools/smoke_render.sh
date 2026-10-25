#!/usr/bin/env bash
# 出片前的本地冒烟测试（手册第 8 步）：用假素材把整条 render.py 跑通，几分钟，不烧任何额度。
#
#   bash production/kitakyushu2002/tools/smoke_render.sh            # 1920×1080（默认，必须）
# 注意：成片阶段有一个固定在水印位置的 delogo（x=1746 起），输出宽度小于 1918 会让它越界报错，
#       所以本地冒烟也请用 1920×1080；只有中间那些 46 个分段是无所谓尺寸的。
#
# 它做的事（与真实出片完全同一条代码路径，仓库里的东西一个字节都不动）：
#   1. 把本项目**复制**到 /tmp/kanghosun-smoke/project（真的 story.json 照用）；
#   2. 造 38 个 6 秒假片段（ffmpeg testsrc2，1792×1024 / 24 fps，与智谱免费档输出同规格）；
#   3. 按 generate_cogvideox.request_hash() 与文件 SHA-256 伪造 results.json（只写在 /tmp）；
#   4. 造 6 段假配音（正弦音，28.5 s/段）与对应的 audio/manifest.json（SHA-256 对齐）；
#   5. 跑 render.py --skip-asr：CUTS/EDL 唯一性断言、7 张信息卡与片头片尾卡排字、
#      六段混音、字幕时间轴、成品技术校验与「成品必须可听」闸门。
#
# 依赖：ffmpeg（没有时用 imageio-ffmpeg 自带的静态版）、python 包 numpy/pillow(/av)。
set -euo pipefail
cd "$(dirname "$0")/../../.."
W=${1:-1920}
H=${2:-1080}
ROOT="$(pwd)"
WORK=/tmp/kanghosun-smoke
PROJ="$WORK/prod/kitakyushu2002"   # 摆成 <root>/production/<slug>，让 generate.py 的 parents[2] 解析得对

if ! command -v ffmpeg >/dev/null 2>&1; then
  FF="$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"
  mkdir -p /tmp/ffshim && ln -sf "$FF" /tmp/ffshim/ffmpeg
  export PATH="/tmp/ffshim:$PATH"
fi
rm -rf "$WORK"
mkdir -p "$WORK/fake" "$WORK/work" "$PROJ"
cp -r production/kitakyushu2002/. "$PROJ/"
rm -rf "$PROJ/cast" "$PROJ/tools"
# generate.py 会把 <root>/production 插进 sys.path 去 import agnes_video，副本里也照配一份
mkdir -p "$WORK/production"
cp production/agnes_video.py "$WORK/production/"
# render.py 在 <root>/.cache/fonts 找 Noto CJK；本机没有 fonts-noto-cjk 时用 mplfonts 自带的同款字体顶上
# BGM 合成器在 电影解说工具包/ 下（render.py 靠 ROOT/电影解说工具包 找它）；副本里照配一份
mkdir -p "$WORK/电影解说工具包"
cp 电影解说工具包/generate_horror_bgm.py "$WORK/电影解说工具包/"
mkdir -p "$WORK/.cache/fonts"
for f in NotoSansCJKsc-Regular.otf NotoSerifCJKsc-Regular.otf; do
  if [ -f ".cache/fonts/$f" ]; then cp ".cache/fonts/$f" "$WORK/.cache/fonts/"; continue; fi
  python3 - "$WORK" "$f" <<'PYFONT' || true
import pathlib, shutil, sys
try:
    import mplfonts
except ImportError:
    sys.exit(0)
src = pathlib.Path(mplfonts.__file__).parent / 'fonts' / sys.argv[2]
if src.exists():
    shutil.copy(src, pathlib.Path(sys.argv[1]) / '.cache/fonts' / sys.argv[2])
    print('font seeded from mplfonts:', src.name)
PYFONT
done

python3 - "$ROOT" "$PROJ" "$WORK" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
root, proj, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
fake = work / 'fake'
sys.path.insert(0, str(proj))
import generate_cogvideox as gen

project = json.loads((proj / 'story.json').read_text())
shots = [s for s in project['shots'] if s['kind'] != 'graphic']

for shot in shots:
    out = fake / f"{shot['id']}.mp4"
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=1792x1024:rate=24', '-t', '6', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(out)], check=True)

receipts = {}
for shot in shots:
    path = fake / f"{shot['id']}.mp4"
    receipts[shot['id']] = {
        'id': shot['id'], 'status': 'completed',
        'request_hash': gen.request_hash(project, shot),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes': path.stat().st_size,
        'video_url': f'https://example.invalid/{shot["id"]}.mp4',
    }
(work / 'results.json').write_text(json.dumps(
    {'project': project['title'], 'model': 'cogvideox-flash', 'shots': receipts},
    ensure_ascii=False, indent=2) + '\n')

# 假配音：每章 28.5 s 正弦音（够长、可测得出电平），manifest 的 SHA-256 与文件一致
# 设 SMOKE_REAL_AUDIO=1 时改用仓库里真实的 N0x.mp3（那就不造假的），用来验证
# 「clause-times 分句字幕」这条路径（假音和分句表对不上，会退回估算）。
import os
audio = proj / 'audio'
if os.environ.get('SMOKE_REAL_AUDIO') == '1':
    print('SMOKE_REAL_AUDIO=1：保留真实配音与 clause-times.json')
    sys.exit(0)
manifest = json.loads((audio / 'manifest.json').read_text())
for clip in manifest['clips']:
    out = audio / clip['file']
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=210:sample_rate=48000:duration=28.5',
                    '-c:a', 'libmp3lame', '-b:a', '192k', str(out)], check=True)
    clip['sha256'] = hashlib.sha256(out.read_bytes()).hexdigest()
(audio / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(f'假素材 {len(shots)} 镜 + 伪造 results.json + 6 段假配音就绪')
PY

python3 "$PROJ/render.py" \
  --sources "$WORK/fake" --work "$WORK/work" --output "$WORK/out.mp4" \
  --project "$PROJ/story.json" --results "$WORK/results.json" --audio "$PROJ/audio" \
  --skip-asr --width "$W" --height "$H"

echo
echo "冒烟测试通过：$WORK/out.mp4"
echo "技术报告：$WORK/work/technical-report.json ；字幕：$WORK/work/captions.srt ；接触表：$WORK/work/final-contact.jpg"
