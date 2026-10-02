"""Serial Agnes generation. Secrets stay in Actions; media stays in artifacts.
Machine QC is NOT approval of anatomy, historical accuracy or audio sync.
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
BASE = 'https://apihub.agnes-ai.com'
MODEL = 'agnes-video-2.5-flash'
MAX_TRIES = 50
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
    # Never print the response body, signed download URLs or credentials.
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True)


def qc(path, sid):
    data = json.loads(run('ffprobe', '-v', 'error', '-show_streams', '-show_format',
                          '-of', 'json', str(path)).stdout)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    duration = float(video.get('duration', data['format']['duration']))
    reasons = []
    if path.stat().st_size < 80000:
        reasons.append('small_file')
    if not 11.95 <= duration <= 12.6:
        reasons.append('duration_outside_normalizable_range')
    if video['width'] < 1280 or video['height'] < 720 or abs(video['width']/video['height']-16/9) > .02:
        reasons.append('resolution_or_aspect')
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
    print('Cooldown: 75 seconds', flush=True)
    time.sleep(GAP)


def collect_one(item, state, key):
    """Collect raw media only; never call QC in this phase."""
    sid = item['id']
    st = state.setdefault(sid, {'tries': 0, 'status': 'pending'})
    dest = CLIPS / (sid + '.mp4')
    if st['status'] in ('downloaded', 'machine_pass') and dest.exists():
        print(f'Clip {sid}: raw file retained, QC deferred', flush=True)
        return
    if st['status'] in ('submission_uncertain', 'submitting'):
        raise SystemExit('Prior create outcome uncertain; reconcile provider task before resuming.')
    while True:
        if not st.get('video_id'):
            if st['tries'] >= MAX_TRIES:
                st['status'] = 'exhausted'
                save(state)
                print(f'::warning title=Clip {sid} exhausted::50 attempts used; no video. Continue to next scene.', flush=True)
                return False
            st['tries'] += 1
            st['status'] = 'submitting'
            save(state)
            print(f'Clip {sid}, create attempt {st["tries"]}/50', flush=True)
            try:
                body = api('POST', '/v1/videos', key, {
                    'model': MODEL, 'prompt': item['prompt'], 'seconds': '12',
                    'mode': 'text', 'size': '720P', 'aspect_ratio': '16:9'})
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


def review_and_repair(story, state, key):
    # Hard gate: never begin QA or repair while a first-pass clip is missing.
    if not all((CLIPS / (i['id']+'.mp4')).exists() for i in story):
        raise SystemExit('First pass incomplete: QC and repair not started.')
    while True:
        rejected = []
        for item in story:
            sid = item['id']
            try:
                good = qc(CLIPS / (sid+'.mp4'), sid)
            except Exception:
                good = False
                (WORK / f'qc-{sid}.json').write_text(json.dumps({
                    'machine_qc': 'fail', 'reasons': ['probe_or_decode_error'],
                    'visual_review': 'pending'}))
            state[sid]['machine_qc'] = 'pass' if good else 'fail'
            state[sid]['visual_review'] = 'pending'
            if not good:
                rejected.append(item)
            save(state)
        (WORK / 'redo.json').write_text(json.dumps([s['id'] for s in rejected]))
        if not rejected:
            print('All raw clips pass machine QC. Human visual QA and narration still pending.', flush=True)
            return
        for item in rejected:
            sid = item['id']
            st = state[sid]
            if st['tries'] >= MAX_TRIES:
                raise SystemExit(f'{sid}: repair budget exhausted; raw file preserved, NOT approved.')
            # Retain rejected originals for audit; never overwrite accepted clips.
            archive = WORK / 'rejected'
            archive.mkdir(exist_ok=True)
            (CLIPS / (sid+'.mp4')).replace(archive / f'{sid}-attempt-{st["tries"]}.mp4')
            st.pop('video_id', None)
            st['status'] = 'redo_pending'
            save(state)
            collect_one(item, state, key)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', choices=[f'{i:02}' for i in range(1,16)])
    parser.add_argument('--review', action='store_true')
    parser.add_argument('--renew-exhausted', action='store_true',
                        help='Explicitly authorized new batch; preserve prior attempt history')
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
    if args.renew_exhausted:
        for sid, st in state.items():
            if st.get('tries', 0) >= MAX_TRIES and not st.get('video_id') and st.get('status') not in ('submitting', 'submission_uncertain'):
                st.setdefault('prior_batches', []).append({
                    'tries': st['tries'], 'status': st['status'], 'http_code': st.get('http_code')})
                print(f'Clip {sid}: prior batch tries={st["tries"]}, HTTP={st.get("http_code")}; new batch authorized', flush=True)
                st.update(tries=0, status='pending')
        save(state)
    if args.review:
        review_and_repair(story, state, key)
        return
    for item in story:
        if not args.scene or args.scene == item['id']:
            collect_one(item, state, key)
    downloaded = [i['id'] for i in story if (CLIPS / (i['id']+'.mp4')).exists()]
    missing = [i['id'] for i in story if i['id'] not in downloaded]
    print(f'::notice title=Collection progress::Downloaded {len(downloaded)}/15; missing={missing}; QC deferred.', flush=True)


if __name__ == '__main__':
    main()
