"""自动续投决策：排队没排到时，要不要自动再投一轮，直到全部生成。

设计（2026-10-10 与用户确认）：
- 已生成的镜头按 SHA-256 断点复用，剩下的镜头反复循环请求，直到全部生成；
- 平台限制单个 job 最长约 6 小时，所以「循环」是一串自动接力的 workflow run；
- 保护闸：连续 ``STALE_STOP`` 轮一个镜头都没多 → 大概率供应商停摆/额度出问题，
  停下来等人看，避免空烧 runner（硬上限 ``CAP_ROUNDS`` 轮双保险）。

判定「这一轮是不是排队满收工」有两路证据（2026-10-11 加固）：
- results.json 的 phase == provider_capacity；
- generate.py 的退出码 42（容量满）。退出码写在 runner 本地文件里，
  git push 全失败也误不了事；43（额度耗尽）/1（真 bug）则不接力。

本模块只读写 GEN_REQUEST / results.json 两个文件，不碰网络，便于单测。
工作流收尾步骤调用它；返回 resume 时由 bash 负责 commit+push+自派发。
"""
import json
import os
import pathlib
import sys

CAP_ROUNDS = 40      # 绝对硬上限：真出怪事时不至于烧几十个小时 runner
STALE_STOP = 3       # 连续这么多轮零进展就停（每轮空等约 140 分钟，3 轮≈7 小时无产出）


def decide(req_path, res_path, rc=None, cap_rounds=CAP_ROUNDS, stale_stop=STALE_STOP):
    """返回 (verdict, msg)：verdict ∈ {resume, skip, stop}。

    ``rc`` 是 generate.py 的退出码（42 容量满 / 43 额度耗尽 / 1 真 bug / None 未知）。
    resume 时会就地更新 GEN_REQUEST：round+1，并记录本轮起跑时的已完成数与连零轮数。
    """
    req = pathlib.Path(req_path)
    res = pathlib.Path(res_path)
    if not req.is_file() or not res.is_file():
        return 'skip', '缺 GEN_REQUEST 或 results.json'
    if rc == 43:
        return 'skip', '退出码 43：额度耗尽，接力也没用，等人处理'
    if rc == 1:
        return 'skip', '退出码 1：流水线真故障，等人修，不接力'
    doc = json.loads(res.read_text(encoding='utf-8'))
    capacity = doc.get('phase') == 'provider_capacity' or rc == 42
    if not capacity:
        return 'skip', 'phase=%s rc=%s（不是排队满，不续投）' % (doc.get('phase'), rc)
    payload = json.loads(req.read_text(encoding='utf-8'))

    rounds = int(payload.get('round', 1))
    if rounds >= cap_rounds:
        return 'stop', '已到硬上限 %d 轮，人工看一眼再继续' % cap_rounds

    done = sum(1 for v in doc.get('shots', {}).values() if v.get('status') == 'completed')
    started_with = int(payload.get('round_started_completed', 0))
    stale = int(payload.get('stale_rounds', 0))
    if done > started_with:
        stale = 0                      # 这轮有产出，连零计数清零
    else:
        stale += 1                     # 这轮一个都没多
    if stale >= stale_stop:
        return 'stop', '连续 %d 轮零进展（约 %d 小时无产出），疑似供应商停摆，等人来看' % (
            stale, stale * 140 // 60)

    payload['round'] = rounds + 1
    payload['round_started_completed'] = done
    payload['stale_rounds'] = stale
    req.write_text(json.dumps(payload, ensure_ascii=False) + '\n', encoding='utf-8')
    return 'resume', 'round=%d 已完成=%d 连零=%d' % (rounds + 1, done, stale)


def main(argv):
    rc = None
    if '--rc' in argv:
        raw = argv[argv.index('--rc') + 1] if argv.index('--rc') + 1 < len(argv) else ''
        try:
            rc = int(raw)
        except ValueError:
            rc = None
    verdict, msg = decide('production/chessboard64/GEN_REQUEST',
                          'production/chessboard64/results.json', rc=rc)
    print('AUTO_RESUME %s: %s' % (verdict, msg))
    if verdict == 'resume':
        marker = pathlib.Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'auto_resume'
        marker.write_text('1')
    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])
