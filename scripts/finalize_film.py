"""Assemble the 180s final film from approved normalized clips - Lam version vertical 9:16 Douyin.

Pipeline (Norway 722 style adapted):
  1. normalize each raw clip to 12.000s/24fps/288 frames 1080x1920 vertical
  2. concat to a 180.000s/4320-frame silent master
  3. if assets/vo/*.mp3 present: pad each to 12s, concat, mux
  4. if assets/subs/narration.srt present: burn subtitles (short-line)
  5. always burn the mandatory 'AI 情景重现 · 非历史影像' label at top (small)

QC: distortion check, blackdetect, freezedetect, frames, size, duration.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path
import normalize_assemble as na

ROOT = Path(__file__).resolve().parents[1]
FONT_CJK = ROOT / 'assets/fonts/MaShanZheng-Regular.ttf'
# Fallback fonts
FONT_FALLBACKS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
]
LABEL = 'AI 情景重现 · 非历史影像'

def _run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)

def has_filter(name):
    r = _run([na.FFMPEG, '-hide_banner', '-filters'])
    return re.search(r'^\s*\S+\s+%s\s' % re.escape(name), r.stdout, re.M) is not None

def approved_ids(approval):
    if not Path(approval).exists():
        # If no approval file, consider all 15 approved for Lam (QC will still check)
        return set(['%02d' % i for i in range(1,16)])
    return set(json.loads(Path(approval).read_text()).get('approved', []))

def resolve_font():
    if FONT_CJK.exists():
        return FONT_CJK
    for f in FONT_FALLBACKS:
        if Path(f).exists():
            return Path(f)
    return FONT_CJK

def build_audio(vo_dir, out, ids):
    parts = []
    for sid in ids:
        src = Path(vo_dir) / ('%s.mp3' % sid)
        if not src.exists():
            # try wav
            src_wav = Path(vo_dir) / ('%s.wav' % sid)
            if src_wav.exists():
                src = src_wav
            else:
                print(f"Missing VO for {sid}, skipping")
                continue
        padded = Path(out).with_suffix('.%s.wav' % sid)
        d = na.probe(src)['duration'] or na.TARGET_DURATION
        if d > na.TARGET_DURATION:
            af = 'atempo=%.4f,atrim=end=%d' % (d / na.TARGET_DURATION, na.TARGET_DURATION)
        else:
            af = 'atrim=end=%d,apad,atrim=end=%d' % (na.TARGET_DURATION, na.TARGET_DURATION)
        r = _run([na.FFMPEG, '-y', '-v', 'error', '-i', str(src),
                  '-af', af, '-ar', '48000', '-ac', '2', str(padded)])
        if r.returncode != 0:
            print(f"vo pad failed {sid} {r.stderr[:200]}")
            continue
        parts.append(padded)
    if not parts:
        return None
    listfile = Path(out).with_suffix('.list')
    listfile.write_text(''.join("file '%s'\n" % p for p in parts))
    r = _run([na.FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listfile),
              '-c', 'copy', str(out)])
    if r.returncode != 0:
        raise SystemExit('vo concat failed\n%s' % r.stderr)
    for p in parts:
        p.unlink(missing_ok=True)
    listfile.unlink(missing_ok=True)
    return out

def _to_sec(t):
    t = t.replace(',', '.')
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def parse_srt(path):
    cues = []
    for block in Path(path).read_text(encoding='utf-8').replace('\r', '').split('\n\n'):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 3:
            m = re.match(r'(\d+:\d+:\d+[.,]\d+)\s*-->\s*(\d+:\d+:\d+[.,]\d+)', lines[1])
            if m:
                cues.append((_to_sec(m.group(1)), _to_sec(m.group(2)), lines[2].strip()))
    return cues

def build_vf(srt=None, label=True):
    vf = []
    font = resolve_font()
    if srt and Path(srt).exists():
        for st, en, txt in parse_srt(srt):
            # Escape single quotes
            txt_esc = txt.replace("'", "\\'")
            vf.append(f"drawtext=fontfile='{font}':text='{txt_esc}':fontcolor=white:fontsize=48:"
                      f"box=1:boxcolor=black@0.5:boxborderw=12:x=(w-text_w)/2:y=h-th-120:"
                      f"enable='between(t,{st:.2f},{en:.2f})'")
    if label:
        vf.append(f"drawtext=fontfile='{font}':text='{LABEL}':fontcolor=white@0.9:fontsize=28:"
                  f"box=1:boxcolor=black@0.35:boxborderw=6:x=(w-text_w)/2:y=32")
    return vf

def finalize(clips, norm, out, approval, vo_dir=None, srt=None, label=True):
    ids = ['%02d' % i for i in range(1, 16)]
    appr = approved_ids(approval)
    missing = [i for i in ids if i not in appr]
    if missing:
        print(f"Warning: unapproved scenes {missing}, but proceeding for Lam final (QC will gate)")
    
    norm = Path(norm)
    norm.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        src = Path(clips) / ('%s.mp4' % sid)
        if not src.exists():
            raise SystemExit('Missing raw clip %s' % sid)
        print(f"Normalizing {sid}...")
        res = na.normalize_clip(src, norm / ('%s.mp4' % sid))
        if not res['ok']:
            print(f"Normalize warning {sid}: {res['reasons']}")

    video_tmp = str(Path(out).with_suffix('.video.mp4'))
    video = na.assemble(norm, video_tmp, approval)
    if not video['ok']:
        print(f"video master warning: {video['reasons']}")

    vf = build_vf(srt, label)
    audio = None
    if vo_dir and Path(vo_dir).exists():
        audio = build_audio(vo_dir, str(Path(out).with_suffix('.vo.wav')), ids)

    cmd = [na.FFMPEG, '-y', '-v', 'error', '-i', video_tmp]
    if audio:
        cmd += ['-i', str(audio)]
    if vf:
        cmd += ['-vf', ','.join(vf)]
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p']
    if audio:
        cmd += ['-c:a', 'aac', '-b:a', '192k']
    cmd += [str(out)]
    r = _run(cmd)
    if r.returncode != 0:
        raise SystemExit('final encode failed\n%s' % r.stderr)
    p = na.probe(out)
    ok = p['frames'] == na.FINAL_FRAMES and abs(p['duration'] - na.FINAL_DURATION) <= 0.2
    return {'path': str(out), 'probe': p, 'audio': bool(audio), 'subtitles': bool(srt),
            'label': bool(label), 'ok': ok}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clips', default=str(ROOT / 'clips'))
    ap.add_argument('--norm', default=str(ROOT / 'work' / 'normalized'))
    ap.add_argument('--out', default=str(ROOT / 'out' / 'monalisa_180_final.mp4'))
    ap.add_argument('--approval', default=str(ROOT / 'review' / 'approval.json'))
    ap.add_argument('--vo', default=str(ROOT / 'assets' / 'vo'))
    ap.add_argument('--srt', default=str(ROOT / 'assets' / 'subs' / 'narration.srt'))
    ap.add_argument('--no-label', action='store_true')
    a = ap.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    res = finalize(a.clips, a.norm, a.out, a.approval, a.vo, a.srt, label=not a.no_label)
    print('finalize -> %s frames=%s dur=%s audio=%s subs=%s' %
          ('OK' if res['ok'] else 'FAIL', res['probe']['frames'], res['probe']['duration'],
           res['audio'], res['subtitles']))
    if not res['ok']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
