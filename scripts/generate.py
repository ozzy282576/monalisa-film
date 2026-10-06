"""Serial Agnes generation - Lam Guoyun version, Norway 722 style.
Secrets stay in Actions; media stays in artifacts.
Machine QC is NOT approval of anatomy, historical accuracy or audio sync.
Based on Norway 722 workflow (arena/01a10095), adapted for Hong Kong 1982 rainy night, 9:16 vertical for Douyin.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
CLIPS = ROOT / 'clips'
# 使用与挪威722相同的API endpoint
BASE = 'https://apihub.agnes-ai.com'
MODEL = 'agnes-video-2.5-flash'
MAX_TRIES = int(os.environ.get('AGNES_MAX_TRIES', '50'))
if not 1 <= MAX_TRIES <= 200:
    raise ValueError('AGNES_MAX_TRIES must be between 1 and 200')
GAP = 75

def save(state):
    WORK.mkdir(exist_ok=True)
    tmp = WORK / 'state.tmp'
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(WORK / 'state.json')

def api(method, path, key, payload=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True)

def qc(path, sid):
    """Machine QC - same as Norway 722 but adapted for 9:16 vertical"""
    data = json.loads(run('ffprobe', '-v', 'error', '-show_streams', '-show_format',
                          '-of', 'json', str(path)).stdout)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    duration = float(video.get('duration', data['format']['duration']))
    reasons = []
    if path.stat().st_size < 80000:
        reasons.append('small_file')
    if not 11.95 <= duration <= 12.6:
        reasons.append('duration_outside_normalizable_range')
    # 适配9:16垂直，挪威是16:9，这里允许9:16
    # 720P vertical = 720x1280, 1080P vertical = 1080x1920
    # 检查是否为9:16
    aspect = video['width'] / video['height']
    is_9_16 = abs(aspect - 9/16) < 0.02
    is_16_9 = abs(aspect - 16/9) < 0.02
    if not (is_9_16 or is_16_9):
        reasons.append('resolution_or_aspect')
    if video['width'] < 720 or video['height'] < 720:
        reasons.append('resolution_too_small')
    decode = run('ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-')
    if decode.stderr.strip():
        reasons.append('decode_errors')
    scan = run('ffmpeg', '-hide_banner', '-i', str(path), '-vf',
               'blackdetect=d=0.5:pic_th=0.98,freezedetect=n=-50dB:d=2', '-an', '-f', 'null', '-')
    if 'black_start:' in scan.stderr:
        reasons.append('black_interval')
    if 'freeze_start:' in scan.stderr:
        reasons.append('freeze_interval')
    folder = WORK / 'frames' / sid
    folder.mkdir(parents=True, exist_ok=True)
    for second in (1, 3, 5, 7, 9, 11):
        run('ffmpeg', '-v', 'error', '-y', '-ss', str(second), '-i', str(path),
            '-frames:v', '1', str(folder / f'{second:02}.jpg'))
    report = {'duration': duration, 'bytes': path.stat().st_size,
              'width': video['width'], 'height': video['height'],
              'machine_qc': 'fail' if reasons else 'pass', 'reasons': reasons,
              'anatomy_review': 'pending', 'temporal_review': 'pending',
              'historical_review': 'pending', 'audio_subtitle_sync': 'not_started'}
    (WORK / f'qc-{sid}.json').write_text(json.dumps(report, indent=2))
    return not reasons

def cooldown():
    print('Cooldown: 75 seconds (Norway 722 style)', flush=True)
    time.sleep(GAP)

def collect_one(item, state, key, create_window=None):
    """Collect raw media only; never call QC in this phase - Norway 722 style"""
    sid = item['id']
    st = state.setdefault(sid, {'tries': 0, 'status': 'pending'})
    dest = CLIPS / (sid + '.mp4')
    if st['status'] in ('downloaded', 'machine_pass') and dest.exists():
        print(f'Clip {sid}: raw file retained, QC deferred', flush=True)
        return
    if st['status'] in ('submission_uncertain', 'submitting'):
        raise SystemExit('Prior create outcome uncertain; reconcile provider task before resuming.')
    initial_tries = st.get('tries', 0)
    while True:
        if not st.get('video_id'):
            if st['tries'] >= MAX_TRIES:
                st['status'] = 'exhausted'
                save(state)
                print(f'::warning title=Clip {sid} exhausted::{MAX_TRIES} attempts used; no video. Continue to next scene.', flush=True)
                return False
            if create_window is not None and st['tries'] - initial_tries >= create_window:
                save(state)
                print(f'::notice title=Checkpoint handoff::Clip {sid}: {st["tries"]}/{MAX_TRIES}; next serial job will continue.', flush=True)
                return None
            st['tries'] += 1
            st['status'] = 'submitting'
            save(state)
            print(f'Clip {sid}, create attempt {st["tries"]}/{MAX_TRIES}', flush=True)
            try:
                # 林过云版改为9:16垂直，1080x1920，抖音
                body = api('POST', '/v1/videos', key, {
                    'model': MODEL, 'prompt': item['prompt'], 'seconds': '12',
                    'mode': 'text', 'size': '1080P', 'aspect_ratio': '9:16'})
            except urllib.error.HTTPError as e:
                st['status'] = 'create_rejected'
                st['http_code'] = e.code
                save(state)
                print(f'Clip {sid}: create rejected HTTP {e.code}', flush=True)
                if e.code in (401, 403):
                    raise SystemExit('Provider authentication/permission rejection; stop rather than repeat invalid requests.')
                cooldown()
                continue
            except Exception:
                st['status'] = 'submission_uncertain'
                save(state)
                raise SystemExit('Create outcome unknown; stopped safely for task reconciliation.')
            vid = body.get('video_id')
            if not vid:
                st['status'] = 'submission_uncertain'
                save(state)
                raise SystemExit('No documented video_id returned; task reconciliation required.')
            st.update(video_id=vid, status='polling')
            save(state)
        while True:
            try:
                body = api('GET', '/agnesapi?' + urlencode({
                    'video_id': st['video_id'], 'model_name': MODEL}), key)
            except Exception:
                cooldown()
                continue
            status = body.get('status')
            print(f'Clip {sid}: {status}', flush=True)
            if status == 'failed':
                st.pop('video_id')
                st['status'] = 'generation_failed'
                save(state)
                cooldown()
                break
            if status == 'completed' and body.get('url'):
                tmp = dest.with_suffix('.part')
                try:
                    with urllib.request.urlopen(body['url'], timeout=180) as response, tmp.open('wb') as out:
                        while block := response.read(1024*1024):
                            out.write(block)
                    tmp.replace(dest)
                except Exception:
                    cooldown()
                    continue
                st.update(status='downloaded', visual_review='pending', machine_qc='pending',
                          bytes=dest.stat().st_size)
                save(state)
                print(f'Clip {sid}: downloaded, QC DEFERRED', flush=True)
                cooldown()
                return
            time.sleep(15)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Lam Guoyun - Norway 722 style serial generation")
    parser.add_argument('--scene', choices=[f'{i:02}' for i in range(1,16)])
    parser.add_argument('--create-window', type=int, choices=range(1, 51), help='Checkpoint after at most this many creates')
    args = parser.parse_args()
    key = os.environ.get('AGNES_API_KEY', '').strip()
    if not key:
        raise SystemExit('Missing AGNES_API_KEY Actions secret. No request sent.')
    CLIPS.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    statefile = WORK / 'state.json'
    state = json.loads(statefile.read_text()) if statefile.exists() else {}
    story = json.loads((ROOT / 'storyboard.json').read_text())
    assert len(story) == 15 and all(s['seconds'] == '12' for s in story)
    print(f"Storyboard loaded: {len(story)} clips, Norway 722 style, 9:16 vertical for Lam")
    for item in story:
        if not args.scene or args.scene == item['id']:
            collect_one(item, state, key, create_window=args.create_window)
    downloaded = [i['id'] for i in story if (CLIPS / (i['id']+'.mp4')).exists()]
    missing = [i['id'] for i in story if i['id'] not in downloaded]
    print(f'::notice title=Collection progress::Downloaded {len(downloaded)}/15; missing={missing}; QC deferred.', flush=True)

if __name__ == '__main__':
    main()
