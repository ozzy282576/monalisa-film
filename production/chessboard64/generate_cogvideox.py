#!/usr/bin/env python3
"""用智谱 CogVideoX-Flash（免费档）生成本片 38 个动态镜头。

本脚本只调用已配置的智谱兼容 API；校验模式不联网、不消耗额度。生产流程包括：

- payload 固定为 ``model/prompt/quality``，请求哈希可复现；
- ``build_story.compose_prompt`` 统一拼接 STYLE、逐镜角色设定、动作描述与 NEGATIVE；
- 生成结果逐条登记 URL、请求哈希、字节数与 SHA-256，供按需恢复和渲染验收；
- 支持断点续跑、接触表质检和 Actions 工作流记账；媒体不会提交到 Git。

Run: ``python3 generate_cogvideox.py --validate`` 只验证计划；生成时使用
``ZHIPUAI_API_KEY``，本地运行 ``python3 generate_cogvideox.py`` 或由专用 workflow 执行。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLAN = HERE / 'story.json'
RESULTS = HERE / 'results.json'
BRANCH = 'arena/56672981-monalisa-film'
sys.path.insert(0, str(HERE))

from model_policy import COGVIDEOX_MODEL as MODEL  # noqa: E402
from build_story import compose_prompt  # noqa: E402
import importlib.util as _ilu  # noqa: E402


def _load_sibling(name: str):
    """按唯一模块名加载本项目同名文件，避开别的项目同名模块的 sys.modules 串味。"""
    spec = _ilu.spec_from_file_location(f"chessboard64_{name}", HERE / f"{name}.py")
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
# 若后续明确启用参考图，先探测 API 是否接受 image_url；当前故事计划未指定图生视频素材，
# 因而校验和默认生成均走纯文生视频。探测结果落 delivery/ref-image-probe.json。
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
    """按用户规范拼 prompt：STYLE → 本镜角色设定 → 镜头动作 → NEGATIVE。

    CogVideoX-Flash 的接口没有独立 negative_prompt 字段，所以红线必须作为正文尾缀发出。
    """
    prompt = compose_prompt(project, shot)
    if len(prompt) > 2600:
        raise ValueError('%s: fully assembled prompt exceeds CogVideoX-Flash 2600-character limit' % shot['id'])
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
            git('commit', '-m', 'chessboard64: 定妆照图生视频探测结果', '--', rel)
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


def archive_inactive_receipts(doc, active_ids):
    """Move receipts for shots that are no longer dynamic into history, never reuse them as active clips."""
    shots = doc.setdefault('shots', {})
    history = doc.setdefault('previous_results', {})
    archived = []
    for sid in sorted(set(shots) - set(active_ids)):
        row = shots.pop(sid)
        if not isinstance(row, dict) or not row:
            continue
        prior = history.setdefault(sid, [])
        if not any(isinstance(old, dict) and old.get('request_hash') == row.get('request_hash')
                   and old.get('status') == row.get('status') for old in prior):
            prior.append(row)
        archived.append(sid)
    return archived


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


def prepare_forced_regeneration(doc, sid, wanted):
    """Archive same-prompt receipts as expired so an explicit refresh cannot revive stale URLs."""
    shots = doc.setdefault('shots', {})
    history = doc.setdefault('previous_results', {}).setdefault(sid, [])
    current = shots.get(sid) or {}
    if current.get('request_hash') == wanted and (current.get('status') == 'completed'
                                                  or current.get('task_id')):
        # 同时保留「已完成」和「交了但没收」的收据：后者的 task_id 是上一轮被取消时
        # 留下的在跑任务，收获它比重投省一次额度，也绕开了 1305 限流。
        archived = dict(current)
        archived['status'] = 'expired' if current.get('status') == 'completed' else 'unharvested'
        archived['error'] = 'Archived before explicit source-URL refresh'
        history.append(archived)
    for previous in history:
        if (isinstance(previous, dict) and previous.get('request_hash') == wanted
                and previous.get('status') == 'completed'):
            previous['status'] = 'expired'
            previous['error'] = 'Archived before explicit source-URL refresh'
    shots[sid] = {'id': sid}


def validate(project):
    shots = project.get('shots') or []
    dynamic = [s for s in shots if s.get('kind') == 'cogvideo']
    graphics = [s for s in shots if s.get('kind') == 'graphic']
    if len(shots) != 45 or len(dynamic) != 38 or len(graphics) != 7:
        raise ValueError('Expected 45 shots = 38 dynamic + 7 graphics, got %d/%d/%d'
                         % (len(shots), len(dynamic), len(graphics)))
    if project.get('model') != MODEL:
        raise ValueError('story.json model must be %s, got %r' % (MODEL, project.get('model')))
    if [s.get('id') for s in shots] != [f'S{i:02d}' for i in range(1, 46)]:
        raise ValueError('Shot IDs must be contiguous and ordered S01–S45')
    presentation = project.get('presentation') or {}
    if set(presentation.get('cards') or {}) != {s['id'] for s in graphics}:
        raise ValueError('Every graphic slot needs exactly one information-card text block')
    if presentation.get('end_card_shot') != shots[-1]['id'] or shots[-1].get('kind') != 'graphic':
        raise ValueError('The final card must be the last of the seven graphic slots (S45)')
    if sum(c.get('duration', 0) for c in project.get('chapters', [])) != 180:
        raise ValueError('Narration chapters must total 180 seconds')
    for index, s in enumerate(shots):
        if s.get('start') != index * 4 or s.get('duration') != 4:
            raise ValueError('%s: invalid 4-second planning grid' % s.get('id'))
        if s.get('kind') == 'graphic':
            if s.get('prompt') or not s.get('graphic'):
                raise ValueError('%s: information cards are post-render typography, not AI video prompts' % s['id'])
            continue
        payload = full_payload(project, s)
        if payload['model'] != MODEL:
            raise ValueError('Wrong provider model')
        prompt = payload.get('prompt', '')
        if not prompt.startswith('【STYLE】') or '【NEGATIVE】' not in prompt:
            raise ValueError('%s: missing STYLE or NEGATIVE prompt section' % s['id'])
        if s.get('characters') and '【角色设定：' not in prompt:
            raise ValueError('%s: missing per-shot character settings' % s['id'])
        if not s.get('prompt', '').strip():
            raise ValueError('%s: missing continuous-motion shot description' % s['id'])


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
                git('commit', '-m', 'chessboard64: ' + label, '--', *paths)
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
            # HTTP exception text may contain a full signed URL; log only a safe status/type.
            reason = getattr(exc, 'code', None) or type(exc).__name__
            print('download retry %d: %s' % (attempt + 1, reason), flush=True)
            time.sleep(10 * (attempt + 1))


MIN_REFRESH_URL_TTL_SECONDS = 6 * 60 * 60
# 提交被限流时每隔几次重试写一个检查点，沙箱才看得到「还在重投」而不是「卡死」。
SUBMIT_PROGRESS_EVERY = 5
# 提交与收获分两段跑：1305「该模型当前访问量过大」是全模型级限流，和具体镜头无关，
# 所以轮流扫所有待生成镜头抢放行窗口，任务交给服务端并行出片，本地不再交一条等一条
# （实测 2026-10-26：串行模式下 S19、S07 各自卡在提交阶段几十分钟，后面 20 多镜一个没轮上）。
SUBMIT_PHASE_SECONDS = 240 * 60
HARVEST_SWEEP_SECONDS = 15


def redact(text):
    """错误文本可能带签名链接或密钥，落盘前抹掉。"""
    cleaned = re.sub(r'https?://[^\s\'"]+', '[URL_REDACTED]', str(text))
    cleaned = re.sub(r'(?i)(api[_-]?key|authorization|signature|token)(["\'\s:=]+)[^\s\'",}]+',
                     lambda m: m.group(1) + m.group(2) + '[REDACTED]', cleaned)
    return cleaned


def signed_url_expiry(url):
    """Return a signed link's Unix expiry without ever logging its query parameters."""
    try:
        query = parse_qs(urlsplit(str(url)).query)
        values = query.get('Expires') or query.get('expires') or []
        return int(values[0]) if values else None
    except (TypeError, ValueError):
        return None


