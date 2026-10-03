"""Assemble the 180s final film from approved normalized clips, optional VO and
subtitles, burning the mandatory 'AI 情景重现 · 非历史影像' label.

Pipeline (all gated on review/approval.json having all 15 ids):
  1. normalize each raw clip to 12.000s/25fps/300 frames (normalize_assemble)
  2. concat to a 180.000s/4500-frame silent master
  3. if assets/vo/*.mp3 present: pad each to 12s, concat, mux
  4. if assets/subs/narration.srt present: burn subtitles
  5. always burn the persistent AI-reconstruction label
No generation / API calls. Refuses to run unless every scene is approved.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import normalize_assemble as na

ROOT = Path(__file__).resolve().parents[1]
FONT_CJK = ROOT / 'assets/fonts/MaShanZheng-Regular.ttf'
LABEL = 'AI 情景重现 · 非历史影像'

# Documented localized cleanups for residual generator artifacts that prompts
# could not eliminate (tiny mast pennant). Applied as delogo before concat.
POSTFIX = {
    '07': [("between(t,0,6)", 860, 0, 140, 120)],   # bare-mast: remove residual pennant at mast top
}


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def has_filter(name):
    r = _run([na.FFMPEG, '-hide_banner', '-filters'])
    return re.search(r'^\s*\S+\s+%s\s' % re.escape(name), r.stdout, re.M) is not None


def approved_ids(approval):
    return set(json.loads(Path(approval).read_text()).get('approved', []))


def apply_postfix(path, fixes):
    """In-place localized delogo cleanups (documented residual-artifact removal)."""
    vf = ','.join("delogo=x=%d:y=%d:w=%d:h=%d:enable='%s'" % (x, y, w, h, en)
                  for (en, x, y, w, h) in fixes)
    tmp = str(path) + '.pf.mp4'
    r = _run([na.FFMPEG, '-y', '-v', 'error', '-i', str(path), '-vf', vf,
              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
              '-pix_fmt', 'yuv420p', '-an', tmp])
    if r.returncode != 0:
        raise SystemExit('postfix failed %s\n%s' % (path, r.stderr))
    Path(tmp).replace(path)


def build_audio(vo_dir, out, ids):
    """Pad each VO to exactly 12s and concat into one 180s track."""
    parts = []
    for sid in ids:
        src = Path(vo_dir) / ('%s.mp3' % sid)
        if not src.exists():
            raise SystemExit('Missing VO for %s' % sid)
        padded = Path(out).with_suffix('.%s.wav' % sid)
        r = _run([na.FFMPEG, '-y', '-v', 'error', '-i', str(src),
                  '-af', 'atrim=end=%d,apad,atrim=end=%d' % (na.TARGET_DURATION, na.TARGET_DURATION),
                  '-ar', '48000', '-ac', '2', str(padded)])
        if r.returncode != 0:
            raise SystemExit('vo pad failed %s\n%s' % (sid, r.stderr))
        parts.append(padded)
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


def build_vf(srt=None, label=True):
    vf = []
    if srt and Path(srt).exists():
        vf.append("subtitles='%s':fontsdir='%s'" % (Path(srt).resolve(), (ROOT / 'assets/fonts').resolve()))
    if label and FONT_CJK.exists():
        vf.append("drawtext=fontfile='%s':text='%s':fontcolor=white@0.85:fontsize=28:"
                  "box=1:boxcolor=black@0.35:boxborderw=8:x=(w-text_w)/2:y=h-th-24" % (FONT_CJK, LABEL))
    return vf


def finalize(clips, norm, out, approval, vo_dir=None, srt=None, label=True):
    ids = ['%02d' % i for i in range(1, 16)]
    appr = approved_ids(approval)
    missing = [i for i in ids if i not in appr]
    if missing:
        raise SystemExit('Finalize blocked: unapproved scenes %s. '
                         'All 15 must be approved before a final cut.' % missing)
    norm = Path(norm)
    norm.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        src = Path(clips) / ('%s.mp4' % sid)
        if not src.exists():
            raise SystemExit('Missing raw clip %s' % sid)
        na.normalize_clip(src, norm / ('%s.mp4' % sid))
        if sid in POSTFIX:
            apply_postfix(norm / ('%s.mp4' % sid), POSTFIX[sid])
            print('postfix applied:', sid)
    video = na.assemble(norm, str(Path(out).with_suffix('.video.mp4')), approval)
    if not video['ok']:
        raise SystemExit('video master invalid: %s' % video['reasons'])

    vf = build_vf(srt, label)
    audio = None
    if vo_dir and Path(vo_dir).exists() and any((Path(vo_dir) / ('%s.mp3' % i)).exists() for i in ids):
        audio = build_audio(vo_dir, str(Path(out).with_suffix('.vo.wav')), ids)

    cmd = [na.FFMPEG, '-y', '-v', 'error', '-i', str(Path(out).with_suffix('.video.mp4'))]
    if audio:
        cmd += ['-i', str(audio)]
    if vf:
        cmd += ['-vf', ','.join(vf)]
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p']
    if audio:
        cmd += ['-c:a', 'aac', '-b:a', '192k', '-shortest']
    cmd += [str(out)]
    r = _run(cmd)
    if r.returncode != 0:
        raise SystemExit('final encode failed\n%s' % r.stderr)
    p = na.probe(out)
    ok = p['frames'] == na.FINAL_FRAMES and abs(p['duration'] - na.FINAL_DURATION) <= 0.1
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
