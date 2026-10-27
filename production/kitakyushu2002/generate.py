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
import traceback

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'production'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import agnes_video as agnes
from media import ensure_tools, inspect_clip, render_python
from throttle import RequestGate, BudgetExhausted
from model_policy import (MODEL,SIZE_TIER,ALLOWED_MODELS,SUPPORTED_SIZES,SUPPORTED_MODES)

BRANCH='arena/44a8fff6-desktop-tutorial'
CAST=Path(__file__).with_name('cast.json')
PLAN=Path(__file__).with_name('story.json')
RESULTS=Path(__file__).with_name('results.json')
PROBE=Path(__file__).with_name('delivery')/'provider-probe.json'
LOCK=threading.RLock()

# 模型与分辨率档位的**唯一出处**是 model_policy.py（generate.py 与 render.py 都从那里读）：
# 仓库里每个项目都有一个 generate.py，让 render.py 去 import generate 会撞到别的项目那份
# （实测 ImportError: cannot import name 'MODEL' from 'generate' → production/dahlia/generate.py，
# 连带把 test_card_typography.py 弄红）；而且 render.py 是另一个进程，跨进程共享变量本来就不成立。
# ---- 供应商容量熔断（2026-10-10 实测）----------------------------------------
# 「No available channel for model agnes-video-v2.0 under group default (distributor)」
# 是网关在说「这个模型现在一个可用通道都没有」，不是我们的请求写错了：
# 2026-10-10 00:30Z 起连续 5 小时、6 轮 Actions 运行、38 镜全部 503、0 镜成功，
# 而同一把 key 同一个模型 2026-10-09T11:57Z 还成功出过片（run 37926988045）。
# 旧策略把 503 当成普通退避：每镜试 8 次、冷却最长 300 秒 → 每镜烧掉约 50 分钟才失败，
# 一整轮跑满 3 小时仍然一个素材都没有（run 38013901390）。
# 现在按「全片共享」计数：连续 channel_error_limit 轮通道不可用就
#   (a) 等待预算内：只等冷却结束再探（探测就是那一次创建请求，失败不占额度）；
#   (b) 预算用尽：立刻诚实地停（phase=provider_capacity），不再烧满整个预算。
CHANNEL_UNAVAILABLE_MARKERS=('no available channel',)
# 冷却分两档，因为这两种 503 的性质完全不同（2026-10-10 实测）：
#   「no available channel」= 该模型没有可用通道（v2.0 被下线时就是它）——等多久都不会变好，
#     长冷却 300 秒，别白烧；
#   「video queue is full」= 排队满，**每一次请求都是一次抽签**——实测 23 次尝试成 1 次
#     （S03 于 09:11:30 建成、09:22:49 出片）。300 秒冷却等于每小时只抽 12 次签，
#     38 镜要排到天荒地老；缩到 90 秒（仍在免费额度 1 次/分钟之内）就是每小时 40 次。
CHANNEL_COOLDOWN_SECONDS=300
QUEUE_COOLDOWN_SECONDS=90
ABORT=threading.Event()


class ProviderCapacity(RuntimeError):
    """供应商侧没有可用通道：不是请求错误，重试不会让它变好，只能等通道恢复。"""


class QuotaExhausted(RuntimeError):
    """账号额度/余额用尽：不是请求错误，重试一万次也不会变好，只能充值或换一把 key。"""


def channel_unavailable(message):
    text=str(message or '').lower()
    return any(marker in text for marker in CHANNEL_UNAVAILABLE_MARKERS)


# 2026-10-10T07:00Z 实测：payload 改对之后，创建请求越过了字段校验，撞上
#   HTTP 403: Insufficient user quota, remaining: ＄0.000000
# 这是账号余额见底，不是代码问题。旧路径把它当普通 Fatal 交给每个镜头各失败一次，
# 38 镜就是 38 次无用请求 + 一整轮 runner 时间。
QUOTA_MARKERS=('insufficient user quota','insufficient quota','insufficient balance',
               'quota exceeded','余额不足','额度不足')


def quota_exhausted(message):
    text=str(message or '').lower()
    return any(marker in text for marker in QUOTA_MARKERS)


