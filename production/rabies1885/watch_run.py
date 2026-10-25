#!/usr/bin/env python3
"""Read-only watcher: fetch small GitHub QA sheets, not blocked media-storage URLs."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
import urllib.parse

REPO='32r4e2q-hub/desktop-tutorial'
BRANCH='arena/cb25986c-desktop-tutorial'


def api(endpoint):
    return json.loads(subprocess.check_output(['gh','api',endpoint],text=True,timeout=60))


def content(path):
    result=api(f'repos/{REPO}/contents/{path}?ref='+urllib.parse.quote(BRANCH,safe=''))
    if not result.get('content') and result.get('size'):
        result=api(f'repos/{REPO}/git/blobs/'+result['sha'])
    return base64.b64decode(result['content'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
    parser.add_argument('--out',type=Path,default=Path('work/rabies1885/review'))
    parser.add_argument('--timeout',type=int,default=6600);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True);started=time.monotonic();seen={};last_phase=None;tick=0
    while time.monotonic()-started<args.timeout:
        tick+=1
        try:
            raw=content('production/rabies1885/results.json');doc=json.loads(raw)
            if str(doc.get('run_id'))!=args.run_id:
                if tick%3==1:print('WAITING_FOR_CURRENT_RUN_CHECKPOINT',flush=True)
                time.sleep(20);continue
            (args.out/'results.json').write_bytes(raw)
            phase=doc.get('phase')
            if phase!=last_phase:print('PHASE '+str(phase),flush=True);last_phase=phase
            required=set(doc.get('required_generated_shots') or
                         [s['id'] for s in json.loads(Path(__file__).with_name('story.json').read_text())['shots'] if s['kind']=='agnes'])
            for sid,row in sorted(doc.get('shots',{}).items()):
                if sid not in required:continue
                if row.get('status')=='completed' and row.get('inspection') and seen.get(sid)!=row.get('sha256'):
                    (args.out/(sid+'.jpg')).write_bytes(content('production/rabies1885/qa/'+sid+'.jpg'))
                    (args.out/(sid+'.json')).write_bytes(content('production/rabies1885/qa/'+sid+'.json'))
                    seen[sid]=row['sha256'];print('QA_READY '+sid,flush=True)
            if phase=='first_cut_ready':
                for name in ['technical-report.json','final-contact.jpg','edit-decision-list.json','alignment-report.json']:
                    if not (args.out/name).exists():
                        (args.out/name).write_bytes(content('production/rabies1885/delivery/'+name))
                print('FIRST_CUT_REVIEW_FILES_READY',flush=True)
            if tick%3==0 or phase in ('pipeline_failed','generation_incomplete','first_cut_ready'):
                run=api(f'repos/{REPO}/actions/runs/{args.run_id}')
                print(f'RUN {run["status"]} {run.get("conclusion")} QA={len(seen)}/{len(required)}',flush=True)
                if run['status']=='completed':
                    artifacts=api(f'repos/{REPO}/actions/runs/{args.run_id}/artifacts')
                    (args.out/'artifacts.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2))
                    print('RUN_FINISHED '+str(run.get('conclusion')),flush=True)
                    return 0 if run.get('conclusion')=='success' else 1
        except Exception as exc:print(f'WATCH_RETRY {type(exc).__name__}: {exc}',flush=True)
        time.sleep(20)
    print('WATCH_TIME_BUDGET_REACHED',flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
