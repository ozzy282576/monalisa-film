#!/usr/bin/env python3
"""Create Agnes clips, poll, download, QC, retry rejects."""
import json, os, shutil, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

KEY = os.environ.get("AGNES_API_KEY", "").strip()
BASE = "https://apihub.agnes-ai.com"
MODEL = "agnes-video-2.5-flash"
ROOT = Path(__file__).resolve().parent
CLIPS = ROOT / "clips"
STATE = ROOT / "work" / "tasks.json"
PROGRESS = ROOT / "work" / "progress.json"
CLIPS.mkdir(exist_ok=True)
(ROOT / "work").mkdir(exist_ok=True)
MAX_TRIES = 10
MIN_BYTES = 80_000
DUR_MIN = 9.0
DUR_MAX = 14.5

if not KEY:
    sys.exit("AGNES_API_KEY missing")


def which_ffmpeg():
    for name in ("ffprobe", "ffmpeg"):
        if shutil.which(name):
            continue
    return shutil.which("ffprobe")


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


def git_push_clip(sid, extra_paths=None):
    """Push each finished clip so the repo shows live progress."""
    if os.environ.get("CI") != "true":
        return
    paths = ["clips", "work/progress.json", "work/progress.md", "work/tasks.json"]
    if extra_paths:
        paths.extend(extra_paths)
    try:
        subprocess.run(["git", "config", "user.name", "arena-ai-coding-agent[bot]"], check=False)
        subprocess.run(
            ["git", "config", "user.email", "298482267+arena-ai-coding-agent[bot]@users.noreply.github.com"],
            check=False,
        )
        subprocess.run(["git", "add", "--"] + paths, check=False)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            return
        subprocess.run(
            ["git", "commit", "-m", f"clip {sid}: incremental QC snapshot"],
            check=False,
        )
        subprocess.run(["git", "pull", "--rebase", "origin", "arena/01a0e83e-monalisa-film"], check=False)
        subprocess.run(["git", "push", "origin", "HEAD:arena/01a0e83e-monalisa-film"], check=False)
        print(f"PUSHED snapshot after {sid}", flush=True)
    except Exception as e:
        print(f"PUSH skip {sid}: {e}", flush=True)


def write_progress(story, state):
    rows = []
    ok = fail = pend = 0
    for item in story:
        sid = item["id"]
        st = state.get(sid, {})
        dest = CLIPS / f"{sid}.mp4"
        status = st.get("qc") or st.get("status") or "pending"
        if dest.exists() and st.get("qc") == "pass":
            ok += 1
            status = "pass"
        elif st.get("qc") == "fail" and st.get("tries", 0) >= MAX_TRIES:
            fail += 1
            status = "fail"
        else:
            pend += 1
        rows.append(
            {
                "id": sid,
                "title": item.get("title"),
                "status": status,
                "tries": st.get("tries", 0),
                "bytes": st.get("bytes"),
                "duration": st.get("duration"),
                "reason": st.get("reason"),
            }
        )
    payload = {
        "ok": ok,
        "pending": pend,
        "fail": fail,
        "total": len(story),
        "updated": int(time.time()),
        "clips": rows,
    }
    PROGRESS.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    md = [f"# progress {ok}/{len(story)} pass, {pend} pending, {fail} fail", ""]
    for r in rows:
        md.append(
            f"- `{r['id']}` {r['title']}: **{r['status']}** tries={r['tries']} dur={r['duration']} bytes={r['bytes']} {r.get('reason') or ''}"
        )
    (ROOT / "work" / "progress.md").write_text("\n".join(md) + "\n")
    print(
        f"PROGRESS {ok}/{len(story)} pass, {pend} pending, {fail} fail",
        flush=True,
    )


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
    print(f"CREATE {item['id']} -> {code} {json.dumps(body)[:400]}", flush=True)
    if code >= 400:
        return None, f"http{code}:{json.dumps(body)[:300]}"
    vid = body.get("video_id") or body.get("id")
    if not vid:
        return None, f"no_video_id:{json.dumps(body)[:300]}"
    return {"video_id": vid, "raw": body, "status": body.get("status", "queued")}, None


def poll(video_id):
    url = f"{BASE}/agnesapi?video_id={video_id}&model_name={MODEL}"
    return req("GET", url)