# 供应商侧「容量」类问题的两种文案，都需要**全片共享**的退避（不是每镜各自撞）：
#   no available channel —— 该模型当前没有可用通道（2026-10-10：v2.0 被下线时就是它）
#   video queue is full  —— 视频排队已满（2026-10-10T07:37Z 实测 agnes-video-2.5-flash 720P）
CAPACITY_REASONS=(('no available channel','该模型当前没有可用通道',CHANNEL_COOLDOWN_SECONDS),
                  ('video queue is full','供应商视频排队已满',QUEUE_COOLDOWN_SECONDS),
                  ('queue is full','供应商视频排队已满',QUEUE_COOLDOWN_SECONDS))


def capacity_problem(message):
    """是容量问题就返回 (中文原因, 该冷却多少秒)，不是就返回 None。"""
    text=str(message or '').lower()
    for marker,reason,cooldown in CAPACITY_REASONS:
        if marker in text:
            return reason,cooldown
    return None


def now_stamp():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())


class ChannelBreaker:
    """「模型没有可用通道」时的共享策略：计数 → 全体冷却 → 等预算 → 放弃。

    独立成类是为了能被离线测试真跑一遍（``production/tests/test_provider_capacity.py``）：
    这段逻辑跑在 runner 上、要几十分钟才看得出结果，靠人眼盯 Actions 日志是盯不住的。
    """

    def __init__(self,gate,deadline,error_limit=3,wait_minutes=0.0,
                 cooldown=CHANNEL_COOLDOWN_SECONDS,clock=None,record=None,probe=None,abort=None):
        self.gate=gate
        self.deadline=deadline
        self.error_limit=max(1,int(error_limit))
        self.wait_budget=max(0.0,float(wait_minutes))*60.0
        self.cooldown=float(cooldown)
        self.clock=clock or time.monotonic
        self.record=record or (lambda **values:None)
        self.probe=probe or (lambda:None)
        self.abort=abort if abort is not None else threading.Event()
        self.started=self.clock()
        self.state={'consecutive':0,'attempts':0,'first_seen':None,'last_seen':None,'last_error':None}

    def note_success(self):
        """有一次创建成功就说明供应商缓过来了：连击计数清零，**等待时钟也清零**。

        等待预算必须按「多久没进展」算，不能按「跑了多久」算——实测排队是间歇性的
        （S03 在 09:11 建成，前后几十次都是 queue is full），按墙钟算会在还有产出时把整轮掐死。
        """
        self.state['consecutive']=0
        self.started=self.clock()

    def observe(self,sid,message,reason='供应商侧没有可用容量',cooldown=None):
        """记一次容量问题。返回 True = 冷却结束后可以再探；抛 ProviderCapacity = 整轮放弃。"""
        self.state['consecutive']+=1
        self.state['attempts']+=1
        self.state['last_seen']=now_stamp()
        self.state['first_seen']=self.state['first_seen'] or self.state['last_seen']
        self.state['last_error']=message
        round_no=self.state['consecutive']
        wait=self.cooldown if cooldown is None else float(cooldown)
        # defer 是共享的：两个 worker 一起冷却，等于对整轮生成熔断。
        self.gate.defer(wait)
        self.record(sid=sid,round_no=round_no,cooldown=wait,error=message,
                    reason=reason,outage=dict(self.state))
        if round_no<self.error_limit:
            return True
        waited=self.clock()-self.started
        if waited<self.wait_budget:
            print('PROVIDER_WAIT round=%d waited=%.0fs budget=%.0fs'%(round_no,waited,self.wait_budget),
                  flush=True)
            self.state['consecutive']=0
            # 冷却期只是等，不创建任务、不占额度；冷却结束再探一次。
            self.gate.wait_unblocked(self.deadline)
            return True
        self.abort.set()
        self.probe()
        raise ProviderCapacity(
            'Agnes 网关连续 %d 轮报告%s：%s；等待预算 %.0f 分钟已用尽。'
            '这是供应商侧容量问题——请求本身没错，只能等它缓过来后再触发一轮。'
            %(round_no,reason,str(message)[:200],self.wait_budget/60.0))


