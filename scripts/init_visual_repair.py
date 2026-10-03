"""Archive only a reviewed rejected source; initialize its replacement once."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(root, sid, plan_rel='review/repair-plan.json'):
    plan = json.loads((root/plan_rel).read_text())
    item = next(i for i in plan['clips'] if i['id'] == sid)
    src_hash = item.get('source_sha256') or item.get('rejected_candidate_sha256')
    revision = plan['revision']
    statepath = root/'work/state.json'
    state = json.loads(statepath.read_text())
    dest = root/'clips'/f'{sid}.mp4'
    st = state[sid]
    if st.get('visual_repair_revision') != revision:
        if st.get('status') not in ('downloaded','machine_pass'):
            raise SystemExit('Source is not a confirmed completed download; no replacement initialized')
        if hashlib.sha256(dest.read_bytes()).hexdigest() != src_hash:
            raise SystemExit('Source hash mismatch; refusing to replace unreviewed media')
        archive = root/'work/rejected'/revision
        archive.mkdir(parents=True, exist_ok=True)
        old = copy.deepcopy(st)
        (archive/f'{sid}-state.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
        report = root/'work'/f'qc-{sid}.json'
        if report.exists():
            report.replace(archive/f'qc-{sid}-original.json')
        dest.replace(archive/f'{sid}.mp4')
        state[sid] = {'tries':0,'status':'pending','visual_review':'pending',
            'visual_repair_revision':revision,'rejected_source_sha256':src_hash,
            'previous_generation':old}
        tmp = statepath.with_suffix('.tmp')
        tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2))
        tmp.replace(statepath)
    # Apply the revised prompt in the runner checkout, including on later windows.
    storypath = root/'storyboard.json'
    story = json.loads(storypath.read_text())
    for scene in story:
        if scene['id'] == sid:
            scene['prompt'] = item['prompt']
            scene['visual_review'] = 'pending'
    storypath.write_text(json.dumps(story,ensure_ascii=False,indent=2))
    print(f'::notice title=Visual repair {sid}::Revision {revision}; source retained. Candidate must be manually reviewed.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--scene',required=True)
    parser.add_argument('--plan',default='review/repair-plan.json',
                        help='Repair plan path (e.g. review/repair-plan-v2.json)')
    args=parser.parse_args()
    prepare(ROOT,args.scene,args.plan)
