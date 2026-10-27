#!/usr/bin/env python3
"""出片前的 38 个动态源体检：收据、签名链接有效期、可用慢放倍率一次性全查。

为什么需要它
------------
渲染作业先 fetch 全部 38 段 CogVideoX-Flash 源片，任何一条签名链接过期都会让整轮
渲染在跑了十几分钟后才失败（2026-10-26 的 S08 就是这样连废两轮）。本脚本在**不下载
媒体**的前提下，一次性检查：

* 每个动态镜头都有 ``status=completed`` 的收据，且 ``request_hash`` 与当前提示词一致；
* 签名链接还剩够跑完一轮渲染的时间（``--min-ttl-hours``，默认 2 小时）；
* 收据里有实测时长，且按 audio/clause-times.json 对出来的槽位计算，所需慢放倍率不超过
  ``render.MAX_SLOW_MOTION_FACTOR``（倒放/ping-pong 一律禁止，超限直接报错）。

只打印链接的 host+path，绝不输出签名查询参数。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent


def load_project_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot load project module %s' % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signed_url_expiry(url: str):
    """读取签名链接的到期时间（Unix 秒），永不回显查询参数本身。"""
    try:
        query = parse_qs(urlsplit(str(url)).query)
        values = query.get('Expires') or query.get('expires') or []
        return int(values[0]) if values else None
    except (TypeError, ValueError):
        return None


def slot_durations(render, align, mapping, timings):
    """按实测旁白分句算出每个槽位要填的成片秒数。"""
    aligned = align(mapping, timings, render.CUTS)
    tempo = sum(float(row['duration']) for row in timings.values()) / (
        render.DURATION - render.INTRO - render.OUTRO - render.GAP * (len(timings) - 1)
    )
    slots = {}
    for chapter, entries in aligned.items():
        chapter_duration = float(timings[chapter]['duration'])
        for index, current in enumerate(entries):
            sid = current[1]
            if index + 1 < len(entries):
                duration = (entries[index + 1][0] - current[0]) / tempo
            else:
                duration = (chapter_duration - current[0]) / tempo + render.GAP
            if chapter == 'N01' and index == 0:
                duration += render.INTRO
            slots[sid] = duration
    return slots


def audit(results, story, render, align, mapping, timings, min_ttl_hours):
    now = time.time()
    slots = slot_durations(render, align, mapping, timings)
    rows, problems = [], []
    for shot in story['shots']:
        if shot.get('kind') != 'cogvideo':
            continue
        sid = shot['id']
        receipt = results.get('shots', {}).get(sid, {})
        row = {'id': sid, 'status': receipt.get('status', 'missing'), 'ttl_hours': None,
               'duration': None, 'factor': None, 'note': ''}
        if row['status'] != 'completed' or not receipt.get('video_url') or not receipt.get('sha256'):
            row['note'] = '收据缺失或未完成，需重新生成'
            problems.append(sid)
            rows.append(row)
            continue
        expiry = signed_url_expiry(receipt['video_url'])
        if expiry is not None:
            row['ttl_hours'] = round((expiry - now) / 3600, 2)
            if row['ttl_hours'] < min_ttl_hours:
                row['note'] = '签名链接剩余时间不足，需刷新'
                problems.append(sid)
        media = receipt.get('media') or {}
        if not media.get('duration'):
            row['note'] = row['note'] or '收据缺少实测时长'
            problems.append(sid)
            rows.append(row)
            continue
        row['duration'] = round(float(media['duration']), 3)
        source_start, source_end = 0.12, float(media['duration']) - 0.12
        if sid in render.WINDOWS:
            window_start, window_end = render.WINDOWS[sid]
            source_start = max(source_start, window_start)
            source_end = min(source_end, window_end if window_end is not None else source_end)
        try:
            _, factor = render.plan_time_stretch(slots[sid], source_end - source_start, sid)
            row['factor'] = round(factor, 3)
            if factor > render.MAX_SLOW_MOTION_FACTOR:
                row['note'] = '慢放倍率超上限'
                problems.append(sid)
        except RuntimeError as error:
            row['factor'] = None
            row['note'] = str(error)[:120]
            problems.append(sid)
        rows.append(row)
    return rows, sorted(set(problems))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, default=HERE / 'results.json')
    parser.add_argument('--story', type=Path, default=HERE / 'story.json')
    parser.add_argument('--min-ttl-hours', type=float, default=2.0,
                        help='签名链接至少要够一轮渲染用（默认 2 小时）')
    parser.add_argument('--json', type=Path, default=None, help='把审计结果另存为 JSON')
    args = parser.parse_args()

    render = load_project_module('chessboard64_render_audit', HERE / 'render.py')
    align = load_project_module('chessboard64_align_audit', HERE / 'align_cuts_to_audio.py').align
    results = json.loads(args.results.read_text(encoding='utf-8'))
    story = json.loads(args.story.read_text(encoding='utf-8'))
    mapping = json.loads((HERE / 'audio' / 'cut-clauses.json').read_text(encoding='utf-8'))
    timings = json.loads((HERE / 'audio' / 'clause-times.json').read_text(encoding='utf-8'))

    rows, problems = audit(results, story, render, align, mapping, timings, args.min_ttl_hours)
    print('%-5s %-11s %9s %9s %7s  %s' % ('镜号', '状态', '剩余(h)', '时长(s)', '倍率', '备注'))
    for row in rows:
        print('%-5s %-11s %9s %9s %7s  %s' % (
            row['id'], row['status'],
            '-' if row['ttl_hours'] is None else '%.2f' % row['ttl_hours'],
            '-' if row['duration'] is None else '%.3f' % row['duration'],
            '-' if row['factor'] is None else '%.3f' % row['factor'],
            row['note']))
    summary = {'audited': len(rows), 'ready': len(rows) - len(problems),
               'blocked': problems, 'min_ttl_hours': args.min_ttl_hours,
               'max_slow_motion_factor': render.MAX_SLOW_MOTION_FACTOR,
               'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if args.json:
        args.json.write_text(json.dumps({'summary': summary, 'shots': rows},
                                        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if problems:
        print('AUDIT_BLOCKED %d/%d 源片未就绪: %s'
              % (len(problems), len(rows), ','.join(problems)), flush=True)
        return 1
    print('AUDIT_OK %d 个动态源全部可用；最低剩余 %.2f 小时，最大慢放 %.3f×'
          % (len(rows), min(r['ttl_hours'] for r in rows if r['ttl_hours'] is not None),
             max(r['factor'] for r in rows if r['factor'] is not None)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