def read_json(path,default):
    return json.loads(path.read_text()) if path.exists() else default


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def cast_ledger():
    """角色谱（露脸模式）：id -> (seed, 面容 token)。缺 cast.json 时返回空表。"""
    if not CAST.is_file():
        return {}
    try:
        cast=read_json(CAST,{})
    except ValueError:
        return {}
    ledger={}
    for character in cast.get('characters') or []:
        cid=str(character.get('id'))
        if cid:
            ledger[cid]=(character.get('seed'),(character.get('face') or '').strip())
    return ledger


def shot_seed(shot):
    """本片的锁脸规则：一个镜头只登记了一个角色时，用**这个角色的 seed**，
    而不是镜头自己的 seed —— 同一张脸跨镜头才稳定（手册《露脸模式》）。
    登记了多个角色（双人镜头）时保持镜头 seed，避免角色之间抢一个种子。"""
    declared=[str(x) for x in (shot.get('cast') or [])]
    if len(declared)==1:
        seed=cast_ledger().get(declared[0],(None,))[0]
        if seed is not None:
            return int(seed)
    return shot['seed']


# agnes-video-2.5 的请求形状（2026-10-10 从 https://agnes-ai.com/en/docs/agnes-video-25 抄来，
# 原文摘录留在 delivery/payload-schema-probe.json 的 docs 段）：
#   model / prompt / seconds（**字符串** "4"–"12"）/ size（"720P"|"1080P"|"1K"|"2K"）
#   / aspect_ratio（"16:9" 等，不能 auto）/ mode（**必填**：text|keyframe|reference）/ n=1 / seed
#   媒体字段按模式给：first_frame / last_frame / images / audios / videos
# 明确「传了就 400」的：width、height、fps、num_frames、quality、num_inference_steps、
#   frame_rate、duration、resolution、negative_prompt，以及 size 传像素（1920x1080）。
# 旧实现 production/agnes_video.py::build_payload() 正好把 width/height/num_frames/frame_rate
# 全填上、还把 negative_prompt 当独立字段，所以换模型后一律 400 —— 这里按项目重写，不改共享实现。
# negative_prompt 不再是独立字段：红线（不出可读文字、不冒充真人、不展示遗体血腥）
# 只能压进提示词正文，否则新模型上这些约束直接消失。
# 单一出处已迁至 model_policy.PROMPT_GUARDRAILS（两条生成路线共用；同时避开测试
# 进程里各项目同名 generate.py 的 sys.modules 串味）。此处再导出，名称与语义不变。
from model_policy import PROMPT_GUARDRAILS  # noqa: F401


def compose_prompt(project,shot):
    return (project['style_prefix']+shot['prompt']).strip()+' '+PROMPT_GUARDRAILS


def full_payload(project,shot):
    seconds=max(4,min(12,int(round(shot['seconds']))))
    reference=shot.get('reference_image')
    payload={'model':MODEL,
             'prompt':compose_prompt(project,shot),
             'seconds':str(seconds),           # 文档要求字符串；传数字会让网关 invalid_json
             'size':SIZE_TIER,
             'aspect_ratio':shot['aspect'],
             # reference_image：该角色的定妆照 URL，用 keyframe 模式钉成真正的第一帧
             # （把这张脸钉死在第一眼）。只在 build_story.py 的 REFERENCE_SHOTS 登记过的镜头上有值。
             'mode':'keyframe' if reference else 'text',
             'n':1,
             'seed':shot_seed(shot)}
    if reference:
        payload['first_frame']=reference
    return payload



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
            if not shot['prompt'].strip() or payload['model']!=MODEL:
                raise ValueError('Invalid Agnes request')
            # 新模型的硬约束，错一个就是 400，所以在闸门里先拦（文档《Parameter Restrictions》）
            if payload['mode'] not in SUPPORTED_MODES:
                raise ValueError(f'{shot["id"]}: mode 必须是 {SUPPORTED_MODES} 之一')
            if not str(payload['seconds']).isdigit() or not 4<=int(payload['seconds'])<=12:
                raise ValueError(f'{shot["id"]}: seconds 必须是 "4"–"12" 的字符串')
            if payload['size'] not in SUPPORTED_SIZES:
                raise ValueError(f'{shot["id"]}: size 只能是 {SUPPORTED_SIZES} 之一，不能传像素')
            for banned in ('width','height','fps','num_frames','frame_rate','duration',
                           'resolution','negative_prompt','quality','num_inference_steps'):
                if banned in payload:
                    raise ValueError(f'{shot["id"]}: {banned} 已被 agnes-video-2.5 拒绝，不要传')
            reference=shot.get('reference_image')
            if reference:
                if not str(reference).startswith('https://'):
                    raise ValueError(f'{shot["id"]}: reference_image 必须是公开 https 地址（Agnes 只在服务器侧取图）')
                if payload['mode']!='keyframe' or payload.get('first_frame')!=reference:
                    raise ValueError(f'{shot["id"]}: 露脸镜头必须用 keyframe 模式并把定妆照作为 first_frame')
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


