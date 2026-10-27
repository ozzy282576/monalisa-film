#!/usr/bin/env python3
"""Cloud-first Agnes production: verified clips, small QA sheets, then a 180s first cut.

Never pretends a visual review has happened. Human review is nonblocking and the
export remains labeled a first cut until it is actually inspected. No video bytes
are committed to Git; only required small QA images, receipts and edit metadata.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'production'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import agnes_video as agnes
from media import ensure_tools, inspect_clip, render_python
from throttle import RequestGate, BudgetExhausted

BRANCH='arena/cb25986c-desktop-tutorial'
PLAN=Path(__file__).with_name('story.json')
RESULTS=Path(__file__).with_name('results.json')
LOCK=threading.RLock()


def read_json(path,default):
    return json.loads(path.read_text()) if path.exists() else default


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def full_payload(project,shot):
    return agnes.build_payload(argparse.Namespace(
        prompt=project['style_prefix']+shot['prompt'],negative_prompt=project['negative_prompt'],
        image=None,mode=None,seed=shot['seed'],steps=None,seconds=shot['seconds'],num_frames=None,
        frame_rate=shot['frame_rate'],aspect=shot['aspect'],resolution=shot['resolution'],
        width=None,height=None,model=agnes.DEFAULT_MODEL))


def request_hash(project,shot):
    return hashlib.sha256(json.dumps(full_payload(project,shot),sort_keys=True).encode()).hexdigest()


GRID_SECONDS=4   # 本片 45 镜 × 4 秒规划网格（参考项目是 30 × 6）；Agnes 每镜仍请求 7 秒


def validate(project):
    shots=project['shots']
    if project['target_duration']!=180 or len(shots)*GRID_SECONDS!=180:
        raise ValueError(f'Expected the reviewed 180-second plan on a {GRID_SECONDS}-second grid')
    if len({s['id'] for s in shots})!=len(shots):raise ValueError('Duplicate shot IDs')
    for i,shot in enumerate(shots):
        if shot['start']!=i*GRID_SECONDS or shot['duration']!=GRID_SECONDS:raise ValueError('Invalid planning timeline')
        if shot['kind']=='agnes':
            payload=full_payload(project,shot)
            if not shot['prompt'].strip() or payload['model']!='agnes-video-v2.0' or (payload['num_frames']-1)%8:
                raise ValueError('Invalid Agnes request')
        elif shot['kind']=='archive':
            asset=(PLAN.parent/shot['archive_asset']).resolve()
            if not asset.is_relative_to(PLAN.parent) or not asset.is_file() or digest(asset)!=shot['archive_sha256']:
                raise ValueError('Missing or changed archival image')
        elif shot['kind']!='graphic' or not shot['graphic'].strip():raise ValueError('Invalid graphic cue')
    if sum(c['duration'] for c in project['chapters'])!=180:raise ValueError('Invalid chapter plan')


def prune_stale(doc):
    """丢掉「还没有可复用素材」的进度记录，让重跑提交新任务而不是去复述一个已失败的任务。

    生成器会记住 provider 的 task_id 以便断点续跑，这在一个任务只是**排队中断**时是省额度的好事；
    但当 provider 已经把这个任务判死（500 / Generation failed）时，续跑会一直轮询同一个死任务，
    于是「重新触发一次」永远修不好它——冷案DNA 项目 2026-09-13 的 S10 就是这样。
    已经有 ``video_url`` 的记录（``generated``：素材在 CDN 上但还没落盘校验）保留：那种情况只需重新下载。
    """
    shots=doc.setdefault('shots',{})
    stale=sorted(sid for sid,row in shots.items()
                 if row.get('status')!='completed' and not row.get('video_url'))
    for sid in stale: shots.pop(sid)
    return stale


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True,stderr=subprocess.STDOUT,timeout=90)


def cached_result_matches(old,wanted_hash):
    return (old.get('request_hash')==wanted_hash and bool(old.get('video_url'))
            and bool(old.get('sha256')) and bool(old.get('bytes')))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--payload',default='{}');parser.add_argument('--validate',action='store_true')
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--prune-failed',action='store_true',
                        help='只清理 results.json 里的死任务记录，清完就退出（不生成）')
    args=parser.parse_args()
    project=read_json(PLAN,{});validate(project)
    audio_manifest=read_json(PLAN.parent/'audio/manifest.json',{})
    audio_by_id={r['id']:r for r in audio_manifest.get('clips',[])}
    for chapter in project['chapters']:
        record=audio_by_id.get(chapter['id'],{})
        path=PLAN.parent/'audio'/record.get('file','missing.mp3')
        if record.get('text')!=chapter['text'] or not path.is_file() or digest(path)!=record.get('sha256'):
            raise ValueError('Narration text/audio mismatch: '+chapter['id'])
    if args.validate:
        count=sum(s['kind']=='agnes' for s in project['shots'])
        gcount=sum(s['kind']=='graphic' for s in project['shots'])
        acount=sum(s['kind']=='archive' for s in project['shots'])
        print(f'VALID: 180-second plan; {len(project["shots"])} shots; {count} Agnes sources; {gcount} graphics; {acount} archival; narration hashes match');return 0
    options=json.loads(args.payload or '{}')
    requested=options.get('only','')
    if not isinstance(requested,str):raise ValueError('only must be comma-separated IDs')
    only={s.strip() for s in requested.split(',') if s.strip()}
    shots=[s for s in project['shots'] if s['kind']=='agnes']
    if only-{s['id'] for s in shots}:raise ValueError('Unknown/non-Agnes shot ID')
    if only:shots=[s for s in shots if s['id'] in only]
    workers=min(2,max(1,int(options.get('workers',2))))
    # Free video model creation is documented at 1 RPM. Two in-flight tasks do
    # not permit bursts of creation requests; they share this paced gate.
    gate=RequestGate(minimum_interval=75)
    # 38 个 Agnes 镜头、共享 75 秒创建间隔：光排队就要 ≈48 分钟，再加生成与下载，
    # 85 分钟（参考项目 24 镜的预算）不够；预算到点只会保存 task_id 等下次续跑，不会丢素材。
    generation_deadline=time.monotonic()+170*60
    if args.publish:
        if os.getenv('GITHUB_ACTIONS')!='true' or git('branch','--show-current').strip()!=BRANCH:
            raise RuntimeError('Publish only from this fixed Arena branch in Actions')
        git('config','user.name','github-actions[bot]')
        git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    doc=read_json(RESULTS,{'project':project['title'],'model':agnes.DEFAULT_MODEL,'shots':{}})
    if args.prune_failed:
        # 只清理、不生成：出片工作流把它单独作为生成前的步骤。
        # （它要是继续往下跑，就把"清理"变成了第二次全量生成，还会把失败当成自己的失败。）
        stale=prune_stale(doc)
        RESULTS.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
        print('PRUNED_STALE '+json.dumps(stale),flush=True)
        return 0
    doc['phase']='preparing_sources'
    doc['review']={'status':'pending','scope':'visual/audio quality','blocking_generation':False,
                   'note':'No automatic visual approval. Export is an unreviewed first cut.'}
    doc['workflow_policy']='cloud-first-cut-v3-rate-aware'
    doc['rate_policy']={'minimum_creation_interval_seconds':75,'poll_interval_seconds':25,
                        'shared_retry_after_cooldown':True,'key_rotation':False}
    doc['required_generated_shots']=[s['id'] for s in project['shots'] if s['kind']=='agnes']
    sources=ROOT/'work/rabies1885/sources';sources.mkdir(parents=True,exist_ok=True)
    export=ROOT/'work/rabies1885/clips';export.mkdir(parents=True,exist_ok=True)
    qa=ROOT/'production/rabies1885/qa';qa.mkdir(parents=True,exist_ok=True)
    key=os.getenv('AGNES_API_KEY','').strip();base=os.getenv('AGNES_BASE_URL',agnes.DEFAULT_BASE_URL).rstrip('/')

    def checkpoint(label,sid=None,files=(),**values):
        with LOCK:
            if sid:
                row=doc['shots'].setdefault(sid,{'id':sid});row.update(values)
                row['updated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            doc['updated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            doc['run_id']=os.getenv('GITHUB_RUN_ID')
            RESULTS.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
            paths=[str(RESULTS.relative_to(ROOT))]+[str(Path(p).relative_to(ROOT)) for p in files]
            if args.publish:
                git('add','--',*paths)
                if subprocess.run(['git','diff','--cached','--quiet','--',*paths],cwd=ROOT).returncode:
                    git('commit','-m','rabies1885: '+label,'--',*paths)
                    for attempt in range(3):
                        try:git('push','origin',BRANCH);break
                        except subprocess.CalledProcessError:
                            if attempt==2:raise
                            git('pull','--rebase','origin',BRANCH)
            print('PRODUCTION_STATUS '+label,flush=True)

    def finish_asset(shot,old,dest,wanted_hash,reused=False):
        sid=shot['id']
        if not dest.exists() or digest(dest)!=old['sha256']:
            agnes.download(old['video_url'],dest,retries=3,retry_delay=5)
        if dest.stat().st_size!=old['bytes'] or digest(dest)!=old['sha256']:
            raise RuntimeError('Downloaded file does not match its receipt: '+sid)
        info=inspect_clip(dest,qa,sid)
        checkpoint(sid+' media and QA ready',sid,files=[qa/(sid+'.jpg'),qa/(sid+'.json')],
                   status='completed',request_hash=wanted_hash,video_url=old['video_url'],
                   sha256=old['sha256'],bytes=old['bytes'],inspection=info,error=None,
                   reused_existing_asset=reused,visual_review='pending')
        return True

    def create_paced(sid,payload):
        for attempt in range(8):
            checkpoint(sid+' waiting for a creation slot',sid,status='waiting_create_slot',error=None)
            gate.acquire_creation(generation_deadline)
            try:
                # Only this outer policy retries 429, so every attempt is paced.
                return agnes.create_task(base,key,payload,retries=1,retry_delay=75)
            except agnes.RateLimited as exc:
                cooldown=max(min(300,75*(2**attempt)),exc.retry_after or 0)
                checkpoint(sid+' provider cooldown',sid,status='rate_limited',
                           quota_retry=attempt+1,provider_retry_after_seconds=exc.retry_after,
                           applied_cooldown_seconds=cooldown,error=str(exc).replace(key,'[redacted]')[:600])
                gate.defer(cooldown)
                if attempt==7:
                    raise
        raise RuntimeError('Creation retry budget exhausted')

    def generate(shot):
        sid=shot['id'];payload=full_payload(project,shot);wanted_hash=request_hash(project,shot)
        with LOCK:old=dict(doc['shots'].get(sid,{}))
        dest=sources/(sid+'.mp4')
        try:
            if cached_result_matches(old,wanted_hash):
                print(sid+': reusing completed provider result; no new generation request',flush=True)
                return finish_asset(shot,old,dest,wanted_hash,reused=True)
            if old.get('request_hash')!=wanted_hash:
                with LOCK:
                    if old:doc.setdefault('previous_results',{}).setdefault(sid,[]).append(old)
                    doc['shots'][sid]={'id':sid}
                old={}
            if not key:
                checkpoint(sid+' blocked',sid,status='blocked',request_hash=wanted_hash,
                           error='AGNES_API_KEY is unavailable to this workflow')
                return False
            video_id,task_id=old.get('video_id'),old.get('task_id')
            if not video_id:
                checkpoint(sid+' submitting',sid,status='submitting',request_hash=wanted_hash,error=None)
                created=create_paced(sid,payload)
                video_id=created.get('video_id') or created.get('id') or created.get('task_id')
                task_id=created.get('task_id') or created.get('id')
                if not video_id:raise agnes.Fatal('No task identifier returned')
                checkpoint(sid+' queued',sid,status='queued',video_id=str(video_id),task_id=str(task_id or ''),
                           requested_seconds=payload['num_frames']/payload['frame_rate'])
            else:print(sid+': resuming existing provider task',flush=True)
            remaining=generation_deadline-time.monotonic()
            if remaining<30:raise BudgetExhausted('Generation budget reached; task ID was saved for resumption')
            final,url=agnes.poll_task(base,key,agnes.DEFAULT_MODEL,str(video_id),str(task_id) if task_id else None,
                                     interval=25,timeout=min(1500,remaining),max_failures=12,
                                     before_request=lambda:gate.wait_unblocked(generation_deadline),
                                     rate_limit_callback=gate.defer)
            size=agnes.download(url,dest,retries=3,retry_delay=5)
            checksum=digest(dest)
            receipt={'video_url':url,'bytes':size,'sha256':checksum,'request_hash':wanted_hash}
            checkpoint(sid+' generated',sid,status='generated',video_url=url,bytes=size,sha256=checksum,
                       reported_size=final.get('size'),reported_seconds=final.get('seconds'),error=None)
            return finish_asset(shot,receipt,dest,wanted_hash)
        except Exception as exc:
            error=str(exc).replace(key,'[redacted]') if key else str(exc)
            checkpoint(sid+' failed',sid,status='failed',error=error[:600])
            return False

    try:
        ensure_tools();doc['phase']='generating_sources';checkpoint('cloud generation started')
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes=list(pool.map(generate,shots))
        if not all(outcomes):
            doc['phase']='generation_incomplete';checkpoint('generation incomplete')
            (export/'未完成说明.txt').write_text('生成尚未完成，未导出成片。请查看 production/rabies1885/results.json。\n')
            for p in sources.glob('*.mp4'):shutil.copy2(p,export/p.name)
            return 1
        if only:
            doc['phase']='selected_sources_ready';checkpoint('selected sources ready')
            for sid in only:shutil.copy2(sources/(sid+'.mp4'),export/(sid+'.mp4'))
            return 0
        doc['phase']='preparing_cloud_edit';checkpoint('preparing cloud edit')
        python=render_python(ROOT);edit=ROOT/'work/rabies1885/edit';edit.mkdir(parents=True,exist_ok=True)
        doc['phase']='rendering_first_cut';checkpoint('rendering first cut')
        staging=edit/'first-cut.mp4'
        subprocess.run([str(python),str(Path(__file__).with_name('render.py')),
                        '--sources',str(sources),'--work',str(edit),'--output',str(staging)],check=True)
        final_name='狂犬病疫苗：一百四十年前那场赌局_三分钟_初版.mp4'
        shutil.move(staging,export/final_name)
        delivery=ROOT/'production/rabies1885/delivery';delivery.mkdir(parents=True,exist_ok=True)
        names=['technical-report.json','edit-decision-list.json','narration-timing.json',
               'caption-timing.json','alignment-report.json','captions.srt','final-contact.jpg']
        saved=[]
        for name in names:
            path=delivery/name;shutil.copy2(edit/name,path);saved.append(path)
        report=read_json(delivery/'technical-report.json',{})
        report['output']=final_name
        (delivery/'technical-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        shutil.copy2(delivery/'technical-report.json',export/'技术检查.json')
        shutil.copy2(delivery/'captions.srt',export/'狂犬病疫苗：一百四十年前那场赌局_字幕.srt')
        shutil.copy2(ROOT/'production/rabies1885/screenplay.md',export/'剧本与来源.md')
        (export/'交付说明.txt').write_text(
            '狂犬病疫苗：一百四十年前那场赌局\n180秒 / 1920×1080 / 30fps / 中文解说\n'
            '使用 Agnes Video V2.0 生成镜头，配音来自用户选定的声音。\n'
            '此文件是技术检查通过的初版；视觉与听感仍需审核，不声称已逐帧或逐字验收。\n'
            'AI情景重现并非历史影像；未经证实的推测没有被写成事实。\n')
        doc['phase']='first_cut_ready'
        doc['delivery']={**report,'artifact_name':'rabies1885-agnes-'+os.getenv('GITHUB_RUN_NUMBER','local')}
        checkpoint('three-minute first cut ready',files=saved)
        summary=os.getenv('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary,'a') as f:
                f.write(f'## 狂犬病疫苗：一百四十年前那场赌局 · 三分钟初版\n\n{len(shots)}段Agnes素材已完成解码检查并剪辑，身份介绍另使用档案肖像。\n\n')
                f.write(f'输出：**{final_name}**，180秒；视觉/听感仍待人工审核。\n\n')
                f.write('成片在本次运行的 `rabies1885-agnes-*` artifact 中。大视频未提交到Git。\n')
        print('CLOUD_FIRST_CUT_READY '+final_name,flush=True);return 0
    except Exception as exc:
        error=str(exc).replace(key,'[redacted]') if key else str(exc)
        doc['phase']='pipeline_failed';doc['pipeline_error']=error[:800]
        checkpoint('pipeline stopped')
        (export/'未完成说明.txt').write_text('制作未完成：'+error[:800]+'\n没有把测试图或静态图冒充Agnes成片。\n')
        raise


if __name__=='__main__':raise SystemExit(main())
