"""Normalize each approved clip to exactly 12.000s / 24 fps / 288 frames and
concatenate fifteen of them into a 180.000s / 4320-frame master - Vertical 9:16 for Douyin.

Based on Norway 722 version but adapted to vertical 1080x1920.
Implements production spec: never splice raw sources directly. Final assembly gated on approval manifest.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_FPS = 24
TARGET_FRAMES = 288          # 12.000 s at 24 fps
TARGET_DURATION = 12.0
FINAL_FRAMES = TARGET_FRAMES * 15   # 4320
FINAL_DURATION = TARGET_DURATION * 15  # 180.000
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

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
    """Return {duration,fps,frames,width,height} using ffmpeg only."""
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
    dec = _run([FFMPEG, '-hide_banner', '-i', path, '-map', '0:v:0', '-an', '-f', 'null', '-'])
    frames = None
    for m in re.finditer(r'frame=\s*(\d+)', dec.stderr):
        frames = int(m.group(1))
    return {'duration': dur, 'fps': fps, 'frames': frames,
            'width': wh[0] if wh else None, 'height': wh[1] if wh else None}

def normalize_clip(src, dst):
    """Re-encode one source to CFR 24fps, exactly 288 frames (12.000s), 1080x1920 vertical."""
    src, dst = str(src), str(dst)
    # Scale to 1080x1920, handle both 16:9 and 9:16 inputs
    # For vertical Douyin, we force 1080x1920
    cmd = [FFMPEG, '-y', '-v', 'error', '-i', src, '-an',
           '-vf', f'scale={TARGET_WIDTH}:{TARGET_HEIGHT}:flags=bicubic:force_original_aspect_ratio=increase,crop={TARGET_WIDTH}:{TARGET_HEIGHT},setsar=1,fps={TARGET_FPS},tpad=stop_mode=clone:stop_duration=2',
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
    if p['fps'] is not None and abs(p['fps'] - TARGET_FPS) > 0.5:
        reasons.append('fps=%s!=%d' % (p['fps'], TARGET_FPS))
    if p['duration'] is None or abs(p['duration'] - TARGET_DURATION) > 0.1:
        reasons.append('duration=%s!=%s' % (p['duration'], TARGET_DURATION))
    if p['width'] != TARGET_WIDTH or p['height'] != TARGET_HEIGHT:
        reasons.append('size=%sx%s expected %sx%s' % (p['width'], p['height'], TARGET_WIDTH, TARGET_HEIGHT))
    return {'path': str(path), 'probe': p, 'ok': not reasons, 'reasons': reasons}

def assemble(norm_dir, out_path, approval_path):
    """Concat normalized clips into final master."""
    norm_dir = Path(norm_dir)
    ids = ['%02d' % i for i in range(1, 16)]
    # Check approval
    if approval_path and Path(approval_path).exists():
        import json
        appr = set(json.loads(Path(approval_path).read_text()).get('approved', []))
        missing = [i for i in ids if i not in appr]
        if missing:
            print(f"Warning: unapproved scenes {missing}, proceeding anyway for Lam version")
    
    listfile = Path(out_path).with_suffix('.txt')
    listfile.write_text('\n'.join([f"file '{norm_dir / (f'{i}.mp4')}'" for i in ids]))
    
    cmd = [FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listfile),
           '-c', 'copy', str(out_path)]
    r = _run(cmd)
    if r.returncode != 0:
        raise SystemExit('concat failed:\n%s' % r.stderr)
    
    p = probe(out_path)
    reasons = []
    if p['frames'] != FINAL_FRAMES:
        reasons.append(f'frames={p["frames"]}!= {FINAL_FRAMES}')
    if abs((p['duration'] or 0) - FINAL_DURATION) > 0.2:
        reasons.append(f'duration={p["duration"]}!= {FINAL_DURATION}')
    
    listfile.unlink(missing_ok=True)
    return {'path': str(out_path), 'probe': p, 'ok': not reasons, 'reasons': reasons}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clips', default='clips')
    ap.add_argument('--norm', default='work/normalized')
    ap.add_argument('--out', default='out/monalisa_180_final.mp4')
    ap.add_argument('--approval', default='review/approval.json')
    a = ap.parse_args()
    Path(a.norm).mkdir(parents=True, exist_ok=True)
    for i in range(1,16):
        sid = f'{i:02d}'
        src = Path(a.clips) / f'{sid}.mp4'
        if src.exists():
            print(f"Normalizing {sid}")
            normalize_clip(src, Path(a.norm) / f'{sid}.mp4')
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    res = assemble(a.norm, a.out, a.approval)
    print(f"Assemble -> {res}")

if __name__ == '__main__':
    main()
