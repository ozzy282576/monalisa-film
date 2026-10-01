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


def main():
    key = os.environ.get('AGNES_API_KEY', '').strip()
    if not key:
        raise SystemExit('Missing AGNES_API_KEY Actions secret. No request sent.')
    CLIPS.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    statefile = WORK / 'state.json'
    state = json.loads(statefile.read_text()) if statefile.exists() else {}
    story = json.loads((ROOT / 'storyboard.json').read_text())
    assert len(story) == 15 and all(s['seconds'] == '12' for s in story)
    for item in story:
        sid = item['id']
        st = state.setdefault(sid, {'tries': 0, 'status': 'pending'})
        dest = CLIPS / (sid + '.mp4')
        if st['status'] == 'machine_pass' and dest.exists() and qc(dest, sid):
            continue
        if st['status'] in ('submission_uncertain', 'submitting'):
            raise SystemExit('Prior create outcome uncertain; reconcile provider task before resuming. No duplicate submission.')
        while True:
            if not st.get('video_id'):
                if st['tries'] >= MAX_TRIES:
                    raise SystemExit(f'{sid}: 50 attempts exhausted. Later clips NOT started.')
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
                    cooldown()
                    continue
                except Exception:
                    st['status'] = 'submission_uncertain'
                    save(state)
                    # Retrying a timed-out POST could create concurrent billable tasks.
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
                    # Retry the same task, NOT another create.
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
                        # No API credentials forwarded to third-party media hosts.
                        with urllib.request.urlopen(body['url'], timeout=180) as response, tmp.open('wb') as out:
                            while block := response.read(1024*1024):
                                out.write(block)
                        tmp.replace(dest)
                    except Exception:
                        cooldown()
                        continue
                    try:
                        good = qc(dest, sid)
                    except Exception:
                        good = False
                    if good:
                        st['status'] = 'machine_pass'
                        st['visual_review'] = 'pending'
                        save(state)
                        print(f'Clip {sid}: machine QC passed; visual review still pending', flush=True)
                        cooldown()
                        break
                    st.pop('video_id')
                    st['status'] = 'qc_failed'
                    save(state)
                    dest.unlink(missing_ok=True)
                    cooldown()
                    break
                time.sleep(15)
            if st['status'] == 'machine_pass':
                break
    print('15 raw clips generated. NOT a finished or visually approved film.', flush=True)


if __name__ == '__main__':
    main()
