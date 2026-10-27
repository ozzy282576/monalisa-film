#!/usr/bin/env python3
"""镜头复审页：把 qa/ 接触表摆成一屏，勾选要重做的镜头。

用法::

    python3 production/rabies1885/review_app.py --port 8020

产出 ``REDO.json``：被标红的镜头 + 原因。代理读它去填 ``GEN_REQUEST`` 的
``{"only":[...]}``，重生成坏镜头。看片本身仍然要人来做——这个页面只是把
38 张接触表和它们的分镜描述摆到一起，省得一个一个开文件。
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
QA = HERE / "qa"
REDO = HERE / "REDO.json"
QC_REPORT = HERE / "qc.json"

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>镜头复审 · 狂犬病疫苗</title>
<style>
:root{--bg:#12110f;--card:#1c1a16;--line:#2e2a22;--ink:#e8e2d4;--dim:#9a927e;--red:#c8543f;--ok:#6f8f5f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:9;background:#12110fcc;backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);padding:14px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{margin:0;font-size:17px;font-weight:600;letter-spacing:.02em}
.count{color:var(--dim);font-size:13px}
button{background:#241f18;color:var(--ink);border:1px solid var(--line);border-radius:6px;
  padding:7px 14px;font-size:14px;cursor:pointer}
button:hover{border-color:#4a4234}
button.primary{background:#3d3324;border-color:#5c4f38}
button.danger{color:var(--red);border-color:#5a332a}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;padding:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.card.bad{border-color:var(--red)}
.card.bad .head{background:#2a1a16}
.head{padding:9px 12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;
  align-items:center;gap:8px;font-size:13px}
.sid{font-weight:600;letter-spacing:.04em}
.state{color:var(--dim);font-size:12px}
.state.done{color:var(--ok)}
img{width:100%;display:block;background:#000;cursor:zoom-in}
.body{padding:10px 12px;font-size:13px;color:#cfc7b4}
.body .purpose{color:var(--ink);margin-bottom:6px}
.body .meta{color:var(--dim);font-size:12px;line-height:1.5}
.badge{font-size:11px;padding:2px 7px;border-radius:4px;font-weight:600;letter-spacing:.05em}
.badge.ok{background:#24301f;color:#8fbf7a}.badge.warn{background:#332a17;color:#d8b45c}
.badge.fail{background:#3a1c17;color:#e08a72}
.qc{border-top:1px solid var(--line);margin-top:8px;padding-top:7px;font-size:12px}
.qc .nums{color:var(--dim)}
.qc .why{color:#d8b45c;margin-top:4px;line-height:1.45}
.foot{padding:9px 12px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center}
.foot input{flex:1;background:#12110f;border:1px solid var(--line);border-radius:5px;color:var(--ink);
  padding:6px 9px;font-size:13px}
.foot input:focus{outline:none;border-color:#5c4f38}
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#241f18;
  border:1px solid var(--line);border-radius:8px;padding:10px 18px;font-size:14px;opacity:0;
  transition:opacity .25s;pointer-events:none}
#toast.show{opacity:1}
</style></head><body>
<header>
  <h1>镜头复审 · 狂犬病疫苗：一百四十年前那场赌局</h1>
  <span class="count" id="count">加载中…</span>
  <button class="primary" id="save">保存标记</button>
  <button id="filter">只看有问题的</button>
  <button id="copy">复制 only 列表</button>
  <span class="count">看什么：露脸 / 手指畸变 / 画面里的假文字 / 中途换场 / 血腥 / 风格跑偏</span>
</header>
<div class="grid" id="grid"></div>
<div id="toast"></div>
<script>
let shots = [];
const saved = {};

let onlyBad = false;

function badge(s){
  const v = (s.qc && s.qc.verdict) || '';
  if (!v) return '';
  const cls = v === 'PASS' ? 'ok' : (v === 'FAIL' ? 'fail' : 'warn');
  return `<span class="badge ${cls}">${v}</span>`;
}

function qcLine(s){
  const q = s.qc; if (!q || q.verdict === undefined) return '';
  const nums = `亮度 ${q.brightness} · 反差 ${q.contrast} · 色温 ${q.warmth} · 颗粒 ${q.grain} · 运动 ${q.motion_median}`
    + ` · 脸 ${q.faces_sure} · 手 ${q.hands}`;
  const notes = [].concat(q.reasons || [], q.warnings || []);
  return `<div class="qc"><div class="nums">${nums}</div>`
    + (notes.length ? `<div class="why">${notes.join('；')}</div>` : '') + `</div>`;
}

function applyFilter(){
  const bad = s => (s.qc && (s.qc.verdict === 'FAIL' || s.qc.verdict === 'WARN'));
  const list = onlyBad ? shots.filter(bad) : shots;
  document.getElementById('grid').innerHTML = list.map(card).join('');
}

function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(()=>t.classList.remove('show'), 1800);
}

function card(s){ return `
    <div class="card ${saved[s.shot]?'bad':''}" data-shot="${s.shot}">
      <div class="head">
        <span class="sid">${s.shot}</span>
        ${badge(s)}
        <span class="state ${s.status==='completed'?'done':''}">${s.status === 'completed'
          ? (s.frames ? s.width+'×'+s.height+' · '+s.frames+' 帧' : '已完成') : (s.status || '待生成')}</span>
      </div>
      ${s.sheet ? `<img src="/qa/${s.sheet}" loading="lazy" onclick="window.open('/qa/${s.sheet}')">`
                : '<div style="height:120px;display:grid;place-items:center;color:#6b6555">还没有接触表</div>'}
      <div class="body">
        <div class="purpose">${s.purpose || ''}</div>
        <div class="meta">运镜：${s.camera || '—'}<br>转场：${s.transition || '—'}</div>
        ${qcLine(s)}
      </div>
      <div class="foot">
        <input placeholder="标红原因（选填）：露脸 / 畸变 / 假文字 / 换场 / 血腥"
               value="${(saved[s.shot]||'')}" oninput="mark('${s.shot}', this.value)">
        <button class="danger" onclick="clearOne('${s.shot}')">清除</button>
      </div>
    </div>`; }

function render(){
  applyFilter();
  document.getElementById('count').textContent =
    `共 ${shots.length} 镜 · 已标红 ${Object.keys(saved).length} 个`
    + (qcDone ? ` · 检验 ${qcDone} 镜` : '');
}
let qcDone = 0;

function mark(shot, reason){
  if (reason.trim()) saved[shot] = reason.trim();
  else delete saved[shot];
  document.querySelector(`.card[data-shot="${shot}"]`).classList.toggle('bad', !!saved[shot]);
  document.getElementById('count').textContent =
    `共 ${shots.length} 镜 · 已标红 ${Object.keys(saved).length} 个`;
}

function clearOne(shot){
  delete saved[shot];
  const c = document.querySelector(`.card[data-shot="${shot}"]`);
  c.classList.remove('bad'); c.querySelector('input').value = '';
  render();
}

async function load(){
  const res = await fetch('/api/data'); shots = await res.json();
  qcDone = shots.filter(s => s.qc && s.qc.verdict).length;
  const rs = await fetch('/api/redos'); const rj = await rs.json();
  for (const [k,v] of Object.entries(rj.redos || {})) saved[k] = v;
  render();
}

document.getElementById('filter').onclick = () => {
  onlyBad = !onlyBad;
  document.getElementById('filter').textContent = onlyBad ? '显示全部' : '只看有问题的';
  render();
};

document.getElementById('save').onclick = async () => {
  const res = await fetch('/api/redos', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({redos: saved})});
  const j = await res.json(); toast(res.ok ? `已保存 ${j.count} 个标红 → REDO.json` : '保存失败');
};

document.getElementById('copy').onclick = async () => {
  const list = Object.keys(saved).sort();
  const text = JSON.stringify({only: list});
  try { await navigator.clipboard.writeText(text); toast(list.length ? '已复制 '+text : '还没有标红任何镜头'); }
  catch(e){ toast(text); }
};

load();
</script></body></html>
"""


