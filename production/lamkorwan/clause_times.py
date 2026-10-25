#!/usr/bin/env python3
"""按 TTS 停顿把解说词的每个分句对到时间上（离线，不用 ASR）。

收紧后的配音（tighten_pauses.py）在每个标点处都留 0.35 秒静音，所以
"分句边界 = 某个静音段的起点"几乎总成立；TTS 偶尔会在长数字串里多停一下，
因此静音段数 ≥ 分句数。这里用动态规划从静音段里挑出一条单调路径，使每个分句
的实际时长与"按字数摊开的期望时长"最接近（对数比的平方和最小）。

输出 audio/clause-times.json（随仓库提交），render.py 的 CUTS 切点、抖音脚本.md 的分镜表、
成片字幕（ASR 覆盖不足时）都从这里取。

    python3 production/lamkorwan/clause_times.py               # 对时间，写 audio/clause-times.json
    python3 production/lamkorwan/clause_times.py --check-cuts  # 核对 render.py 的 CUTS 是否都落在分句停顿窗内
"""
import json, math, re, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
RATE = 48000; HOP = 480
PUNCT = r'[，。！？；：、—]+'


def decode(p):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(p), '-ac', '1', '-ar', str(RATE), '-f', 's16le', '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(out, '<i2').astype(np.float32) / 32768


def pauses(x, min_len=0.18):
    n = len(x) // HOP * HOP
    rms = np.sqrt((x[:n].reshape(-1, HOP) ** 2).mean(1)); quiet = rms < 0.01
    spans = []; s = None; lead = 0.0
    for i, q in enumerate(quiet):
        if not q: lead = i * 0.01; break
    for i, q in enumerate(quiet):
        if q and s is None: s = i
        if not q and s is not None:
            if (i - s) * 0.01 >= min_len and s > 0: spans.append((s * 0.01, (i - s) * 0.01))
            s = None
    return lead, spans


def align(text, x):
    dur = len(x) / RATE
    lead, spans = pauses(x)
    clauses = [c for c in re.split(PUNCT, text) if c]
    w = np.array([max(1, len(re.sub(r'[^\u3400-\u9fffA-Za-z0-9]', '', c))) for c in clauses], float)
    speech = dur - lead - 0.25 - sum(d for _, d in spans)
    rate = speech / w.sum()                      # 秒/字
    K = len(clauses); J = len(spans)
    starts = [lead] + [s + d for s, d in spans]  # 候选"分句开始时间"：片头 或 某个静音段结束
    ends = [s for s, _ in spans] + [dur]         # 候选"分句结束时间"：某个静音段开始 或 片尾
    INF = float('inf')
    # dp[k][j]: 第 k 个分句结束在第 j 个候选结束点（j∈[0,J]），j=J 只允许 k=K-1
    dp = [[INF] * (J + 1) for _ in range(K)]; back = [[-1] * (J + 1) for _ in range(K)]

    def cost(k, a, b):
        actual = b - a
        expected = w[k] * rate
        if actual <= 0.05: return INF
        return math.log(actual / expected) ** 2

    for j in range(J + 1):
        if j == J and K > 1: continue
        dp[0][j] = cost(0, starts[0], ends[j])
    for k in range(1, K):
        for j in range(k, J + 1):
            if j == J and k != K - 1: continue
            best = INF; bi = -1
            for i in range(k - 1, j):
                if dp[k - 1][i] == INF: continue
                c = dp[k - 1][i] + cost(k, starts[i + 1], ends[j])
                if c < best: best = c; bi = i
            dp[k][j] = best; back[k][j] = bi
    j = J; path = [None] * K
    for k in range(K - 1, -1, -1):
        path[k] = j; j = back[k][j]
    rows = []
    for k in range(K):
        a = starts[0] if k == 0 else starts[path[k - 1] + 1]
        b = ends[path[k]]
        rows.append({'i': k, 'start': round(a, 2), 'end': round(b, 2), 'text': clauses[k],
                     'chars_per_second': round(w[k] / (b - a), 2)})
    return dur, rows


def check_cuts(window=0.35, lead_max=0.0):
    """核对 render.py 的 CUTS：除每章第一个切点外，每个切点都必须落在某个分句起点前的停顿窗里
    [clause_start - window, clause_start + lead_max]。返回违规列表（空 = 全部通过）。"""
    sys.path.insert(0, str(HERE))
    import render  # noqa: E402  (同目录；只取 CUTS)
    table = json.loads((HERE / 'audio' / 'clause-times.json').read_text())
    problems = []
    for cid, cuts in render.CUTS.items():
        clauses = table[cid]['clauses']
        for j, (cut, sid, _variant) in enumerate(cuts):
            if j == 0:
                if cut != 0:
                    problems.append(f'{cid} {sid}: 每章第一个切点必须是 0（现在是 {cut}）')
                continue
            nearest = min(clauses, key=lambda c: abs(c['start'] - cut))
            delta = cut - nearest['start']
            ok = -window <= delta <= lead_max
            print(f"{'OK ' if ok else 'BAD'} {cid} {sid:>4} cut={cut:6.2f}  分句「{nearest['text'][:12]}」起点 {nearest['start']:6.2f}  差 {delta:+.2f}")
            if not ok:
                problems.append(f'{cid} {sid}: 切点 {cut} 不在分句「{nearest["text"]}」起点 {nearest["start"]} 前的 '
                                f'[{nearest["start"] - window:.2f}, {nearest["start"] + lead_max:.2f}] 窗内')
    return problems


def main(slug='lamkorwan'):
    story = json.loads((HERE / 'story.json').read_text())
    root = HERE.parents[1]
    result = {}
    for ch in story['chapters']:
        dur, rows = align(ch['text'], decode(HERE / 'audio' / (ch['id'] + '.mp3')))
        result[ch['id']] = {'duration': round(dur, 3), 'clauses': rows}
        print(ch['id'], f'dur {dur:.2f}')
        for r in rows:
            print(f"   {r['i']:2d} {r['start']:6.2f}-{r['end']:6.2f}  {r['chars_per_second']:4.1f}/s  {r['text']}")
    out = HERE / 'audio' / 'clause-times.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print('written', out)


if __name__ == '__main__':
    if '--check-cuts' in sys.argv:
        bad = check_cuts()
        if bad:
            print('\n'.join(bad), file=sys.stderr)
            sys.exit(f'{len(bad)} 个切点不在停顿窗内，先改 render.py 的 CUTS 再出片')
        print('CUTS 全部落在分句停顿窗内')
    else:
        main()