def unharvested_task(doc, sid, wanted):
    """上一轮交出去却没收回来的同提示词任务 ID（供本轮继续轮询，不重复花额度）。"""
    for old in reversed(doc.get('previous_results', {}).get(sid, []) or []):
        if not isinstance(old, dict) or old.get('request_hash') != wanted:
            continue
        if old.get('task_id') and not old.get('sha256'):
            return str(old['task_id'])
    return None


def refresh_forced_source_from_task(client, doc, sid, wanted, sources, qa, publish=False):
    """Re-fetch a completed matching provider task and use only a newly valid signed URL.

    CogVideoX's result endpoint may re-issue a signed media URL for an old completed task.
    This is a no-cost recovery path for expired URLs; the old URL is never reused, and the
    downloaded media must still match the archived SHA-256 before the receipt is restored.
    If the task endpoint returns the old/expired link or no result, normal generation follows.
    """
    attempted = set()
    history = doc.get('previous_results', {}).get(sid, [])
    dest = Path(sources) / ('%s.mp4' % sid)
    qa_json = Path(qa) / ('%s.json' % sid)
    for old in reversed(history):
        task_id = old.get('task_id') if isinstance(old, dict) else None
        # 没有 SHA 的历史条目来自「提交了但还没收获」的任务（上一轮被取消时留下的）：
        # 任务 ID 对应的就是同一条提示词，照样可以收获，只是没有旧校验和可比对。
        expected = old.get('sha256') if isinstance(old, dict) else None
        if (not task_id or old.get('request_hash') != wanted
                or str(task_id) in attempted):
            continue
        attempted.add(str(task_id))
        temp = dest.with_name(dest.stem + '.task-refresh.tmp.mp4')
        try:
            result = client.videos.retrieve_videos_result(id=str(task_id))
            if str(obj_get(result, 'task_status', '')).upper() != 'SUCCESS':
                continue
            rows = obj_get(result, 'video_result') or []
            url = obj_get(rows[0], 'url') if rows else None
            if not url:
                continue
            expiry = signed_url_expiry(url)
            if expiry is not None and expiry <= time.time() + MIN_REFRESH_URL_TTL_SECONDS:
                print('%s: prior task returned an expired or near-expiry URL; submit a fresh generation'
                      % sid, flush=True)
                continue
            download(url, temp)
            actual = digest(temp)
            if expected and actual != expected:
                print('%s: prior task checksum mismatch; submit a fresh generation' % sid,
                      flush=True)
                continue
            info = inspect_clip(temp, qa, sid)
            temp.replace(dest)
            # Contact sheets are intentionally ignored binary artifacts; stage only text QA.
            checkpoint(doc, sid + ' signed URL refreshed from completed task', sid,
                       files=[qa_json], publish=publish, status='completed',
                       request_hash=wanted, task_id=str(task_id), video_url=url,
                       sha256=actual, bytes=dest.stat().st_size, media=info, error=None)
            print('%s: recovered the matching completed source from its provider task' % sid,
                  flush=True)
            return True
        except Exception as exc:
            # Never print the returned URL or exception text; HTTP errors can embed signed URLs.
            print('%s: prior task URL refresh unavailable (%s); submit a fresh generation'
                  % (sid, type(exc).__name__), flush=True)
        finally:
            if temp.exists():
                temp.unlink()
    return False