def download(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)
    return dest.stat().st_size


def probe(path: Path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"duration": None, "width": None, "height": None, "nb_frames": None}
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,nb_frames,duration",
        "-show_entries",
        "format=duration,size",
        "-of",
        "json",
        str(path),
    ]
    raw = subprocess.check_output(cmd, text=True)
    data = json.loads(raw)
    fmt = data.get("format") or {}
    st = (data.get("streams") or [{}])[0]
    dur = st.get("duration") or fmt.get("duration")
    try:
        dur = float(dur) if dur is not None else None
    except ValueError:
        dur = None
    return {
        "duration": dur,
        "width": st.get("width"),
        "height": st.get("height"),
        "nb_frames": st.get("nb_frames"),
        "size": fmt.get("size"),
    }


def black_ratio(path: Path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return 0.0
    cmd = [
        ffmpeg,
        "-i",
        str(path),
        "-vf",
        "blackdetect=d=0.5:pic_th=0.98",
        "-an",
        "-f",
        "null",
        "-",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    text = p.stderr or ""
    total = 0.0
    for line in text.splitlines():
        if "black_duration:" in line:
            try:
                total += float(line.split("black_duration:")[-1].split()[0])
            except ValueError:
                pass
    info = probe(path)
    dur = info.get("duration") or 12.0
    return total / dur if dur else 0.0


def qc_clip(path: Path, expected=12.0):
    if not path.exists():
        return False, "missing", {}
    size = path.stat().st_size
    if size < MIN_BYTES:
        return False, f"too_small:{size}", {"bytes": size}
    info = probe(path)
    dur = info.get("duration")
    reasons = []
    if dur is None:
        reasons.append("no_duration")
    elif dur < DUR_MIN or dur > DUR_MAX:
        reasons.append(f"duration:{dur:.2f}")
    w, h = info.get("width"), info.get("height")
    if w and w < 640:
        reasons.append(f"width:{w}")
    if w and h and abs((w / h) - (16 / 9)) > 0.08:
        reasons.append(f"aspect:{w}x{h}")
    try:
        br = black_ratio(path)
        info["black_ratio"] = br
        if br > 0.45:
            reasons.append(f"black:{br:.2f}")
    except Exception as e:
        info["black_err"] = str(e)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        p = subprocess.run(
            [ffmpeg, "-i", str(path), "-vf", "freezedetect=n=0.003:d=2.5", "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        if "freeze_start" in (p.stderr or "") and (p.stderr or "").count("freeze_start") >= 2:
            reasons.append("frozen_frames")
    info["bytes"] = size
    if reasons:
        return False, ",".join(reasons), info
    return True, "ok", info


GAP_SEC = 75
QUEUE_GAP_SEC = 240
FORCE_REDO = {"02", "05", "11"}


def wait_gap(reason, seconds=None):
    n = seconds if seconds is not None else GAP_SEC
    if "queue_full" in (reason or "") or "503" in (reason or ""):
        n = QUEUE_GAP_SEC
    print(f"WAIT {n}s before next create ({reason})", flush=True)
    time.sleep(n)


def process_one(item, story, state):
    """Create + poll + QC a single clip. Never starts another clip in parallel."""
    sid = item["id"]
    dest = CLIPS / f"{sid}.mp4"
    st = state.get(sid, {}) or {}
    if dest.exists() and st.get("qc") != "fail":
        ok, reason, info = qc_clip(dest)
        st.update({"path": str(dest), "bytes": dest.stat().st_size, "duration": info.get("duration")})
        if ok:
            st["qc"] = "pass"
            st["reason"] = reason
            state[sid] = st
            save_state(state)
            write_progress(story, state)
            print(f"SKIP {sid} already QC pass dur={info.get('duration')}", flush=True)
            return True
        print(f"QC FAIL existing {sid} {reason} -> retry", flush=True)
        dest.unlink(missing_ok=True)
        st = {"tries": 0, "qc": "fail", "reason": reason}

    # drop stale failed ids so we create fresh one-at-a-time
    if st.get("status") in ("create_failed", "failed") or st.get("qc") == "fail":
        st.pop("video_id", None)

    while st.get("tries", 0) < MAX_TRIES:
        if not st.get("video_id"):
            created, err = create_task(item)
            st["tries"] = st.get("tries", 0) + 1
            if not created:
                st["status"] = "create_failed"
                st["error"] = err or "create_failed"
                st["reason"] = err or "create_failed"
                state[sid] = st
                save_state(state)
                write_progress(story, state)
                git_push_clip(sid)
                print(f"CREATE FAIL {sid} tries={st['tries']} {err}", flush=True)
                wait_gap(f"create_failed {sid}")
                continue
            created["tries"] = st["tries"]
            st = created
            state[sid] = st
            save_state(state)
            write_progress(story, state)
            git_push_clip(sid)

        while True:
            vid = st.get("video_id")
            code, body = poll(vid)
            status = (body or {}).get("status") or ""
            url = (body or {}).get("url")
            print(
                f"POLL {sid} try={st.get('tries')} {code} {status} progress={(body or {}).get('progress')}",
                flush=True,
            )
            st["status"] = status
            st["poll"] = {k: (body or {}).get(k) for k in ("status", "progress", "error", "seconds")}
            state[sid] = st
            save_state(state)
            if status == "completed" and url:
                size = download(url, dest)
                ok, reason, info = qc_clip(dest)
                st["path"] = str(dest)
                st["bytes"] = size
                st["duration"] = info.get("duration")
                st["reason"] = reason
                if ok:
                    st["qc"] = "pass"
                    print(f"QC PASS {sid} {size}B dur={info.get('duration')}", flush=True)
                    state[sid] = st
                    save_state(state)
                    write_progress(story, state)
                    git_push_clip(sid)
                    return True
                print(f"QC FAIL {sid} {reason} -> regenerate after gap", flush=True)
                dest.unlink(missing_ok=True)
                st["qc"] = "fail"
                st.pop("video_id", None)
                state[sid] = st
                save_state(state)
                write_progress(story, state)
                git_push_clip(sid)
                wait_gap(f"qc_fail {sid}")
                break
            if status == "failed":
                print(f"GEN FAIL {sid} {body}", flush=True)
                st["qc"] = "fail"
                st["reason"] = f"agnes:{body}"
                st.pop("video_id", None)
                state[sid] = st
                save_state(state)
                write_progress(story, state)
                git_push_clip(sid)
                wait_gap(f"gen_fail {sid}")
                break
            time.sleep(8)
    print(f"GIVE UP {sid} after {st.get('tries')} tries", flush=True)
    state[sid] = st
    save_state(state)
    write_progress(story, state)
    git_push_clip(sid)
    return False


def main():
    story = json.loads((ROOT / "storyboard.json").read_text())
    state = load_state()
    for item in story:
        sid = item["id"]
        st = state.get(sid, {})
        dest = CLIPS / f"{sid}.mp4"
        if sid in FORCE_REDO and dest.exists():
            print(f"FORCE REDO {sid} visual QC failed last round", flush=True)
            dest.unlink(missing_ok=True)
            st = {"tries": 0, "status": "queued", "qc": "redo"}
            state[sid] = st
        elif not (dest.exists() and st.get("qc") == "pass"):
            st["tries"] = 0
            st.pop("video_id", None)
            st["status"] = "queued"
            state[sid] = st
    save_state(state)
    write_progress(story, state)
    print("COOLDOWN 180s before first new create", flush=True)
    time.sleep(180)
    last_created = False
    for item in story:
        sid = item["id"]
        dest = CLIPS / f"{sid}.mp4"
        st = state.get(sid, {})
        if dest.exists() and st.get("qc") == "pass":
            print(f"KEEP {sid}", flush=True)
            continue
        if last_created:
            wait_gap(f"before starting {sid}")
        print(f"START sequential clip {sid} {item.get('title')}", flush=True)
        ok = process_one(item, story, state)
        last_created = True
        if not ok:
            print(f"clip {sid} not passed, continue to next after gap", flush=True)
    failed = [i["id"] for i in story if state.get(i["id"], {}).get("qc") != "pass"]
    if failed:
        raise SystemExit(f"unqualified clips: {failed}")
    print("ALL DONE all clips QC pass", flush=True)


if __name__ == "__main__":
    main()