def shot_data():
    story = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
    results = json.loads((HERE / "results.json").read_text(encoding="utf-8")) if (HERE / "results.json").exists() else {}
    rows = results.get("shots", results) if isinstance(results, dict) else {}
    out = []
    for shot in story["shots"]:
        if shot["kind"] != "agnes":
            continue
        info = rows.get(shot["id"], {}) if isinstance(rows, dict) else {}
        # CI 提交回分支的 results.json 里 contact_sheet 是空的（媒体本身不进 git），
        # 所以接触表以本地 qa/ 目录里有没有这张图为准，不靠 results.json 的字段。
        local = QA / f"{shot['id']}.jpg"
        meta = {}
        if (QA / f"{shot['id']}.json").exists():
            meta = json.loads((QA / f"{shot['id']}.json").read_text(encoding="utf-8"))
        qc = {}
        if QC_REPORT.exists():
            try:
                qc = json.loads(QC_REPORT.read_text(encoding="utf-8")).get(shot["id"], {})
            except Exception:
                qc = {}
        out.append({
            "shot": shot["id"],
            "chapter": shot["narration_id"],
            "purpose": shot.get("purpose", ""),
            "camera": shot.get("camera", ""),
            "transition": shot.get("transition_out", ""),
            "status": info.get("status", ""),
            "width": meta.get("width") or info.get("width"),
            "height": meta.get("height") or info.get("height"),
            "frames": meta.get("frames") or info.get("frames"),
            "sheet": f"{shot['id']}.jpg" if local.exists() else None,
            "qc": qc,
        })
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, kind: str = "text/html; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", ""):
            return self._send(PAGE.encode("utf-8"))
        if path == "/api/data":
            return self._send(json.dumps(shot_data(), ensure_ascii=False).encode("utf-8"), "application/json")
        if path == "/api/redos":
            redos = json.loads(REDO.read_text(encoding="utf-8")).get("redos", {}) if REDO.exists() else {}
            return self._send(json.dumps({"redos": redos}, ensure_ascii=False).encode("utf-8"), "application/json")
        if path.startswith("/qa/"):
            target = (QA / path[4:]).resolve()
            if QA.resolve() in target.parents and target.exists():
                return self._send(target.read_bytes(), "image/jpeg")
        self.send_error(404)

    def do_POST(self):
        if self.path.split("?")[0] == "/api/redos":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            redos = body.get("redos") or {}
            REDO.write_text(json.dumps({"redos": redos, "count": len(redos)},
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return self._send(json.dumps({"count": len(redos)}, ensure_ascii=False).encode("utf-8"),
                              "application/json")
        self.send_error(404)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"镜头复审页 http://0.0.0.0:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