RETRY_BASE_SECONDS = 20
RETRY_INCREMENT_SECONDS = 5
RETRY_MAX_SECONDS = 120
# 视频创建接口只负责返回异步任务 ID；不要让 SDK 自带多轮长超时重试，
# 交由下方有检查点的提交循环统一退避，避免单次网络故障卡住数十分钟。
PROVIDER_REQUEST_TIMEOUT_SECONDS = 120
PROVIDER_SDK_MAX_RETRIES = 0


def create_client(api_key):
    """把 SDK 的隐藏重试收敛为一个有界请求，由工作流提交循环负责重试。"""
    from zhipuai import ZhipuAI
    return ZhipuAI(api_key=api_key, timeout=PROVIDER_REQUEST_TIMEOUT_SECONDS,
                   max_retries=PROVIDER_SDK_MAX_RETRIES)


def retry_delay(attempt):
    """第1次拒绝等20秒，后续每次递增5秒（20、25、30、35…），最多120秒。"""
    if attempt < 1:
        raise ValueError('attempt must be >= 1')
    return min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS + (attempt - 1) * RETRY_INCREMENT_SECONDS)


def retryable(exc):
    """识别可恢复的限流、超时与临时服务拒绝；1301审核拦截单独处理。"""
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
    return any(m in str(text).lower() for m in (
        '1234', '网络错误', '请稍后重试', '1305', '429', '访问量过大',
        'rate', 'timeout', 'timed out', 'temporar', 'connection', '502', '503', '504'))


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
        # 保留不同模型生成过的收据和指针，但不把旧素材混进当前 CogVideoX 交付。
        doc['backup_previous_model_shots'] = doc['shots']
        doc['shots'] = {}
        checkpoint(doc, 'previous-model receipts archived', publish=args.publish)
    doc.update(model=MODEL, provider='Zhipu AI', workflow_policy='cogvideox-flash-receipt-v2-refprobe')
    active_ids = {shot['id'] for shot in project['shots'] if shot.get('kind') == 'cogvideo'}
    archived = archive_inactive_receipts(doc, active_ids)
    if archived:
        print('ARCHIVED_INACTIVE_RECEIPTS', ','.join(archived), flush=True)
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
    shots = [x for x in project['shots'] if x.get('kind') == 'cogvideo']
    if only - {x['id'] for x in shots}:
        raise ValueError('Unknown/non-dynamic shot: ' + ','.join(sorted(only)))
    if only:
        shots = [x for x in shots if x['id'] in only]
    force = options.get('force', False)
    if not isinstance(force, bool):
        raise ValueError('force must be a boolean')
    if force and not only:
        raise ValueError('force regeneration requires an explicit non-empty only list')
    recover_only = options.get('recover_only', False)
    if not isinstance(recover_only, bool):
        raise ValueError('recover_only must be a boolean')
    if recover_only and (not force or not only):
        raise ValueError('recover_only requires force=true and an explicit non-empty only list')
    key = os.getenv('ZHIPUAI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('ZHIPUAI_API_KEY is unavailable to this workflow')
    client = create_client(key)
    # 先探测定妆照支持性，再进主循环（request_hash 依赖 REF_IMAGE_OK）。
    probe_ref_image(client, project)
    sources = ROOT / 'work/chessboard64/sources'
    qa = HERE / 'qa'
    sources.mkdir(parents=True, exist_ok=True)
    qa.mkdir(parents=True, exist_ok=True)
    ensure_tools()
    deadline = time.monotonic() + 330 * 60
    doc['phase'] = 'generating_sources'
    doc['required_generated_shots'] = [x['id'] for x in project['shots']
                                       if x.get('kind') == 'cogvideo']
    checkpoint(doc, 'CogVideoX cloud generation started', publish=args.publish)
    failures = []
    queued = {}
    needs_generation = []
    for shot in shots:
        sid = shot['id']
        wanted = request_hash(project, shot)
        if force:
            prepare_forced_regeneration(doc, sid, wanted)
            checkpoint(doc, sid + ' prior receipt archived for forced refresh', sid, publish=args.publish)
            if refresh_forced_source_from_task(client, doc, sid, wanted, sources, qa,
                                               publish=args.publish):
                continue
            if recover_only:
                error = 'No fresh signed URL was available from a matching completed provider task'
                checkpoint(doc, sid + ' prior task could not refresh the signed URL', sid,
                           publish=args.publish, status='failed', request_hash=wanted,
                           error=error)
                failures.append(sid)
                continue
            disposition = 'generate'
        else:
            disposition = reuse_receipt(doc, sid, wanted)
        if disposition in ('current', 'history'):
            row = doc['shots'][sid]
            print('%s: verified receipt restored (%s); no new generation'
                  % (sid, disposition), flush=True)
            # A prior Actions run may have ended before its ignored contact sheet could
            # be uploaded. Re-fetch completed media on demand and rebuild missing QA,
            # without ever adding MP4/JPG binaries to Git.
            qa_json = qa / ('%s.json' % sid)
            qa_jpg = qa / ('%s.jpg' % sid)
            if not qa_json.is_file() or not qa_jpg.is_file():
                dest = sources / ('%s.mp4' % sid)
                try:
                    download(row['video_url'], dest)
                    actual = digest(dest)
                    if actual != row['sha256']:
                        raise RuntimeError('restored source SHA-256 mismatch: %s != %s'
                                           % (actual, row['sha256']))
                    info = inspect_clip(dest, qa, sid)
                    checkpoint(doc, sid + ' QA restored', sid, files=[qa_json], publish=args.publish,
                               status='completed', request_hash=wanted, video_url=row['video_url'],
                               sha256=actual, bytes=dest.stat().st_size, media=info, error=None)
                except Exception as exc:
                    # An expired URL or damaged cached receipt must not abort the other 37 shots.
                    message = 'Unable to restore prior source for QA: %s' % redact(exc)[:500]
                    checkpoint(doc, sid + ' QA restore failed', sid, publish=args.publish,
                               status='failed', request_hash=wanted, error=message)
                    failures.append(sid)
            continue
        old = doc.get('shots', {}).get(sid, {})
        if old and old.get('request_hash') != wanted:
            doc.setdefault('previous_results', {}).setdefault(sid, []).append(old)
            doc['shots'][sid] = {'id': sid}
        probe_task = PROBE_TASKS.pop(sid, None)
        if probe_task and full_payload(project, shot).get('image_url'):
            print('%s: reusing ref-image probe submission %s' % (sid, probe_task), flush=True)
            queued[sid] = {'task_id': str(probe_task), 'request_hash': wanted,
                           'attempts': 0, 'shot': shot}
            checkpoint(doc, sid + ' queued', sid, publish=args.publish,
                       status='queued', task_id=str(probe_task), request_hash=wanted)
            continue
        in_flight = unharvested_task(doc, sid, wanted)
        if in_flight:
            # 上一轮交出去但没收回来的任务还在服务端跑：接着等它，别浪费额度重投。
            print('%s: resuming the task submitted by an earlier run' % sid, flush=True)
            queued[sid] = {'task_id': in_flight, 'request_hash': wanted,
                           'attempts': 0, 'shot': shot}
            checkpoint(doc, sid + ' queued', sid, publish=args.publish,
                       status='queued', task_id=in_flight, request_hash=wanted)
            continue
        needs_generation.append(shot)

    def harvest_sweep(harvest_deadline):
        """查一轮所有在跑的任务：谁 SUCCESS 就立刻下载校验，别等全部提交完再收。"""
        progressed = False
        for sid, entry in list(queued.items()):
            if time.monotonic() >= harvest_deadline:
                break
            task_id, wanted, shot = entry['task_id'], entry['request_hash'], entry['shot']
            entry['attempts'] += 1
            try:
                polled = client.videos.retrieve_videos_result(id=task_id)
                status = str(obj_get(polled, 'task_status', '')).upper()
            except Exception as exc:
                last_error = redact(exc)[:600]
                if moderation_block(exc):
                    checkpoint(doc, sid + ' blocked (content moderation (1301))', sid,
                               publish=args.publish, status='failed', request_hash=wanted,
                               task_id=task_id, error=last_error)
                    failures.append(sid)
                    queued.pop(sid, None)
                elif not retryable(exc) and entry['attempts'] > 3:
                    checkpoint(doc, sid + ' failed (polling error)', sid, publish=args.publish,
                               status='failed', request_hash=wanted, task_id=task_id,
                               error=last_error)
                    failures.append(sid)
                    queued.pop(sid, None)
                continue
            print('%s task %s poll %d: %s' % (sid, task_id, entry['attempts'], status), flush=True)
            if status not in ('SUCCESS', 'FAIL'):
                continue
            progressed = True
            queued.pop(sid, None)
            if status == 'FAIL':
                last_error = redact(obj_get(polled, 'error', '') or polled)[:600]
                if transient_fail(last_error) and entry.get('resubmissions', 0) < 2 \
                        and time.monotonic() < submit_deadline:
                    entry['resubmissions'] = entry.get('resubmissions', 0) + 1
                    needs_generation.append(shot)
                    print('%s: transient provider failure; resubmit a new task' % sid, flush=True)
                    continue
                blocker = 'content moderation (1301)' if moderation_block(last_error) \
                    else 'non-transient provider failure'
                checkpoint(doc, sid + ' failed (' + blocker + ')', sid, publish=args.publish,
                           status='failed', request_hash=wanted, task_id=task_id, error=last_error)
                failures.append(sid)
                continue
            video_result = obj_get(polled, 'video_result') or []
            first = video_result[0] if video_result else None
            url = obj_get(first, 'url') if first else None
            if not url:
                checkpoint(doc, sid + ' failed (SUCCESS without a video URL)', sid,
                           publish=args.publish, status='failed', request_hash=wanted,
                           task_id=task_id, error='provider returned SUCCESS without media')
                failures.append(sid)
                continue
            dest = sources / ('%s.mp4' % sid)
            try:
                download(url, dest)
                checksum = digest(dest)
                info = inspect_clip(dest, qa, sid)
            except Exception as exc:
                checkpoint(doc, sid + ' failed inspection', sid, publish=args.publish,
                           status='failed', request_hash=wanted, task_id=task_id,
                           video_url=url, error=redact(exc)[:600])
                failures.append(sid)
                continue
            checkpoint(doc, sid + ' media and QA ready', sid, files=[qa / ('%s.json' % sid)],
                       publish=args.publish, status='completed', request_hash=wanted,
                       task_id=task_id, video_url=url, sha256=checksum,
                       bytes=dest.stat().st_size, media=info, error=None)
        return progressed

    # 提交阶段：免费档的 1305「该模型当前访问量过大」是全模型级限流，和具体镜头无关。
    # 所以轮流扫一遍所有待生成镜头，谁赶上放行窗口谁先进队列；任务在服务端并行出片，
    # 本地不再「交一条等一条」，免得等待时间全花在轮询上。
    submit_deadline = min(deadline, time.monotonic() + SUBMIT_PHASE_SECONDS)
    sweep = 0
    while needs_generation and time.monotonic() < submit_deadline:
        sweep += 1
        accepted, throttled = [], 0
        for shot in list(needs_generation):
            if time.monotonic() >= submit_deadline:
                break
            sid = shot['id']
            wanted = request_hash(project, shot)
            payload = full_payload(project, shot)
            if sweep == 1:
                checkpoint(doc, sid + ' submitting', sid, publish=args.publish,
                           status='submitting', request_hash=wanted)
            try:
                response = client.videos.generations(**payload)
                task_id = obj_get(response, 'id')
                if not task_id:
                    raise RuntimeError('No task id: %r' % (response,))
            except Exception as exc:
                last_error = redact(exc)[:600]
                if moderation_block(exc):
                    print('%s: content moderation (1301); record and continue after prompt review'
                          % sid, flush=True)
                    checkpoint(doc, sid + ' blocked (content moderation (1301))', sid,
                               publish=args.publish, status='failed', request_hash=wanted,
                               error=last_error)
                    failures.append(sid)
                    needs_generation.remove(shot)
                elif retryable(exc):
                    throttled += 1
                else:
                    print('%s: non-transient provider rejection; preserve the failure receipt'
                          % sid, flush=True)
                    checkpoint(doc, sid + ' failed (non-transient provider rejection)', sid,
                               publish=args.publish, status='failed', request_hash=wanted,
                               error=last_error)
                    failures.append(sid)
                    needs_generation.remove(shot)
                continue
            accepted.append(sid)
            queued[sid] = {'task_id': str(task_id), 'request_hash': wanted,
                           'attempts': 0, 'shot': shot}
            needs_generation.remove(shot)
            checkpoint(doc, sid + ' queued', sid, publish=args.publish,
                       status='queued', task_id=str(task_id), request_hash=wanted)
        print('SUBMIT_SWEEP %d accepted=%d throttled=%d still_waiting=%d queued=%d'
              % (sweep, len(accepted), throttled, len(needs_generation), len(queued)), flush=True)
        # 边提交边收获：已出片的任务立刻落地，不必等所有镜头都挤过限流窗口。
        harvested = harvest_sweep(deadline)
        if needs_generation:
            wait = 0 if harvested else retry_delay(sweep)
            if time.monotonic() + wait >= submit_deadline:
                break
            time.sleep(wait)
    for shot in needs_generation:
        sid = shot['id']
        checkpoint(doc, sid + ' failed (provider throttled every submission attempt)', sid,
                   publish=args.publish, status='failed', request_hash=request_hash(project, shot),
                   error='Provider kept rejecting submissions (1305 throttling) for this run')
        failures.append(sid)

    # 收获阶段：任务已经在服务端排队出片，轮流查询，谁先 SUCCESS 谁先下载校验。
    while queued and time.monotonic() < deadline:
        progressed = harvest_sweep(deadline)
        if needs_generation and time.monotonic() < submit_deadline:
            # 重投瞬时失败的任务，仍然走同一个限流友好的扫描逻辑。
            for shot in list(needs_generation):
                sid = shot['id']
                wanted = request_hash(project, shot)
                try:
                    response = client.videos.generations(**full_payload(project, shot))
                    task_id = obj_get(response, 'id')
                except Exception as exc:
                    if not retryable(exc):
                        checkpoint(doc, sid + ' failed (resubmission rejected)', sid,
                                   publish=args.publish, status='failed', request_hash=wanted,
                                   error=redact(exc)[:600])
                        failures.append(sid)
                        needs_generation.remove(shot)
                    continue
                if task_id:
                    queued[sid] = {'task_id': str(task_id), 'request_hash': wanted,
                                   'attempts': 0, 'shot': shot}
                    needs_generation.remove(shot)
                    checkpoint(doc, sid + ' queued', sid, publish=args.publish,
                               status='queued', task_id=str(task_id), request_hash=wanted)
        if queued and not progressed:
            time.sleep(HARVEST_SWEEP_SECONDS)
    for sid, entry in queued.items():
        checkpoint(doc, sid + ' failed (task never finished before the deadline)', sid,
                   publish=args.publish, status='failed', request_hash=entry['request_hash'],
                   task_id=entry['task_id'], error='polling deadline reached')
        failures.append(sid)
    complete = [sid for sid, row in doc.get('shots', {}).items() if row.get('status') == 'completed']
    missing = sorted(set(doc['required_generated_shots']) - set(complete))
    doc['phase'] = 'selected_sources_ready' if only and not failures else \
        'sources_ready' if not missing else 'generation_incomplete'
    checkpoint(doc, 'CogVideoX generation pass finished (missing=%d failed=%d)'
               % (len(missing), len(failures)), publish=args.publish)
    print('COMPLETE %d requested clips; model=%s' % (len(shots), MODEL), flush=True)
    return 1 if recover_only and failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
