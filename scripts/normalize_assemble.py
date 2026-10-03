"""Normalize each approved clip to exactly 12.000s / 25 fps / 300 frames and
concatenate fifteen of them into a 180.000s / 4500-frame master.

Implements production spec (docs/制作与核查.md §5): never splice the raw 12.25s
sources directly. Final assembly is gated on an approval manifest; any clip not
explicitly approved keeps the pipeline blocked. No generation / API calls.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_FPS = 25
TARGET_FRAMES = 300          # 12.000 s at 25 fps
TARGET_DURATION = 12.0
FINAL_FRAMES = TARGET_FRAMES * 15   # 4500
FINAL_DURATION = TARGET_DURATION * 15  # 180.000


def resolve_ffmpeg():
    env = os.environ.get('FFMPEG')
    if env and Path(env).exists():
        return env
    vendored = ROOT / '.tools' / 'ffmpeg'
    if vendored.exists():
        return str(vendored)
    found = shutil.which('ffmpeg')
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'


FFMPEG = resolve_ffmpeg()


def _run(args):
    return subprocess.run(args, capture_output=True, text=True)


def probe(path):
    """Return {duration,fps,frames,width,height} using ffmpeg only (no ffprobe)."""
    path = str(path)
    info = _run([FFMPEG, '-hide_banner', '-i', path])
    meta = info.stderr
    dur = None
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', meta)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    fps = None
    m = re.search(r',\s*([\d.]+)\s*fps', meta)
    if m:
        fps = float(m.group(1))
    wh = None
    m = re.search(r'(\d{3,4})x(\d{3,4})', meta)
    if m:
        wh = (int(m.group(1)), int(m.group(2)))
    # Default verbosity so the final "frame= N" progress line is present.
    dec = _run([FFMPEG, '-hide_banner', '-i', path, '-map', '0:v:0', '-an', '-f', 'null', '-'])
    frames = None
    for m in re.finditer(r'frame=\s*(\d+)', dec.stderr):
        frames = int(m.group(1))
    return {'duration': dur, 'fps': fps, 'frames': frames,
            'width': wh[0] if wh else None, 'height': wh[1] if wh else None}


def normalize_clip(src, dst):
    """Re-encode one source to CFR 25fps, exactly 300 frames (12.000s), 1280x720."""
    src, dst = str(src), str(dst)
    cmd = [FFMPEG, '-y', '-v', 'error', '-i', src, '-an',
           '-vf', 'scale=1280:720:flags=bicubic,setsar=1,fps=%d' % TARGET_FPS,
           '-frames:v', str(TARGET_FRAMES),
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
           '-pix_fmt', 'yuv420p', dst]
    r = _run(cmd)
    if r.returncode != 0:
        raise SystemExit('normalize failed for %s:\n%s' % (src, r.stderr))
    return verify_clip(dst)


def verify_clip(path):
    p = probe(path)
    reasons = []
    if p['frames'] != TARGET_FRAMES:
        reasons.append('frames=%s!=%d' % (p['frames'], TARGET_FRAMES))
    if p['fps'] != TARGET_FPS:
        reasons.append('fps=%s!=%d' % (p['fps'], TARGET_FPS))
    if p['duration'] is None or abs(p['duration'] - TARGET_DURATION) > 0.05:
        reasons.append('duration=%s!=%s' % (p['duration'], TARGET_DURATION))
    if p['width'] != 1280 or p['height'] != 720:
        reasons.append('size=%sx%s' % (p['width'], p['height']))
    return {'path': str(path), 'probe': p, 'ok': not reasons, 'reasons': reasons}


def load_approval(path):
    data = json.loads(Path(path).read_text())
    return set(data.get('approved', []))


def assemble(norm_dir, out, approval_path):
    norm_dir = Path(norm_dir)
    approved = load_approval(approval_path)
    ids = ['%02d' % i for i in range(1, 16)]
    missing_approval = [i for i in ids if i not in approved]
    missing_files = [i for i in ids if not (norm_dir / (i + '.mp4')).exists()]
    if missing_approval or missing_files:
        raise SystemExit('Assembly blocked: unapproved=%s missing=%s. '
                         'Final 180s requires all 15 approved normalized clips.'
                         % (missing_approval or '[]', missing_files or '[]'))
    listfile = norm_dir / 'concat.txt'
    listfile.write_text(''.join("file '%s'\n" % (norm_dir / (i + '.mp4')) for i in ids))
    cmd = [FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listfile),
           '-c', 'copy', str(out)]
    r = _run(cmd)
    if r.returncode != 0:
        raise SystemExit('concat failed:\n%s' % r.stderr)
    p = probe(out)
    reasons = []
    if p['frames'] != FINAL_FRAMES:
        reasons.append('frames=%s!=%d' % (p['frames'], FINAL_FRAMES))
    if p['duration'] is None or abs(p['duration'] - FINAL_DURATION) > 0.1:
        reasons.append('duration=%s!=%s' % (p['duration'], FINAL_DURATION))
    return {'path': str(out), 'probe': p, 'ok': not reasons, 'reasons': reasons}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--normalize', action='store_true')
    ap.add_argument('--in', dest='src', default=str(ROOT / 'clips'))
    ap.add_argument('--norm', default=str(ROOT / 'work' / 'normalized'))
    ap.add_argument('--assemble', action='store_true')
    ap.add_argument('--out', default=str(ROOT / 'out' / 'film_180.mp4'))
    ap.add_argument('--approval', default=str(ROOT / 'review' / 'approval.json'))
    ap.add_argument('--scene', help='normalize a single scene id, e.g. 01')
    args = ap.parse_args()

    if args.normalize:
        norm = Path(args.norm)
        norm.mkdir(parents=True, exist_ok=True)
        ids = [args.scene] if args.scene else ['%02d' % i for i in range(1, 16)]
        for sid in ids:
            src = Path(args.src) / (sid + '.mp4')
            if not src.exists():
                print('::warning title=Missing source::%s absent; skip.' % sid)
                continue
            res = normalize_clip(src, norm / (sid + '.mp4'))
            print('%s -> %s' % (sid, 'OK' if res['ok'] else 'FAIL ' + ','.join(res['reasons'])))
    if args.assemble:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        res = assemble(args.norm, args.out, args.approval)
        print('assemble -> %s' % ('OK' if res['ok'] else 'FAIL ' + ','.join(res['reasons'])))
        if not res['ok']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
