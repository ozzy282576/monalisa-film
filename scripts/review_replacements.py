"""Machine checks on replacement candidates only, without granting visual approval."""
import json
from pathlib import Path
from generate import qc
ROOT=Path(__file__).resolve().parents[1]
plan=json.loads((ROOT/'review/repair-plan.json').read_text())
state=json.loads((ROOT/'work/state.json').read_text())
for item in plan['clips']:
    sid=item['id']
    dest=ROOT/'clips'/f'{sid}.mp4'
    st=state.get(sid,{})
    if not dest.exists() or st.get('visual_repair_revision')!=plan['revision']:
        print(f'::warning title=Missing replacement::Clip {sid} has no new candidate.')
        continue
    try:
        good=qc(dest,sid)
    except Exception:
        good=False
        (ROOT/'work'/f'qc-{sid}.json').write_text(json.dumps({'machine_qc':'fail','reasons':['probe_or_decode_failure'],'visual_review':'pending'}))
    st['machine_qc']='pass' if good else 'fail'
    st['visual_review']='pending'
    print(f'::notice title=Candidate {sid}::Machine QC {st["machine_qc"]}; visual approval pending.')
(ROOT/'work/state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
