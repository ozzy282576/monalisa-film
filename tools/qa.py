#!/usr/bin/env python3
"""qa.py — final QC battery for the finished MP4."""
import json, subprocess, sys, glob, os
import numpy as np
from PIL import Image

FF = subprocess.run(['python3', '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                    capture_output=True, text=True).stdout.strip()
FFPROBE = subprocess.run(['node', '-e', "console.log(require('@ffprobe-installer/ffprobe').path)"],
                         capture_output=True, text=True).stdout.strip()
OUT = 'output/lin_guoyun_1982_rainy_night_butcher_1080p.mp4'
T = json.load(open('build/timeline.json'))

fails = []
def check(name, ok, detail=''):
    print(('PASS' if ok else 'FAIL'), '-', name, ('| ' + str(detail)) if detail else '')
    if not ok:
        fails.append(name)

# ---- 1. container / streams -------------------------------------------------
probe = json.loads(subprocess.run([FFPROBE, '-v', 'error', '-show_streams', '-show_format',
                                   '-of', 'json', OUT], capture_output=True, text=True).stdout)
vs = [s for s in probe['streams'] if s['codec_type'] == 'video'][0]
aus = [s for s in probe['streams'] if s['codec_type'] == 'audio']
dur = float(probe['format']['duration'])
check('video codec h264', vs['codec_name'] == 'h264', vs['codec_name'])
check('pix_fmt yuv420p', vs['pix_fmt'] == 'yuv420p', vs['pix_fmt'])
check('resolution 1920x1080', (vs['width'], vs['height']) == (1920, 1080), f"{vs['width']}x{vs['height']}")
check('fps 24', vs['r_frame_rate'] == '24/1', vs['r_frame_rate'])
check('audio stream aac 44.1k', len(aus) == 1 and aus[0]['codec_name'] == 'aac' and aus[0]['sample_rate'] == '44100',
      aus[0]['codec_name'] + ' ' + aus[0]['sample_rate'] if aus else 'none')
check('duration ~timeline', abs(dur - T['total']) < 0.6, f'{dur:.2f} vs {T["total"]:.2f}')

# ---- 2. frame integrity (1 fps sample) --------------------------------------
os.makedirs('/tmp/qa_frames', exist_ok=True)
for f in glob.glob('/tmp/qa_frames/*.png'):
    os.remove(f)
subprocess.run([FF, '-v', 'error', '-y', '-i', OUT, '-vf', 'fps=1', '/tmp/qa_frames/q%03d.png'],
               capture_output=True, text=True)
frames = sorted(glob.glob('/tmp/qa_frames/q*.png'))
means, stds = [], []
for f in frames:
    a = np.asarray(Image.open(f).convert('L'), dtype=np.float32)
    means.append(a.mean())
    stds.append(a.std())
means, stds = np.array(means), np.array(stds)
times1 = np.arange(len(frames))
check('no dead-black seconds (outside fades/flashes)',
      sum(1 for i, (m, s) in enumerate(zip(means, stds))
          if m < 5 and not (times1[i] < 0.5 or times1[i] > T['total'] - 1.3) and m < 170) == 0,
      f'min mean {means.min():.1f}')
check('no flat/frozen frames (outside fades/flashes)',
      sum(1 for i, s in enumerate(stds)
          if s < 7 and means[i] < 170 and not (times1[i] < 0.5 or times1[i] > T['total'] - 1.3)) == 0,
      'flashes & fades excluded')
# flash verification at 8 fps against designed event times
for f in glob.glob('/tmp/qa_frames/h*.png'):
    os.remove(f)
subprocess.run([FF, '-v', 'error', '-y', '-i', OUT, '-vf', 'fps=8,scale=480:270', '/tmp/qa_frames/h%04d.png'],
               capture_output=True, text=True)
hframes = sorted(glob.glob('/tmp/qa_frames/h*.png'))
ht = []
for i, f in enumerate(hframes):
    a = np.asarray(Image.open(f).convert('L'), dtype=np.float32)
    ht.append((i / 8.0, a.mean()))
det = [t for t, m in ht if m > 165]
clusters = []
for t in det:
    if clusters and t - clusters[-1][-1] <= 0.5:
        clusters[-1].append(t)
    else:
        clusters.append([t])
detected = [c[0] for c in clusters]
expected = []
for e in sorted(T['flashes']):
    if not expected or e - expected[-1] > 0.2:
        expected.append(e)
spurious = [d for d in detected if not any(abs(d - e) <= 0.6 for e in expected)]
# precise per-event check: seek exactly to each designed flash time
missed = []
for e in expected:
    outb = subprocess.run([FF, '-v', 'error', '-ss', f'{max(0, e - 0.06):.3f}', '-i', OUT, '-frames', '4',
                           '-vf', 'scale=480:270', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                          capture_output=True).stdout
    arr = np.frombuffer(outb, dtype=np.uint8).reshape(-1, 270 * 480)
    m = float(arr.mean(axis=1).max())
    if m < 150:
        missed.append((round(e, 2), round(m, 1)))
check('all designed flashes present (seek-verified)', len(missed) == 0, f'{len(expected) - len(missed)}/{len(expected)}, missed={missed[:4]}')
check('no spurious white frames', len(spurious) == 0, f'spurious={spurious[:4]}')
# consecutive-duplicate detection (skip flash frames)
dup = 0
prev = None
for i, f in enumerate(frames):
    if means[i] > 170:
        prev = None
        continue
    a = np.asarray(Image.open(f).convert('L'), dtype=np.float32)[::8, ::8]
    if prev is not None and np.abs(a - prev).mean() < 0.4:
        dup += 1
    prev = a
check('no frozen consecutive seconds', dup == 0, f'{dup} dup pairs')

# ---- 3. glyph coverage (no tofu possible) -----------------------------------
cov = subprocess.run(['node', 'tools/coverage.js'], capture_output=True, text=True).stdout.strip()
check('glyph coverage complete', cov == '[]', cov)

# ---- 4. audio health ---------------------------------------------------------
raw = subprocess.run([FF, '-v', 'error', '-i', OUT, '-f', 's16le', '-ac', '1', '-ar', '8000', '-'],
                     capture_output=True).stdout
sig = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
check('audio peak below clipping', np.abs(sig).max() < 32600, f'peak {np.abs(sig).max():.0f}')
win = 8000
rms = np.array([np.sqrt((sig[i:i+win] ** 2).mean()) for i in range(0, len(sig) - win, win)])
quiet = [i for i, r in enumerate(rms) if r < 120]
# quiet windows allowed only inside gaps (0.35s) or final fade; flag any quiet *segment* second
bad = []
for s in T['segs']:
    i0, i1 = int(s['start']) + 1, int(s['start'] + s['dur']) - 1
    for i in range(i0, min(i1, len(rms))):
        if rms[i] < 120:
            bad.append(i)
check('narration present across all segments', len(bad) == 0, f'quiet seconds at {bad[:6]}')
ebur = subprocess.run([FF, '-v', 'info', '-i', OUT, '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'],
                      capture_output=True, text=True).stderr
import re
m = re.search(r'I:\s+(-?\d+\.?\d*)\s+LUFS', ebur)
lufs = float(m.group(1)) if m else -99
check('loudness broadcast-safe (-20..-10 LUFS)', -20 <= lufs <= -10, f'{lufs} LUFS')

print()
if fails:
    print('QA FAILED:', fails)
    sys.exit(1)
print('QA ALL PASS —', len(frames), 'sampled seconds checked')
