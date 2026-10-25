#!/usr/bin/env python3
"""用智谱 CogVideoX-Flash（免费档）生成本片 38 个动态镜头。

2026-10-11 用户拍板：Agnes 免费档供应商排队严重超订（实测 23 抽 1 中、76 抽 0 中），
改走仓库里已实测跑通的智谱流水线（production/jeong2000/，一轮 3–4 分钟）。
本脚本是那套引擎的本项目移植版：

- payload 稳定三字段 ``model/prompt/quality``（重试幂等、请求哈希可复现）；
- prompt = style_prefix + 镜头 prompt + 本片红线 ``PROMPT_GUARDRAILS``
  （从 generate.py 导入，单一出处；红线永不渲染进视频模型之外的地方）；
- SHA-256 收据、断点续跑、QA 接触表与 Agnes 路径同构，render.py 认同一 schema；
- Agnes 已出的 3 镜在首次开跑时移入 ``backup_agnes_shots`` 备用，不被覆盖；
- 记账（commit/push）尽力而为、**永不抛异常**（第 4 轮日志实证的血泪：记账失败
  一旦抛异常就会掩盖真因、污染退出码）。

Run:  AGNES 不用；ZHIPUAI_API_KEY=... python3 generate_cogvideox.py --publish --payload '{}'
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLAN = HERE / 'story.json'
RESULTS = HERE / 'results.json'
BRANCH = 'arena/44a8fff6-desktop-tutorial'
sys.path.insert(0, str(HERE))

from model_policy import COGVIDEOX_MODEL as MODEL, PROMPT_GUARDRAILS  # noqa: E402  红线单一出处
import importlib.util as _ilu  # noqa: E402


def _load_sibling(name: str):
    """按唯一模块名加载本项目同名文件，避开别的项目同名模块的 sys.modules 串味。"""
    spec = _ilu.spec_from_file_location(f"kitakyushu2002_{name}", HERE / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_media = _load_sibling("media")
ensure_tools, inspect_clip = _media.ensure_tools, _media.inspect_clip

GRID_SECONDS = 6  # CogVideoX-Flash 免费档单条时长（实测收据为准，render 会按需裁切）

# 本轮要不要用定妆照（image_url）。None=照旧先探测（服务端收不收由真实请求说话）；
# True/False=payload 里 ``{"ref_image": false}`` 强制，用于两种现实：
#   * 免费档的 image_url 队列随负载波动极大 —— 2026-10-12 实测 02:00 探测 429 限流、
#     03:00 探测 supported=true、04:00 带图任务排队 20 分钟以上全部轮询超时，一条
#     带图收据要磨掉一小时；先把不带图的成品补齐、低峰再单独补带图版；
#   * 出片链两侧都认两种哈希（render.py / fetch_sources.py 的 wanted_hashes），
#     所以开关来回切换不会破坏已签收的素材。
REF_IMAGE_MODE = None

# 定妆照探测（2026-10-11 用户要求露脸镜头钉住定妆照）：免费档 cogvideox-flash 此前
# 只实测过纯文生视频三字段 payload（jeong2000 流水线）；SDK 里有 image_url 参数，
# 但服务端收不收只有真实请求能证明。开轮前用第一个带定妆照的镜头发一发带
# image_url 的探测请求：收下 → 带 reference_image 的镜头（S06/S12/S16/S27/S40）
# 用定妆照做图生视频输入，同 Agnes keyframe 首帧的设计意图（把这张脸钉在观众
# 第一眼）；拒绝 → 整轮退回纯文生视频（露脸镜头的 prompt 已内嵌各角色面容
# 描述，跨镜一致靠 face token）。探测结果落 delivery/ref-image-probe.json。
REF_IMAGE_OK = None  # None=未探测（默认纯文生）；True=收下定妆照；False=拒绝
# 探测提交的重试次数：免费档 429/1305「该模型当前访问量过大」是常态，一次失败就判
# unsupported 会让整轮悄悄退回纯文生（2026-10-12 实测：S14/S39 那一轮白等）。
PROBE_ATTEMPTS = 8
PROBE_TASKS = {}     # sid -> 探测已提交的 task_id；主循环直接复用，不浪费免费额度


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def full_payload(project, shot):
    """CogVideoX-Flash 收 model/prompt/quality（+探测通过后带定妆照镜头加 image_url）。"""
    prompt = (project['style_prefix'] + shot['prompt'] + ' ' + PROMPT_GUARDRAILS).strip()
    if len(prompt) > 2600:
        prompt = prompt[:2600]
    payload = {'model': MODEL, 'prompt': prompt, 'quality': 'speed'}
    if REF_IMAGE_OK and shot.get('reference_image'):
        payload['image_url'] = shot['reference_image']
    return payload


def probe_ref_image(client, project, record_path=None):
    """用第一个定妆照镜头探测 flash 收不收 image_url；收下则记下 task id 供主循环复用。

    必须在主循环算 request_hash 之前跑：REF_IMAGE_OK 决定带定妆照镜头的 payload
    形状（进而决定请求哈希），先探测后哈希，整轮内哈希才稳定。
    """
    global REF_IMAGE_OK
    if REF_IMAGE_MODE is not None:
        # 强制模式：跳过探测（省一次真实请求），也**不覆盖**探测收据 ——
        # delivery/ref-image-probe.json 是「服务端此刻收不收」的证据，不是本轮开关。
        REF_IMAGE_OK = bool(REF_IMAGE_MODE)
        print('REF_IMAGE_PROBE skipped: payload 指定 ref_image=%s（%s）'
              % (REF_IMAGE_MODE, '带定妆照' if REF_IMAGE_OK else '纯文生'), flush=True)
        return {'skipped': True, 'supported': REF_IMAGE_OK,
                'reason': 'payload ref_image=%s' % REF_IMAGE_MODE}
    shot = next((s for s in project.get('shots', []) if s.get('reference_image')), None)
    record_path = Path(record_path) if record_path else HERE / 'delivery/ref-image-probe.json'
    if shot is None:
        REF_IMAGE_OK = False
        record = {'supported': False, 'reason': 'no reference_image shot in story'}
    else:
        payload = full_payload(project, shot)  # 此刻 REF_IMAGE_OK 是 None → 纯三字段
        payload['image_url'] = shot['reference_image']
        record = {'shot': shot['id'], 'image_url': payload['image_url'],
                  'payload_keys': sorted(payload)}
        for attempt in range(1, PROBE_ATTEMPTS + 1):
            try:
                response = client.videos.generations(**payload)
                task_id = obj_get(response, 'id')
                if not task_id:
                    raise RuntimeError('No task id: %r' % (response,))
                REF_IMAGE_OK = True
                PROBE_TASKS[shot['id']] = str(task_id)
                record.update(supported=True, task_id=str(task_id), attempts=attempt)
                break
            except Exception as exc:
                # 限流（429/1305）要重试；参数被真正拒收才判 unsupported。
                if retryable(exc) and attempt < PROBE_ATTEMPTS:
                    wait = min(60, 10 + attempt * 5)
                    print('REF_IMAGE_PROBE throttled attempt %d/%d, wait %ds: %s'
                          % (attempt, PROBE_ATTEMPTS, wait, str(exc)[:160]), flush=True)
                    time.sleep(wait)
                    continue
                REF_IMAGE_OK = False
                record.update(supported=False, error=str(exc)[:400], attempts=attempt)
    print('REF_IMAGE_PROBE supported=%s shot=%s' % (REF_IMAGE_OK, record.get('shot')),
          flush=True)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    # 探测结果是「免费档收不收定妆照」的收据，必须随分支走：
    # 2026-10-12 本片实测 flash 拒收 image_url（REF_IMAGE_OK=False），
    # 于是 38 镜全部走纯文生视频 —— 这条证据要能在仓库里查到。
    try:
        rel = str(record_path.relative_to(ROOT))
        git('add', '--', rel)
        if subprocess.run(['git', 'diff', '--cached', '--quiet', '--', rel],
                          cwd=ROOT).returncode:
            git('commit', '-m', 'kitakyushu2002: 定妆照图生视频探测结果', '--', rel)
            push_provenance()
    except Exception as exc:
        print('REF_IMAGE_PROBE_RECORD_GIT_FAILED %r' % (exc,), flush=True)
    return record


def request_hash(project, shot):
    return hashlib.sha256(json.dumps(full_payload(project, shot), sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def parse_ref_image(value):
    """payload 里的 ``ref_image`` 是什么就认什么：None=按探测，bool=直接，字符串=宽松解析。"""
    if value is None or isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def usable_receipt(row, wanted):
    """一条收据是否就是本轮要的那一镜：完成、哈希相同、视频 URL 与校验和都在。"""
    return bool(isinstance(row, dict) and row.get('status') == 'completed'
                and row.get('request_hash') == wanted and row.get('video_url')
                and row.get('sha256'))


def reuse_receipt(doc, sid, wanted):
    """这一镜要不要重新生成：``current`` 现收据可用；``history`` 从历史收据恢复；``generate`` 得重投。

    为什么要能从 ``previous_results`` 恢复：定妆照开关随服务端限流**每轮浮动**，同一镜
    的纯文生版与带图版都可能已经有成品。2026-10-12 实测过一次：这轮探测 supported=true
    → 带图哈希与旧收据不匹配 → 5 个露脸镜全部重投，其中 4 个卡在带图队列里超时，
    把已经花掉的纯文生成品判成了缺料。有了历史恢复，开关怎么抖都不再重复花钱：
    本轮要哪个版本，就先把那版找回来，找不到才生成。
    """
    shots = doc.setdefault('shots', {})
    old = shots.get(sid) or {}
    if usable_receipt(old, wanted):
        return 'current'
    history = doc.setdefault('previous_results', {})
    revived = next((row for row in reversed(history.get(sid) or [])
                    if usable_receipt(row, wanted)), None)
    if revived is None:
        return 'generate'
    if old.get('status') or old.get('request_hash'):
        history.setdefault(sid, []).append(old)
    shots[sid] = dict(revived)
    return 'history'


def validate(project):
    shots = project.get('shots') or []
    dynamic = [s for s in shots if s.get('kind') in ('cogvideo', 'agnes')]
    graphics = [s for s in shots if s.get('kind') == 'graphic']
    if len(shots) != 45 or len(dynamic) != 38 or len(graphics) != 7:
        raise ValueError('Expected 45 shots = 38 dynamic + 7 graphics, got %d/%d/%d'
                         % (len(shots), len(dynamic), len(graphics)))
    for s in dynamic:
        if full_payload(project, s)['model'] != MODEL:
            raise ValueError('Wrong provider model')


def obj_get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True,
                                   stderr=subprocess.STDOUT, timeout=90)


def push_provenance():
    """推回分支；永远不抛（记账是尽力而为，生成才是本体）。"""
    for attempt in range(4):
        try:
            git('push', 'origin', BRANCH)
            return
        except subprocess.CalledProcessError:
            time.sleep(5 * (attempt + 1))
            try:
                git('fetch', 'origin', BRANCH)
                git('rebase', 'FETCH_HEAD')
            except subprocess.CalledProcessError:
                subprocess.run(['git', 'rebase', '--abort'], cwd=ROOT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    git('-c', 'user.name=arena-agent', '-c', 'user.email=arena@local',
                        'merge', '-X', 'ours', '--no-edit', 'FETCH_HEAD')
                except subprocess.CalledProcessError:
                    pass
            print('PROVENANCE_PUSH_RETRY attempt=%d' % (attempt + 1), flush=True)
    print('PROVENANCE_PUSH_GIVEUP: 检查点留在本地，继续生成，收尾再推', flush=True)


def checkpoint(doc, label, sid=None, files=(), publish=False, **values):
    if sid:
        row = doc['shots'].setdefault(sid, {'id': sid})
        row.update(values)
        row['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    doc['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    RESULTS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    if publish:
        try:
            paths = [str(RESULTS.relative_to(ROOT))] + [str(Path(p).relative_to(ROOT)) for p in files]
            git('add', '--', *paths)
            if subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *paths], cwd=ROOT).returncode:
                git('commit', '-m', 'kitakyushu2002: ' + label, '--', *paths)
                push_provenance()
        except Exception as exc:
            print('CHECKPOINT_GIT_FAILED %s: %r' % (label, exc), flush=True)
    print('PRODUCTION_STATUS ' + label, flush=True)


def download(url, dest):
    for attempt in range(4):
        try:
            urllib.request.urlretrieve(url, dest)
            return
        except Exception as exc:
            if attempt == 3:
                raise
            print('download retry %d: %s' % (attempt + 1, str(exc)[:120]), flush=True)
            time.sleep(10 * (attempt + 1))


def retryable(exc):
    text = str(exc).lower()
    return any(x in text for x in ('1305', '429', '访问量过大', 'rate', 'timeout',
                                   'timed out', 'temporar', 'connection', '502', '503', '504'))


def moderation_block(text):
    """供应商内容审核拦截（1301 / 「敏感内容」）——不重投、不致命，跳过这一镜。

    2026-10-12 本片实测：这个错误有两种到达方式，都要接住——
      ① 轮询接口返回 task_status=FAIL（走 outcome=='fail' 分支）；
      ② SDK 直接把 400 抛成 APIRequestFailedError（旧版会穿透 try/except 把整批掐掉，S22 就是这么
         把第 1、2 轮各掐一次的）。被拦的是**这一镜的提示词**，改完提示词下一轮再投即可。
    """
    text = str(text)
    return '1301' in text or '敏感内容' in text


def transient_fail(text):
    """FAIL 里值得重投新任务的瞬时故障签名。

    实证（2026-10-11 S06，gen-diag-cogvideox.log）：任务 PROCESSING 空转 24 分钟后
    FAIL，错误码 1234「网络错误…请稍后重试」——供应商自己都让重试，不能当致命。
    """
    return any(m in str(text) for m in ('1234', '网络错误', '请稍后重试',
                                        '1305', '429', '访问量过大'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', default='{}')
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--publish', action='store_true')
    ap.add_argument('--prune-failed', action='store_true')
    args = ap.parse_args()
    project = read_json(PLAN, {})
    validate(project)
    if args.validate:
        print('VALID: 180-second plan; 45 shots; 38 CogVideoX-Flash sources; 7 graphics')
        return 0
    doc = read_json(RESULTS, {'project': project['title'], 'model': MODEL,
                              'provider': 'Zhipu AI', 'shots': {}})
    old_model = doc.get('model')
    if old_model and old_model != MODEL and doc.get('shots'):
        # Agnes 已出的镜头留作备用，不覆盖、不重花。
        doc['backup_agnes_shots'] = doc['shots']
        doc['shots'] = {}
        checkpoint(doc, 'Agnes 结果移入 backup_agnes_shots 备用', publish=args.publish)
    doc.update(model=MODEL, provider='Zhipu AI', workflow_policy='cogvideox-flash-receipt-v2-refprobe')
    if args.prune_failed:
        stale = [sid for sid, row in doc.get('shots', {}).items()
                 if row.get('status') == 'failed' and not row.get('video_url')]
        for sid in stale:
            doc['shots'].pop(sid, None)
        checkpoint(doc, 'pruned failed tasks', publish=args.publish)
        print('PRUNED', stale)
        return 0
    if args.publish:
        if os.getenv('GITHUB_ACTIONS') != 'true' or git('branch', '--show-current').strip() != BRANCH:
            raise RuntimeError('Publish only from this fixed Arena branch in Actions')
        git('config', 'user.name', 'github-actions[bot]')
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    options = json.loads(args.payload or '{}')
    global REF_IMAGE_MODE
    raw_ref = options.get('ref_image')
    if raw_ref is not None:
        REF_IMAGE_MODE = parse_ref_image(raw_ref)
        print('REF_IMAGE_MODE=%s (payload override)' % REF_IMAGE_MODE, flush=True)
    only = {x.strip() for x in str(options.get('only', '')).split(',') if x.strip()}
    shots = [x for x in project['shots'] if x.get('kind') in ('cogvideo', 'agnes')]
    if only - {x['id'] for x in shots}:
        raise ValueError('Unknown/non-dynamic shot: ' + ','.join(sorted(only)))
    if only:
        shots = [x for x in shots if x['id'] in only]
    key = os.getenv('ZHIPUAI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('ZHIPUAI_API_KEY is unavailable to this workflow')
    from zhipuai import ZhipuAI
    client = ZhipuAI(api_key=key)
    # 先探测定妆照支持性，再进主循环（request_hash 依赖 REF_IMAGE_OK）。
    probe_ref_image(client, project)
    sources = ROOT / 'work/kitakyushu2002/sources'
    qa = HERE / 'qa'
    sources.mkdir(parents=True, exist_ok=True)
    qa.mkdir(parents=True, exist_ok=True)
    ensure_tools()
    deadline = time.monotonic() + 330 * 60
    doc['phase'] = 'generating_sources'
    doc['required_generated_shots'] = [x['id'] for x in project['shots']
                                       if x.get('kind') in ('cogvideo', 'agnes')]
    checkpoint(doc, 'CogVideoX cloud generation started', publish=args.publish)
    failures = []
    for index, shot in enumerate(shots, 1):
        sid = shot['id']
        wanted = request_hash(project, shot)
        disposition = reuse_receipt(doc, sid, wanted)
        if disposition == 'current':
            print('%s: verified receipt already exists; no new generation' % sid, flush=True)
            continue
        if disposition == 'history':
            print('%s: stored receipt restored from previous_results (no new generation)'
                  % sid, flush=True)
            continue
        old = doc.get('shots', {}).get(sid, {})
        if old and old.get('request_hash') != wanted:
            doc.setdefault('previous_results', {}).setdefault(sid, []).append(old)
            doc['shots'][sid] = {'id': sid}
        if time.monotonic() > deadline:
            raise RuntimeError('Generation deadline reached; rerun resumes from receipts')
        payload = full_payload(project, shot)
        result = None
        last_error = None
        # 每镜最多 3 次提交：FAIL（瞬时签名）或轮询超时都重投新任务；三连败才记
        # failed 并继续下一镜——本轮不死，缺口由下一轮按收据补（2026-10-11 S06 教训）。
        for submission in range(1, 4):
            task_id = PROBE_TASKS.pop(sid, None) \
                if (submission == 1 and payload.get('image_url')) else None
            if task_id:
                print('%s: reusing ref-image probe submission %s' % (sid, task_id), flush=True)
            checkpoint(doc, sid + ' submitting', sid, publish=args.publish,
                       status='submitting', request_hash=wanted, error=None)
            for attempt in range(1, 21):
                if task_id:
                    break
                try:
                    response = client.videos.generations(**payload)
                    task_id = obj_get(response, 'id')
                    if not task_id:
                        raise RuntimeError('No task id: %r' % (response,))
                    break
                except Exception as exc:
                    if not retryable(exc) or attempt == 20:
                        raise
                    wait = min(120, 15 + attempt * 5)
                    print('%s: submit throttled attempt %d, wait %ds: %s'
                          % (sid, attempt, wait, str(exc)[:180]), flush=True)
                    time.sleep(wait)
            checkpoint(doc, sid + ' queued', sid, publish=args.publish,
                       status='queued', task_id=str(task_id), request_hash=wanted)
            outcome = 'timeout'
            for poll in range(1, 121):
                try:
                    polled = client.videos.retrieve_videos_result(id=task_id)
                    status = str(obj_get(polled, 'task_status', '')).upper()
                    print('%s [%d/%d] submission %d poll %d: %s'
                          % (sid, index, len(shots), submission, poll, status), flush=True)
                    if status == 'SUCCESS':
                        result = polled
                        outcome = 'success'
                        break
                    if status == 'FAIL':
                        outcome = 'fail'
                        last_error = str(obj_get(polled, 'error', '') or polled)[:600]
                        break
                    time.sleep(10)
                except Exception as exc:
                    if moderation_block(exc):
                        blocker = 'content moderation (1301)'
                        print('%s: %s; skipping to the next shot' % (sid, blocker), flush=True)
                        checkpoint(doc, sid + ' blocked (' + blocker + ')', sid, publish=args.publish,
                                   status='failed', request_hash=wanted, error=str(exc)[:600])
                        failures.append(sid)
                        result = None
                        outcome = 'blocked'
                        break
                    if retryable(exc) and poll < 120:
                        time.sleep(min(60, 10 + poll // 10))
                        continue
                    raise
            if outcome == 'success':
                break
            if outcome == 'blocked':
                break
            if outcome == 'fail' and not transient_fail(last_error):
                # 供应商内容审核（1301）、参数被拒等**单镜**故障：记 failed 后继续跑下一镜，
                # 不让一镜的问题把整批 38 镜全掐掉（2026-10-12 本片 S22 实测：1301 触发后
                # 旧版直接 raise，整轮 18/38 就此中断）。缺口由下一轮按收据补，或改完提示词再投。
                blocker = 'content moderation' if '1301' in last_error else 'non-transient provider failure'
                checkpoint(doc, sid + ' failed (' + blocker + ')', sid, publish=args.publish,
                           status='failed', request_hash=wanted, error=last_error[:600])
                failures.append(sid)
                print('%s: %s; skipping to the next shot' % (sid, blocker), flush=True)
                break
            print('%s: submission %d ended %s (%s); resubmitting'
                  % (sid, submission, outcome, (last_error or 'polling timeout')[:200]),
                  flush=True)
            time.sleep(30)
        if result is None:
            if outcome == 'blocked':
                continue
            checkpoint(doc, sid + ' failed after 3 submissions', sid, publish=args.publish,
                       status='failed', request_hash=wanted,
                       error=(last_error or 'polling timeout')[:600])
            failures.append(sid)
            continue
        video_result = obj_get(result, 'video_result') or []
        first = video_result[0] if video_result else None
        url = obj_get(first, 'url') if first else None
        if not url:
            raise RuntimeError('%s: SUCCESS without video URL: %r' % (sid, result))
        dest = sources / ('%s.mp4' % sid)
        download(url, dest)
        checksum = digest(dest)
        try:
            info = inspect_clip(dest, qa, sid)
        except Exception as exc:
            checkpoint(doc, sid + ' failed inspection', sid, publish=args.publish,
                       status='failed', request_hash=wanted, task_id=str(task_id),
                       video_url=url, error=str(exc)[:600])
            failures.append(sid)
            continue
        files = [qa / ('%s.jpg' % sid), qa / ('%s.json' % sid)]
        checkpoint(doc, sid + ' media and QA ready', sid, files=files, publish=args.publish,
                   status='completed', request_hash=wanted, task_id=str(task_id),
                   video_url=url, sha256=checksum, bytes=dest.stat().st_size,
                   media=info, error=None)
    complete = [sid for sid, row in doc.get('shots', {}).items() if row.get('status') == 'completed']
    missing = sorted(set(doc['required_generated_shots']) - set(complete))
    doc['phase'] = 'selected_sources_ready' if only and not failures else \
        'sources_ready' if not missing else 'generation_incomplete'
    checkpoint(doc, 'CogVideoX generation pass finished (missing=%d failed=%d)'
               % (len(missing), len(failures)), publish=args.publish)
    print('COMPLETE %d requested clips; model=%s' % (len(shots), MODEL), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
