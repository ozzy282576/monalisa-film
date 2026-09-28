#!/usr/bin/env python3
import json, os, sys, time, urllib.request, urllib.error, ssl
from pathlib import Path

KEY = os.environ.get("AGNES_API_KEY", "").strip()
BASE = "https://apihub.agnes-ai.com"
MODEL = "agnes-video-2.5-flash"
ROOT = Path(__file__).resolve().parent
CLIPS = ROOT / "clips"
STATE = ROOT / "work" / "tasks.json"
CLIPS.mkdir(exist_ok=True)
(ROOT / "work").mkdir(exist_ok=True)

if not KEY:
    sys.exit("AGNES_API_KEY missing")

def req(method, url, body=None, timeout=120, attempts=6):
    data = None if body is None else json.dumps(body).encode()
    last = None
    for i in range(attempts):
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Authorization", f"Bearer {KEY}")
        r.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw.decode() or "{}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"error": raw}
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}

def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2))

def create_task(item):
    payload = {
        "model": MODEL,
        "prompt": item["prompt"],
        "seconds": str(item["seconds"]),
        "mode": "text",
        "size": "720P",
        "aspect_ratio": "16:9",
    }
    code, body = req("POST", f"{BASE}/v1/videos", payload)
    print(f"CREATE {item['id']} -> {code} {body}", flush=True)
    if code >= 400:
        return None
    vid = body.get("video_id") or body.get("id")
    return {"video_id": vid, "raw": body, "status": body.get("status", "queued")}

def poll(video_id):
    url = f"{BASE}/agnesapi?video_id={video_id}&model_name={MODEL}"
    code, body = req("GET", url)
    return code, body

def download(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)
    return dest.stat().st_size

def main():
    story = json.loads((ROOT / "storyboard.json").read_text())
    state = load_state()
    # create missing
    for item in story:
        sid = item["id"]
        st = state.get(sid, {})
        if st.get("path") and Path(st["path"]).exists() and Path(st["path"]).stat().st_size > 10000:
            print(f"SKIP {sid} already downloaded", flush=True)
            continue
        if not st.get("video_id"):
            created = create_task(item)
            if not created:
                time.sleep(2)
                created = create_task(item)
            if not created:
                state[sid] = {"error": "create_failed"}
                save_state(state)
                continue
            state[sid] = created
            save_state(state)
            time.sleep(0.5)

    # poll loop
    pending = True
    while pending:
        pending = False
        for item in story:
            sid = item["id"]
            st = state.get(sid, {})
            dest = CLIPS / f"{sid}.mp4"
            if dest.exists() and dest.stat().st_size > 10000:
                st["path"] = str(dest)
                st["status"] = "completed"
                state[sid] = st
                continue
            vid = st.get("video_id")
            if not vid:
                pending = True
                continue
            code, body = poll(vid)
            status = (body or {}).get("status") or ""
            url = (body or {}).get("url")
            print(f"POLL {sid} {code} {status} progress={(body or {}).get('progress')}", flush=True)
            st["status"] = status
            st["poll"] = body
            if status == "completed" and url:
                try:
                    size = download(url, dest)
                    st["path"] = str(dest)
                    st["bytes"] = size
                    print(f"DL {sid} {size} bytes", flush=True)
                except Exception as e:
                    print(f"DL FAIL {sid} {e}", flush=True)
                    pending = True
            elif status == "failed":
                print(f"FAIL {sid} {body}", flush=True)
                # retry create once
                if not st.get("retried"):
                    created = create_task(item)
                    if created:
                        created["retried"] = True
                        state[sid] = created
                        pending = True
            else:
                pending = True
            state[sid] = st
        save_state(state)
        if pending:
            time.sleep(8)
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
