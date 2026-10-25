#!/usr/bin/env python3
"""制作进度台：一屏看完这部片子走到哪一步了，页面每 10 秒自动刷新。

用法::

    python3 production/rabies1885/progress_app.py --port 8040

看三样东西：

* **流水线**——史实核对 → 解说 → 分镜 → 生成 → 自动检验 → 出片 → 听检，
  每一步的状态和时间都从仓库里的文件与 git 提交读出来，不是手填的；
* **GitHub Actions 实时状态**——正在跑的 workflow 连它的 job/step 一起显示，
  跑完的显示结论和耗时；
* **38 个镜头的检验结果**——接触表缩略图 + 判定 + 亮度/运动数字。

成片用支持 Range 请求的方式直接喂给浏览器的 <video>，可以在页面里播。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
FILM = REPO_ROOT / "交付" / "狂犬病疫苗_一百四十年前那场赌局_三分钟_带声音.mp4"
QA = HERE / "qa"
DELIVERY = HERE / "delivery"
PROJECT = "production/rabies1885"

CACHE_SECONDS = 12
_runs_cache: dict = {"at": 0.0, "data": None}
_repo_cache: dict = {"at": 0.0, "slug": ""}

STAGES = [
    ("史实核对", ["史实核对.md", "事实底稿-资料.md"]),
    ("解说词", ["解说词体检.md", "story.json"]),
    ("45 镜分镜", ["screenplay.md", "story.json"]),
    ("38 镜生成", ["results.json"]),
    ("自动检验", ["qc.json", "qc-report.md"]),
    ("出片", ["delivery/technical-report.json"]),
    ("逐字听检", ["delivery/verbatim-check.json"]),
]


def sh(args, timeout=25):
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                             cwd=str(REPO_ROOT))
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def repo_slug() -> str:
    if time.time() - _repo_cache["at"] < 3600 and _repo_cache["slug"]:
        return _repo_cache["slug"]
    slug = sh(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not slug:
        slug = "32r4e2q-hub/desktop-tutorial"
    _repo_cache.update(at=time.time(), slug=slug)
    return slug


def git_time(path: str) -> str:
    """文件最后一次被提交的时间。"""
    return sh(["git", "log", "-1", "--format=%ad", "--date=format:%m-%d %H:%M", "--",
               f"{PROJECT}/{path}"], timeout=15)


def runs_snapshot() -> dict:
    """GitHub Actions 的最近运行 + 正在跑的 job/step。"""
    if time.time() - _runs_cache["at"] < CACHE_SECONDS and _runs_cache["data"]:
        return _runs_cache["data"]
    slug = repo_slug()
    raw = sh(["gh", "api", f"repos/{slug}/actions/runs?per_page=8",
              "--jq", "[.workflow_runs[] | {id, name, status, conclusion, display_title,"
                      " created_at, updated_at, run_started_at, html_url}]"], timeout=30)
    try:
        runs = json.loads(raw) if raw else []
    except Exception:
        runs = []
    for r in runs:
        r["minutes"] = ""
        if r.get("run_started_at") and r.get("updated_at"):
            try:
                a = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                r["minutes"] = f"{(b - a).total_seconds() / 60:.1f} 分钟"
            except Exception:
                pass
        r["jobs"] = []
        if r.get("status") in ("in_progress", "queued", "pending"):
            jraw = sh(["gh", "api", f"repos/{slug}/actions/runs/{r['id']}/jobs",
                       "--jq", "[.jobs[] | {name, status, conclusion, started_at,"
                               " completed_at, steps: [.steps[] | {name, status,"
                               " conclusion, number, completed_at}]}]"], timeout=30)
            try:
                jobs = json.loads(jraw) if jraw else []
            except Exception:
                jobs = []
            for j in jobs:
                done = [s for s in j.get("steps", []) if s.get("conclusion") == "success"]
                j["done_steps"] = len(done)
                j["steps"] = j.get("steps", [])[-14:]
            r["jobs"] = jobs
    data = {"fetched": datetime.now().strftime("%H:%M:%S"), "runs": runs}
    _runs_cache.update(at=time.time(), data=data)
    return data


def generation_status() -> dict:
    """38 镜里有多少镜是用当前提示词生成的（比 request_hash，不看 status）。"""
    try:
        story = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
        results = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    except Exception:
        return {"done": 0, "total": 38, "stale": []}
    import sys
    sys.path.insert(0, str(HERE))
    try:
        import generate
        want = {s["id"]: generate.request_hash(story, s)
                for s in story["shots"] if s.get("kind") == "agnes"}
    except Exception:
        return {"done": 0, "total": 38, "stale": []}
    got = {k: (v or {}).get("request_hash") for k, v in results.get("shots", {}).items()}
    stale = sorted(i for i, h in want.items() if got.get(i) != h)
    return {"done": len(want) - len(stale), "total": len(want), "stale": stale}


def stages() -> list:
    out = []
    for name, files in STAGES:
        stamps = [t for f in files if (t := git_time(f))]
        present = any((HERE / f).exists() for f in files)
        out.append({"name": name, "done": bool(present and stamps),
                    "at": max(stamps) if stamps else "", "files": files})
    return out


def snapshot() -> dict:
    qc = {}
    if (HERE / "qc.json").exists():
        qc = json.loads((HERE / "qc.json").read_text(encoding="utf-8"))
    verdicts = [v.get("verdict") for v in qc.values()]
    tech = verb = {}
    if (DELIVERY / "technical-report.json").exists():
        tech = json.loads((DELIVERY / "technical-report.json").read_text(encoding="utf-8"))
    if (DELIVERY / "verbatim-check.json").exists():
        verb = json.loads((DELIVERY / "verbatim-check.json").read_text(encoding="utf-8"))
    shots = []
    story = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
    purpose = {s["id"]: s.get("purpose", "") for s in story["shots"]}
    for sid, v in sorted(qc.items()):
        shots.append({
            "id": sid,
            "verdict": v.get("verdict"),
            "brightness": round(v.get("brightness", 0), 1),
            "motion": round(v.get("motion_median", 0), 1),
            "note": (v.get("flags") or [""])[0] if isinstance(v.get("flags"), list) else "",
            "purpose": purpose.get(sid, ""),
        })
    commits = [c for c in sh(["git", "log", "-8", "--format=%h|%ad|%s",
                              "--date=format:%m-%d %H:%M"], timeout=15).split("\n") if c]
    commits = [dict(zip(("hash", "at", "msg"), c.split("|", 2))) for c in commits
               if c.count("|") >= 2]
    return {
        "generated_at": datetime.now().strftime("%H:%M:%S"),
        "stages": stages(),
        "generation": generation_status(),
        "qc_counts": {k: verdicts.count(k) for k in ("PASS", "WARN", "FAIL")},
        "shots": shots,
        "film": {
            "size_mb": round(FILM.stat().st_size / 1e6, 1) if FILM.exists() else 0,
            "mtime": datetime.fromtimestamp(FILM.stat().st_mtime).strftime("%m-%d %H:%M")
            if FILM.exists() else "",
            "duration": tech.get("duration"), "clips": tech.get("source_clips"),
            "no_reuse": tech.get("unique_shots_no_reuse"),
        },
        "verbatim": [{"id": c["id"], "cer": round(c["character_error_rate"], 3),
                      "verdict": c["verdict"]} for c in verb.get("film_pass", {}).get("chapters", [])],
        "commits": commits,
        **runs_snapshot(),
    }


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>制作进度 · 狂犬病疫苗</title>
<style>
:root{--bg:#12110f;--card:#1c1a16;--line:#2e2a22;--ink:#e8e2d4;--dim:#9a927e;--red:#c8543f;--ok:#6f8f5f;--warn:#c9a227;--blue:#5b8fa8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:9;background:#12110fe6;backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:14px 20px;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
h1{margin:0;font-size:17px;font-weight:600}
.live{color:var(--dim);font-size:13px}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:6px;animation:p 2s infinite}
@keyframes p{50%{opacity:.25}}
main{padding:18px 20px 60px;max-width:1400px;margin:0 auto}
section{margin-bottom:26px}
h2{font-size:14px;font-weight:600;color:var(--dim);letter-spacing:.06em;margin:0 0 12px;text-transform:uppercase}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.card.done{border-color:#3f5233}
.card .t{font-weight:600;font-size:14px}
.card .s{font-size:12px;color:var(--dim);margin-top:3px}
.badge{float:right;font-size:11px;padding:1px 7px;border-radius:20px;border:1px solid var(--line);color:var(--dim)}
.badge.ok{color:var(--ok);border-color:#3f5233}
.run{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:8px}
.run .top{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.run .nm{font-weight:600;font-size:14px}
.run .meta{color:var(--dim);font-size:12px;margin-left:auto}
.st{font-size:11px;padding:1px 8px;border-radius:20px;border:1px solid var(--line)}
.st.success{color:var(--ok);border-color:#3f5233}
.st.failure{color:var(--red);border-color:#5a332a}
.st.in_progress{color:var(--blue);border-color:#2f4a56}
.st.queued,.st.pending{color:var(--warn);border-color:#4d422a}
ol.steps{margin:8px 0 0;padding-left:18px;font-size:13px;color:var(--dim)}
ol.steps li.done{color:var(--ok)}
ol.steps li.running{color:var(--blue)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
.shot{background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
.shot img{width:100%;display:block;background:#000}
.shot .b{padding:8px 10px;font-size:12px}
.shot .id{font-weight:600;font-size:13px}
.shot .p{color:var(--dim);margin-top:2px;line-height:1.45;height:2.9em;overflow:hidden}
.PASS{border-color:#3f5233}.FAIL{border-color:#5a332a}.WARN{border-color:#4d422a}
.v{font-size:11px;padding:0 6px;border-radius:20px;border:1px solid var(--line)}
.v.PASS{color:var(--ok)}.v.FAIL{color:var(--red)}.v.WARN{color:var(--warn)}
video{width:100%;max-width:900px;border-radius:8px;background:#000;border:1px solid var(--line)}
a{color:var(--blue)}
.kv{color:var(--dim);font-size:13px}
</style></head><body>
<header><h1>制作进度 · 狂犬病疫苗：一百四十年前那场赌局</h1>
<span class="live"><span class="dot"></span>实时刷新 · 最后更新 <b id="at">—</b></span></header>
<main>
<section><h2>流水线</h2><div class="cards" id="stages"></div></section>
<section><h2>GitHub Actions <span class="kv" id="fetched"></span></h2><div id="runs"></div></section>
<section><h2>成片</h2><div id="film"></div></section>
<section><h2>38 镜检验 <span class="kv" id="qccounts"></span></h2><div class="grid" id="shots"></div></section>
<section><h2>最近提交</h2><table id="commits"></table></section>
</main>
<script>
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function tick(){
  const d=await (await fetch('/api')).json();
  document.getElementById('at').textContent=d.generated_at;
  document.getElementById('fetched').textContent='（拉取于 '+d.fetched+'）';
  document.getElementById('stages').innerHTML=d.stages.map(s=>
    `<div class="card ${s.done?'done':''}"><span class="badge ${s.done?'ok':''}">${s.done?'已完成':'待办'}</span>
     <div class="t">${esc(s.name)}</div><div class="s">${s.at?('提交于 '+s.at):'尚无产物'}</div></div>`).join('');
  document.getElementById('runs').innerHTML=d.runs.length?d.runs.map(r=>{
     const steps=r.jobs&&r.jobs.length?('<ol class="steps">'+r.jobs.flatMap(j=>j.steps.map(s=>
       `<li class="${s.conclusion==='success'?'done':(s.status==='in_progress'?'running':'')}">${esc(s.name)} — ${s.conclusion||s.status}</li>`
     )).join('')+'</ol>'):'';
     return `<div class="run"><div class="top"><span class="nm">${esc(r.display_title||r.name)}</span>
       <span class="st ${r.conclusion||r.status}">${r.conclusion||r.status}</span>
       <span class="meta">${esc(r.name)} · ${esc(r.minutes||'')} · <a href="${esc(r.html_url)}" target="_blank">明细</a></span></div>${steps}</div>`;
   }).join(''):'<div class="kv">读不到 workflow 状态</div>';
  const f=d.film;
  document.getElementById('film').innerHTML=f.size_mb?
    `<video src="/film" controls preload="metadata"></video>
     <div class="kv" style="margin-top:8px">${f.size_mb} MB · ${f.duration} 秒 · ${f.clips} 个源片段（无复用：${f.no_reuse?'是':'否'}）· 生成于 ${f.mtime}
     · <a href="/film" download>下载</a>
     ${d.verbatim.length?' · 听检：'+d.verbatim.map(v=>`${v.id} ${v.cer}`).join(' / '):''}</div>`
    :'<div class="kv">还没有成片</div>';
  document.getElementById('qccounts').textContent=`PASS ${d.qc_counts.PASS||0} · WARN ${d.qc_counts.WARN||0} · FAIL ${d.qc_counts.FAIL||0} · 已按当前提示词生成 ${d.generation.done}/${d.generation.total}`;
  document.getElementById('shots').innerHTML=d.shots.map(s=>
    `<div class="shot ${s.verdict}"><img src="/qa/${s.id}.jpg" loading="lazy">
     <div class="b"><span class="id">${s.id}</span> <span class="v ${s.verdict}">${s.verdict}</span>
     <div class="kv">亮度 ${s.brightness} · 运动 ${s.motion}</div>
     <div class="p">${esc(s.purpose)}</div></div></div>`).join('');
  document.getElementById('commits').innerHTML='<tr><th>时间</th><th>提交</th></tr>'+
    d.commits.map(c=>`<tr><td style="white-space:nowrap;color:var(--dim)">${esc(c.at)}</td><td>${esc(c.msg)}</td></tr>`).join('');
}
tick(); setInterval(tick,10000);
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype: str, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api":
            try:
                self._send(json.dumps(snapshot()).encode(), "application/json; charset=utf-8")
            except Exception as exc:                      # 进度台挂了不该影响别的
                self._send(json.dumps({"error": str(exc)}).encode(),
                           "application/json; charset=utf-8", code=500)
        elif path.startswith("/qa/"):
            f = QA / path[4:]
            if f.exists() and f.suffix == ".jpg":
                self._send(f.read_bytes(), "image/jpeg")
            else:
                self._send(b"", "text/plain", code=404)
        elif path == "/film":
            self._film()
        else:
            self._send(b"", "text/plain", code=404)

    def _film(self):
        """带 Range 支持，浏览器才能拖动进度条。"""
        if not FILM.exists():
            self._send(b"", "text/plain", code=404)
            return
        size = FILM.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        code = 200
        extra = {"Accept-Ranges": "bytes"}
        if rng and rng.startswith("bytes="):
            try:
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else 0
                end = int(b) if b else size - 1
                end = min(end, size - 1)
                code = 206
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            except Exception:
                start, end, code = 0, size - 1, 200
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(length))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command == "HEAD":
            return
        with FILM.open("rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(1 << 20, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8040)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"进度台 http://0.0.0.0:{args.port}/  （成片 {FILM}）")
    srv.serve_forever()


if __name__ == "__main__":
    main()
