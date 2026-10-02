"""Single-request diagnostic; never log keys or signed media URLs.
Restore the exhausted batch first. If no task is active, probe creation ONCE.
Any accepted task is persisted for recovery, never repeated or discarded.
"""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
KEY = os.environ.get('AGNES_API_KEY', '').strip()
OUT = ROOT / 'diagnostic'
OUT.mkdir(exist_ok=True)


def clean(value):
    text = str(value)
    if KEY:
        text = text.replace(KEY, '[REDACTED]')
    text = re.sub(r'https?://\S+', '[URL]', text)
    text = re.sub(r'(?i)(bearer\s+|sk-)[A-Za-z0-9_.-]+', '[REDACTED]', text)
    text = re.sub(r'[A-Za-z0-9_-]{40,}', '[LONG_VALUE]', text)
    return text[:1000]


def report(title, text):
    text = clean(text).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print(f'::notice title={title}::{text}', flush=True)


def request(method, path, payload=None):
    req = urllib.request.Request('https://apihub.agnes-ai.com' + path,
        data=json.dumps(payload).encode() if payload else None,
        headers={'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        raw = error.read(16000).decode('utf-8', 'replace')
        try:
            body = json.loads(raw)
        except ValueError:
            body = {'message': raw}
        return error.code, body


def main():
    paths = list((ROOT / 'restored').rglob('state.json'))
    if len(paths) != 1:
        raise SystemExit('Cannot unambiguously locate restored task state; no provider request sent.')
    state = json.loads(paths[0].read_text())
    summary = {sid: {k: st.get(k) for k in ('tries', 'status', 'http_code', 'prior_batches')}
               for sid, st in state.items()}
    report('Prior batch state', json.dumps(summary, ensure_ascii=False))
    (OUT / 'prior-summary.json').write_text(json.dumps(summary, indent=2))
    if not KEY:
        report('Credential check', 'AGNES_API_KEY is missing; no provider request sent.')
        return
    if any(st.get('video_id') or st.get('status') in ('submitting', 'submission_uncertain') for st in state.values()):
        report('Probe skipped', 'Task may exist; no create request sent.')
        return
    first = state.get('01', {})
    if first.get('status') != 'create_rejected' or first.get('tries', 0) < 50:
        report('Probe skipped', 'Prior state does not confirm exhausted rejected submissions.')
        return
    item = json.loads((ROOT / 'storyboard.json').read_text())[0]
    payload = {'model': 'agnes-video-2.5-flash', 'prompt': item['prompt'], 'seconds': '12',
               'mode': 'text', 'size': '720P', 'aspect_ratio': '16:9'}
    record = {'scene': '01', 'tries': 1, 'status': 'submitting', 'prior_run': 36876593240}
    target = OUT / 'probe-state.json'
    target.write_text(json.dumps(record))
    try:
        code, body = request('POST', '/v1/videos', payload)
    except Exception as error:
        record['status'] = 'submission_uncertain'
        target.write_text(json.dumps(record))
        report('Probe uncertain', type(error).__name__ + '; no retry will be sent.')
        return
    if 200 <= code < 300 and body.get('video_id'):
        record.update(status='polling', video_id=body['video_id'])
        report('Probe accepted', 'First clip task accepted and saved in diagnostic-state artifact. Resume this task; do NOT create another.')
    elif code >= 400:
        message = body.get('error', body.get('message', 'No documented error message')) if isinstance(body, dict) else body
        record.update(status='create_rejected', http_code=code, error=clean(message))
        report('Provider rejection', f'HTTP {code}: {clean(message)}')
    else:
        record['status'] = 'submission_uncertain'
        report('Probe uncertain', 'Response has no documented video_id; no retry will be sent.')
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