def push_provenance():
    """把 checkpoint 推回分支；**永远不抛异常**。

    两段血泪史：
    - 2026-10-10：GitHub 瞬时 5xx 让一次 push 失败杀死整轮（run 38024372451）；
    - 2026-10-11 第 4 轮日志实证：探针 workflow 途中 push 了一个 commit 后，本 runner
      的 push 全被拒、rebase 也失败，checkpoint 抛出的 CalledProcessError 把真正的
      ProviderCapacity 掩盖成「真 bug」→ 退出码 1 → 接力步骤按契约不接力 → 静默断档。
    所以：推送被拒就 fetch+rebase，rebase 失败 abort 后 merge -X ours；
    全失败就老实记下、继续生成——记账是尽力而为，生成才是本体。
    """
    for attempt in range(4):
        try:
            git('push','origin',BRANCH);return
        except subprocess.CalledProcessError:
            time.sleep(5*(attempt+1))
            try:
                git('fetch','origin',BRANCH)
                git('rebase','FETCH_HEAD')
            except subprocess.CalledProcessError:
                subprocess.run(['git','rebase','--abort'],cwd=ROOT,
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    git('-c','user.name=arena-agent','-c','user.email=arena@local',
                        'merge','-X','ours','--no-edit','FETCH_HEAD')
                except subprocess.CalledProcessError:
                    pass
            print('PROVENANCE_PUSH_RETRY attempt=%d'%(attempt+1),flush=True)
    print('PROVENANCE_PUSH_GIVEUP: 检查点留在本地，继续生成，收尾步骤会再推',flush=True)

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
    parser.add_argument('--wait-for-channel',type=float,default=None,
                        help='供应商报「没有可用通道」时，最多等多少分钟（0=立刻诚实失败）；'
                             '覆盖 payload 里的 wait_channel_minutes')
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
    global MODEL,SIZE_TIER
    if str(options.get('model') or '').strip():
        MODEL=str(options['model']).strip()
        print('MODEL_OVERRIDE '+MODEL,flush=True)
    # 2026-10-10 实测：agnes-video-2.5-flash 只收 720P（「size must be one of 720P」），
    # 主档 agnes-video-2.5 才认 1080P。换档时分辨率要跟着走，所以也做成可覆盖。
    if str(options.get('size') or '').strip():
        SIZE_TIER=str(options['size']).strip()
        if SIZE_TIER not in SUPPORTED_SIZES:
            raise ValueError('size 只能是 %s 之一'%(SUPPORTED_SIZES,))
        print('SIZE_OVERRIDE '+SIZE_TIER,flush=True)
    requested=options.get('only','')
    if not isinstance(requested,str):raise ValueError('only must be comma-separated IDs')
    only={s.strip() for s in requested.split(',') if s.strip()}
    shots=[s for s in project['shots'] if s['kind']=='agnes']
    if only-{s['id'] for s in shots}:raise ValueError('Unknown/non-Agnes shot ID')
    if only:shots=[s for s in shots if s['id'] in only]
    workers=min(2,max(1,int(options.get('workers',2))))
    # 供应商通道不可用时的策略（见文件头的实测记录）。
    channel_error_limit=max(1,int(options.get('channel_error_limit',3)))
    wait_channel_minutes=max(0.0,float(options.get('wait_channel_minutes',0)))
    if args.wait_for_channel is not None:
        wait_channel_minutes=max(0.0,args.wait_for_channel)
    generation_budget_minutes=max(30.0,float(options.get('generation_budget_minutes',170)))
    # Free video model creation is documented at 1 RPM. Two in-flight tasks do
    # not permit bursts of creation requests; they share this paced gate.
    gate=RequestGate(minimum_interval=75)
    # 38 个 Agnes 镜头、共享 75 秒创建间隔：光排队就要 ≈48 分钟，再加生成与下载，
    # 85 分钟（参考项目 24 镜的预算）不够；预算到点只会保存 task_id 等下次续跑，不会丢素材。
    # 「等通道」的时间也算在同一个 deadline 里，总和压在 320 分钟以内（工作流 timeout 350 分钟）。
    total_budget_minutes=min(320.0,wait_channel_minutes+generation_budget_minutes)
    generation_deadline=time.monotonic()+total_budget_minutes*60
    if args.publish:
        if os.getenv('GITHUB_ACTIONS')!='true' or git('branch','--show-current').strip()!=BRANCH:
            raise RuntimeError('Publish only from this fixed Arena branch in Actions')
        git('config','user.name','github-actions[bot]')
        git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    doc=read_json(RESULTS,{'project':project['title'],'model':MODEL,'shots':{}})
    doc['model']=MODEL   # results.json 里留着旧模型名会让 render.py 的模型闸门直接拒绝出片
    if args.prune_failed:
        # 只清理、不生成：出片工作流把它单独作为生成前的步骤。
        # （它要是继续往下跑，就把"清理"变成了第二次全量生成，还会把失败当成自己的失败。）
        stale=prune_stale(doc)
        RESULTS.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
        print('PRUNED_STALE '+json.dumps(stale),flush=True)
        return 0
    doc['phase']='preparing_sources'
    # 上一轮留下的失败原因不属于这一轮：不删掉，results.json 会一直挂着旧错误，
    # 让人以为修好的 bug 又复发（2026-10-10 的 push_provenance 就被误读了两次）。
    doc.pop('pipeline_error',None)
    doc.pop('provider_outage',None)
    doc['review']={'status':'pending','scope':'visual/audio quality','blocking_generation':False,
                   'note':'No automatic visual approval. Export is an unreviewed first cut.'}
    doc['workflow_policy']='cloud-first-cut-v4-channel-aware'
    doc['rate_policy']={'minimum_creation_interval_seconds':75,'poll_interval_seconds':25,
                        'shared_retry_after_cooldown':True,'key_rotation':False,
                        'channel_cooldown_seconds':CHANNEL_COOLDOWN_SECONDS,
                        'channel_error_limit':channel_error_limit,
                        'wait_channel_minutes':wait_channel_minutes,
                        'total_budget_minutes':total_budget_minutes}
    doc['required_generated_shots']=[s['id'] for s in project['shots'] if s['kind']=='agnes']
    sources=ROOT/'work/kitakyushu2002/sources';sources.mkdir(parents=True,exist_ok=True)
    export=ROOT/'work/kitakyushu2002/clips';export.mkdir(parents=True,exist_ok=True)
    qa=ROOT/'production/kitakyushu2002/qa';qa.mkdir(parents=True,exist_ok=True)
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
                # 记账（add/commit/push）任何失败都只记日志、不抛——
                # 第 4 轮日志实证：这里一抛，真因 ProviderCapacity 就被掩盖成 rc=1，接力停摆。
                try:
                    git('add','--',*paths)
                    if subprocess.run(['git','diff','--cached','--quiet','--',*paths],cwd=ROOT).returncode:
                        git('commit','-m','kitakyushu2002: '+label,'--',*paths)
                        push_provenance()
                except Exception as exc:
                    print('CHECKPOINT_GIT_FAILED %s: %r'%(label,exc),flush=True)
            print('PRODUCTION_STATUS '+label,flush=True)

    def probe_provider():
        """问网关「这个模型现在有没有通道」。

        ``GET /v1/models`` 不创建任务、不花视频额度，所以可以在开跑前和放弃前各量一次，
        把「到底是我们的请求有问题，还是供应商没有通道」这件事变成仓库里的一张收据
        （``delivery/provider-probe.json``）。沙箱连不上 Agnes，只有 runner 能量。
        """
        receipt={'model':MODEL,'base':base,'probed_at':now_stamp(),
                 'api_key_present':bool(key),
                 # 只留指纹，不留 key：换过 key 之后要能一眼看出跑的是哪一把
                 'api_key_sha256_12':hashlib.sha256(key.encode()).hexdigest()[:12] if key else None,
                 'api_key_last4':key[-4:] if key else None}
        try:
            code,body,text=agnes.http_json('GET',base+'/v1/models',key,timeout=30)
            ids=[]
            data=body.get('data') if isinstance(body,dict) else None
            if isinstance(data,list):
                ids=[str(x.get('id')) for x in data if isinstance(x,dict) and x.get('id')]
            elif isinstance(data,dict):
                ids=[str(k) for k in data]
            receipt.update(http_status=code,models=ids[:300],
                           target_model_listed=MODEL in ids,
                           body_excerpt=' '.join((text or '').split())[:600])
        except Exception as exc:   # 网关没有这个端点也不影响生成，如实记下就行
            receipt['error']=str(exc)[:300]
        # 余额（不花额度）：2026-10-10 卡在 403「Insufficient user quota, remaining: ＄0.000000」，
        # 而沙箱既连不上 Agnes、也读不到 Actions 日志 —— 只有把额度问出来写进收据，
        # 才不用靠「投一轮看它红不红」来判断 key 有没有钱。
        receipt['billing']=[]
        for path in ('/dashboard/billing/subscription','/dashboard/billing/usage'):
            try:
                code,_body,text=agnes.http_json('GET',base+path,key,timeout=30)
                receipt['billing'].append({'path':path,'http_status':code,
                                           'excerpt':' '.join((text or '').split())[:400]})
            except Exception as exc:
                receipt['billing'].append({'path':path,'error':str(exc)[:200]})
        PROBE.parent.mkdir(parents=True,exist_ok=True)
        PROBE.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        print('PROVIDER_PROBE '+json.dumps(
            {k:receipt[k] for k in ('http_status','target_model_listed','error') if k in receipt},
            ensure_ascii=False),flush=True)
        return receipt

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

    def record_outage(sid,round_no,cooldown,error,outage,reason='供应商侧没有可用容量'):
        """把这次通道不可用写进 results.json（沙箱读不到 Actions 日志，只能靠它）。"""
        with LOCK:
            doc['provider_outage']={
                'model':MODEL,'base':base,
                'first_seen':outage['first_seen'],'last_seen':outage['last_seen'],
                'create_attempts':outage['attempts'],'consecutive_rounds':round_no,
                'cooldown_seconds':cooldown,'channel_error_limit':channel_error_limit,
                'wait_channel_minutes':wait_channel_minutes,'last_error':error,
                'reason':reason}
        checkpoint(sid+' provider channel unavailable',sid,status='provider_unavailable',
                   channel_error_round=round_no,applied_cooldown_seconds=cooldown,error=error)
        checkpoint('provider channel unavailable (round %d)'%round_no)

    breaker=ChannelBreaker(gate,generation_deadline,error_limit=channel_error_limit,
                           wait_minutes=wait_channel_minutes,record=record_outage,
                           probe=probe_provider,abort=ABORT)

    def create_paced(sid,payload):
        rate_attempts=0
        fatal_attempts=0
        while True:
            if ABORT.is_set():
                raise ProviderCapacity('Provider capacity already exhausted in this run')
            checkpoint(sid+' waiting for a creation slot',sid,status='waiting_create_slot',error=None)
            gate.acquire_creation(generation_deadline)
            try:
                # Only this outer policy retries 429, so every attempt is paced.
                created=agnes.create_task(base,key,payload,retries=1,retry_delay=75)
            except agnes.RateLimited as exc:
                rate_attempts+=1
                if rate_attempts>8:
                    raise
                cooldown=max(min(300,75*(2**(rate_attempts-1))),exc.retry_after or 0)
                checkpoint(sid+' provider cooldown',sid,status='rate_limited',
                           quota_retry=rate_attempts,provider_retry_after_seconds=exc.retry_after,
                           applied_cooldown_seconds=cooldown,error=str(exc).replace(key,'[redacted]')[:600])
                gate.defer(cooldown)
                continue
            except agnes.Fatal as exc:
                text=str(exc)
                redacted=(text.replace(key,'[redacted]') if key else text)[:600]
                if quota_exhausted(text):
                    ABORT.set()
                    probe_provider()
                    raise QuotaExhausted(
                        'Agnes 账号额度已用尽：%s。请充值或换一把 AGNES_API_KEY 再触发一轮；'
                        '已完成的镜头按 SHA-256 复用，不会重复扣费。'%redacted)
                capacity=capacity_problem(text)
                if capacity:
                    reason,cooldown=capacity
                    breaker.observe(sid,redacted,reason=reason,cooldown=cooldown)
                    continue   # 放弃时 observe 会抛 ProviderCapacity
                # 其他 5xx（502/504 之类）仍按原来的每镜退避扛过去。
                if 'HTTP 5' not in text:
                    raise
                fatal_attempts+=1
                if fatal_attempts>8:
                    raise
                cooldown=max(min(300,75*(2**(fatal_attempts-1))),120)
                checkpoint(sid+' provider 5xx',sid,status='provider_unavailable',
                           quota_retry=fatal_attempts,applied_cooldown_seconds=cooldown,error=redacted)
                gate.defer(cooldown)
                continue
            breaker.note_success()
            return created

    def generate(shot):
        sid=shot['id'];payload=full_payload(project,shot);wanted_hash=request_hash(project,shot)
        if ABORT.is_set():
            print(sid+': skipped, provider capacity exhausted',flush=True)
            return False
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
                           requested_seconds=float(payload['seconds']))
            else:print(sid+': resuming existing provider task',flush=True)
            remaining=generation_deadline-time.monotonic()
            if remaining<30:raise BudgetExhausted('Generation budget reached; task ID was saved for resumption')
            final,url=agnes.poll_task(base,key,MODEL,str(video_id),str(task_id) if task_id else None,
                                     interval=25,timeout=min(1500,remaining),max_failures=12,
                                     before_request=lambda:gate.wait_unblocked(generation_deadline),
                                     rate_limit_callback=gate.defer)
            size=agnes.download(url,dest,retries=3,retry_delay=5)
            checksum=digest(dest)
            receipt={'video_url':url,'bytes':size,'sha256':checksum,'request_hash':wanted_hash}
            checkpoint(sid+' generated',sid,status='generated',video_url=url,bytes=size,sha256=checksum,
                       reported_size=final.get('size'),reported_seconds=final.get('seconds'),error=None)
            return finish_asset(shot,receipt,dest,wanted_hash)
        except (ProviderCapacity,QuotaExhausted):
            # 「供应商没通道」「账号没额度」都是整轮的事，不是这一镜的事：吞掉它，phase 就会
            # 写成 generation_incomplete，看起来像素材没做完，而不是外部条件不具备。
            raise
        except Exception as exc:
            error=str(exc).replace(key,'[redacted]') if key else str(exc)
            checkpoint(sid+' failed',sid,status='failed',error=error[:600])
            return False

    try:
        ensure_tools()
        doc['phase']='generating_sources'
        probe_provider()
        checkpoint('cloud generation started',files=[PROBE] if PROBE.is_file() else ())
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes=list(pool.map(generate,shots))
        if not all(outcomes):
            doc['phase']='generation_incomplete';checkpoint('generation incomplete')
            (export/'未完成说明.txt').write_text('生成尚未完成，未导出成片。请查看 production/kitakyushu2002/results.json。\n')
            for p in sources.glob('*.mp4'):shutil.copy2(p,export/p.name)
            return 1
        if only:
            doc['phase']='selected_sources_ready';checkpoint('selected sources ready')
            for sid in only:shutil.copy2(sources/(sid+'.mp4'),export/(sid+'.mp4'))
            return 0
        doc['phase']='preparing_cloud_edit';checkpoint('preparing cloud edit')
        python=render_python(ROOT);edit=ROOT/'work/kitakyushu2002/edit';edit.mkdir(parents=True,exist_ok=True)
        doc['phase']='rendering_first_cut';checkpoint('rendering first cut')
        staging=edit/'first-cut.mp4'
        subprocess.run([str(python),str(Path(__file__).with_name('render.py')),
                        '--sources',str(sources),'--work',str(edit),'--output',str(staging)],check=True)
        final_name='北九州监禁案：逃出魔窟的少女，七条人命背后的秘密_三分钟_初版.mp4'
        shutil.move(staging,export/final_name)
        delivery=ROOT/'production/kitakyushu2002/delivery';delivery.mkdir(parents=True,exist_ok=True)
        names=['technical-report.json','edit-decision-list.json','narration-timing.json',
               'caption-timing.json','alignment-report.json','captions.srt','final-contact.jpg']
        saved=[]
        for name in names:
            path=delivery/name;shutil.copy2(edit/name,path);saved.append(path)
        report=read_json(delivery/'technical-report.json',{})
        report['output']=final_name
        (delivery/'technical-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        shutil.copy2(delivery/'technical-report.json',export/'技术检查.json')
        shutil.copy2(delivery/'captions.srt',export/'北九州监禁案：逃出魔窟的少女，七条人命背后的秘密_字幕.srt')
        shutil.copy2(ROOT/'production/kitakyushu2002/screenplay.md',export/'剧本与来源.md')
        (export/'交付说明.txt').write_text(
            '北九州监禁案：逃出魔窟的少女，七条人命背后的秘密\n180秒 / 1920×1080 / 30fps / 中文解说\n'
            '使用 Agnes '+MODEL+' 生成镜头，配音来自用户选定的声音。\n'
            '此文件是技术检查通过的初版；视觉与听感仍需审核，不声称已逐帧或逐字验收。\n'
            'AI情景重现并非历史影像；未经证实的推测没有被写成事实。\n')
        doc['phase']='first_cut_ready'
        doc['delivery']={**report,'artifact_name':'kitakyushu2002-agnes-'+os.getenv('GITHUB_RUN_NUMBER','local')}
        checkpoint('three-minute first cut ready',files=saved)
        summary=os.getenv('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary,'a') as f:
                f.write(f'## 北九州监禁案：逃出魔窟的少女，七条人命背后的秘密 · 三分钟初版\n\n{len(shots)}段Agnes素材已完成解码检查并剪辑，身份介绍另使用档案肖像。\n\n')
                f.write(f'输出：**{final_name}**，180秒；视觉/听感仍待人工审核。\n\n')
                f.write('成片在本次运行的 `kitakyushu2002-agnes-*` artifact 中。大视频未提交到Git。\n')
        print('CLOUD_FIRST_CUT_READY '+final_name,flush=True);return 0
    except Exception as exc:
        error=str(exc).replace(key,'[redacted]') if key else str(exc)
        # 「供应商没通道」和「流水线自己有 bug」是两件事，phase 必须分开：
        # 混在一起，下一个人（或下一次的我）会去改根本没有坏的代码。
        # 退出码是接力步骤的命根子（沙箱读不到 Actions 日志，git push 也可能失败）：
        #   42 = 供应商容量满（可自动接力）  43 = 额度耗尽（停下等人）  1 = 真 bug（停下等人）
        code=43 if isinstance(exc,QuotaExhausted) else 42 if isinstance(exc,ProviderCapacity) else 1
        doc['phase']=('quota_exhausted' if isinstance(exc,QuotaExhausted)
                      else 'provider_capacity' if isinstance(exc,ProviderCapacity)
                      else 'pipeline_failed')
        doc['pipeline_error']=error[:800]
        try:
            # 先落盘（不走 git）：接力步骤在同一台机器上读 results.json，push 全失败也误不了事；
            # checkpoint / 说明文件再尽力而为，失败也不影响退出码。
            RESULTS.write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n')
            checkpoint('pipeline stopped',files=[PROBE] if PROBE.is_file() else ())
            (export/'未完成说明.txt').write_text('制作未完成：'+error[:800]+'\n没有把测试图或静态图冒充Agnes成片。\n')
        except Exception as inner:
            print('DIAG WRITE FAILED: %r'%inner,flush=True)
        traceback.print_exc()
        return code


if __name__=='__main__':raise SystemExit(main())
