#!/usr/bin/env python3
"""Resumable uploader that persists a new source video to the Arena branch."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "incoming_uploads"
PARTS_DIR = ROOT / "production" / "new_source_parts"
MANIFEST = PARTS_DIR / "manifest.json"
BRANCH = "arena/01a03c8f-desktop-tutorial"
CHUNK_SIZE = 5 * 1024 * 1024
GIT_PART_SIZE = 45_000_000
MAX_SIZE = 3 * 1024**3
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATE_LOCK = threading.Lock()
STATE: dict = {"phase": "idle", "message": "等待上传"}

PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>上传全新电影解说</title><style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 20% 0,#1d2942,#080c15 52%,#04060b);color:#f3f6ff;font:15px/1.65 system-ui,"Microsoft YaHei"}main{width:min(740px,92vw);padding:32px;background:#141b2bf5;border:1px solid #35435f;border-radius:20px;box-shadow:0 24px 80px #0009}h1{margin:0 0 8px}.lead,.small{color:#aebbd1}.notice{margin:20px 0;padding:13px 15px;background:#202a40;border-left:4px solid #7199ff;border-radius:9px}.pick{display:block;margin:20px 0;padding:40px 20px;border:2px dashed #5d729a;border-radius:14px;text-align:center;cursor:pointer}.pick input{display:none}button{padding:12px 22px;border:0;border-radius:10px;background:#5d87f7;color:white;font-weight:750}button:disabled{opacity:.4}.track{height:10px;margin:20px 0 8px;background:#2a354d;border-radius:99px;overflow:hidden}.bar{height:100%;width:0;background:linear-gradient(90deg,#557ff3,#74c7ff)}.ok{color:#50dda0;font-weight:700}.warn{color:#ffd36e}.err{color:#ff8181}.file{word-break:break-all;color:#c1cbe0}.existing{margin-top:20px;padding:12px 14px;background:#101724;border-radius:10px}</style><main><h1>上传全新电影解说视频</h1><p class=lead>支持 MP4、MOV、MKV、WebM，最大 3 GB。</p><div class=notice><b>请等待两个阶段全部完成：</b><br>① 浏览器上传；② 自动分卷并推送至制作分支。只有页面显示“远端持久保存完成”后，才可以关闭页面或回到对话。</div><label class=pick>点击选择视频<br><span class=small>采用5 MB分块上传并自动重试</span><input id=f type=file accept="video/*,.mp4,.mov,.mkv,.webm"></label><div id=n class=file>尚未选择文件</div><p><button id=g disabled>开始上传</button></p><div class=track><div id=b class=bar></div></div><div id=s>等待选择视频</div><div id=e class=existing>正在检查远端保存状态…</div></main><script>const C=5*1024*1024,f=document.querySelector('#f'),g=document.querySelector('#g'),b=document.querySelector('#b'),s=document.querySelector('#s'),n=document.querySelector('#n'),e=document.querySelector('#e');let x;const wait=m=>new Promise(r=>setTimeout(r,m));async function getStatus(){let j=await(await fetch('/status')).json();if(j.persisted){e.className='existing ok';e.innerHTML=`<b>远端持久保存完成 ✓</b><br>${j.persisted.name}（${(j.persisted.size/1048576).toFixed(1)} MB）<br>SHA-256：${j.persisted.sha256}<br>分卷：${j.persisted.parts.length} 个`;return j}if(j.phase==='error'){e.className='existing err';e.textContent='持久保存失败：'+j.message}else if(j.phase!=='idle'){e.className='existing warn';e.textContent='正在持久保存：'+j.message}else{e.className='existing';e.textContent='远端尚无新视频'}return j}getStatus().catch(()=>e.textContent='状态读取失败');f.onchange=()=>{x=f.files[0];n.textContent=x?`${x.name}（${(x.size/1048576).toFixed(1)} MB）`:'尚未选择文件';g.disabled=!x};async function send(id,i,t,a,z){let q=new URLSearchParams({id,name:x.name,index:i,total:t,size:x.size,offset:a});for(let k=1;k<=6;k++){try{let r=await fetch('/upload?'+q,{method:'POST',body:z});let j=await r.json();if(!r.ok)throw Error(j.error);return j}catch(err){if(k===6)throw err;s.textContent=`网络波动，第 ${k} 次重试…`;await wait(k*900)}}}async function waitPersisted(hash){for(let i=0;i<900;i++){let j=await getStatus();if(j.persisted&&j.persisted.sha256===hash)return;if(j.phase==='error')throw Error(j.message);s.className='warn';s.textContent='浏览器上传完成，正在分卷并推送到远端，请勿关闭页面…';await wait(2000)}throw Error('远端保存等待超时')}g.onclick=async()=>{g.disabled=true;f.disabled=true;let id=Date.now().toString(36)+Math.random().toString(36).slice(2),t=Math.ceil(x.size/C),last;try{for(let i=0;i<t;i++){let a=i*C,z=Math.min(x.size,a+C);s.className='';s.textContent=`上传中 ${(z/1048576).toFixed(0)} / ${(x.size/1048576).toFixed(0)} MB（${i+1}/${t}）`;last=await send(id,i,t,a,x.slice(a,z));b.style.width=(z/x.size*100)+'%'}await waitPersisted(last.sha256);s.className='ok';s.textContent='上传及远端持久保存完成 ✓ 可以回到对话';g.textContent='全部完成'}catch(err){s.className='err';s.textContent='处理失败：'+err.message;g.disabled=false;f.disabled=false}};</script></html>'''


def safe_name(value: str) -> str:
    value = re.sub(r"[\x00-\x1f/\\]", "_", Path(value).name).strip()
    return (value or "uploaded-video.mp4")[:220]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_manifest() -> dict | None:
    if not MANIFEST.exists():
        return None
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if data.get("persisted") and all((PARTS_DIR / name).exists() for name in data["parts"]):
            return data
    except Exception:
        pass
    return None


def set_state(phase: str, message: str, **extra) -> None:
    with STATE_LOCK:
        STATE.clear()
        STATE.update({"phase": phase, "message": message, **extra})
    print(f"PERSIST {phase}: {message}", flush=True)


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=True,
    )


def persist_to_branch(source: Path, info: dict) -> None:
    try:
        set_state("splitting", "正在生成 Git 安全分卷")
        staging = ROOT / "production" / ".new_source_parts.tmp"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        parts = []
        with source.open("rb") as handle:
            index = 0
            while True:
                block = handle.read(GIT_PART_SIZE)
                if not block:
                    break
                name = f"source.part-{index:03d}"
                (staging / name).write_bytes(block)
                parts.append(name)
                index += 1
        manifest = {
            **info,
            "part_size": GIT_PART_SIZE,
            "parts": parts,
            "persisted": True,
            "branch": BRANCH,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shutil.rmtree(PARTS_DIR, ignore_errors=True)
        os.replace(staging, PARTS_DIR)
        set_state("committing", f"正在提交 {len(parts)} 个分卷")
        run_git("add", "-f", "production/new_source_parts")
        changed = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=ROOT
        ).returncode != 0
        if changed:
            run_git("commit", "-m", f"Store new commentary source {info['sha256'][:12]}")
        set_state("pushing", "正在推送到远端制作分支，请继续等待")
        run_git("push", "origin", BRANCH)
        set_state("done", "远端持久保存完成", persisted=manifest)
        print(
            f"UPLOAD PERSISTED {info['name']} {info['size']} {info['sha256']} "
            f"parts={len(parts)}",
            flush=True,
        )
    except Exception as exc:
        set_state("error", str(exc))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def json_response(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urllib.parse.urlsplit(self.path).path == "/status":
            with STATE_LOCK:
                state = dict(STATE)
            persisted = state.get("persisted") or read_manifest()
            self.json_response(200, {**state, "persisted": persisted})
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path != "/upload":
                raise ValueError("上传地址无效")
            query = urllib.parse.parse_qs(parsed.query)
            get = lambda key: query[key][0]
            uid = re.sub(r"[^A-Za-z0-9_-]", "", get("id"))
            filename = safe_name(get("name"))
            index, total = int(get("index")), int(get("total"))
            size, offset = int(get("size")), int(get("offset"))
            length = int(self.headers.get("Content-Length", "0"))
            if not uid or not (0 <= index < total <= 2000 and 0 < size <= MAX_SIZE):
                raise ValueError("文件或分块参数无效")
            if offset != index * CHUNK_SIZE or length != min(CHUNK_SIZE, size - offset):
                raise ValueError("分块位置或大小无效")
            partial = UPLOAD_DIR / f".{uid}.part"
            received_path = UPLOAD_DIR / f".{uid}.json"
            with partial.open("r+b" if partial.exists() else "w+b") as handle:
                handle.seek(offset)
                remaining = length
                while remaining:
                    block = self.rfile.read(min(remaining, 1024 * 1024))
                    if not block:
                        raise ValueError("上传连接提前中断")
                    handle.write(block)
                    remaining -= len(block)
            received = set(json.loads(received_path.read_text()) if received_path.exists() else [])
            received.add(index)
            received_path.write_text(json.dumps(sorted(received)), encoding="utf-8")
            done = len(received) == total and all(i in received for i in range(total))
            response = {"ok": True, "done": done}
            if done:
                if partial.stat().st_size != size:
                    raise ValueError("文件大小校验失败")
                target = UPLOAD_DIR / filename
                os.replace(partial, target)
                received_path.unlink(missing_ok=True)
                digest = file_hash(target)
                info = {"name": filename, "size": size, "sha256": digest}
                response.update(info)
                set_state("received", "浏览器上传完成，准备持久保存")
                threading.Thread(
                    target=persist_to_branch, args=(target, info), daemon=True
                ).start()
            self.json_response(200, response)
        except Exception as exc:
            self.json_response(400, {"error": str(exc)})


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
