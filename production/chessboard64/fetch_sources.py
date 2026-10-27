#!/usr/bin/env python3
"""按需恢复 CogVideoX-Flash 已生成片段；媒体不入 Git，只保留可校验收据。

Generated clips are never committed to Git. ``results.json`` stores the request
hash, byte size and SHA-256, so a re-render can fetch the exact same footage
without spending generation quota or silently substituting missing media.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from media import probe  # noqa: E402
# 所有请求哈希均来自本项目 CogVideoX-Flash payload；兼容未启用/已启用参考图的记录。
import generate_cogvideox as _cog  # noqa: E402


def cogvideox_request_hashes(project, shot):
    """返回纯文生和带参考图两种合法 payload 哈希，便于后续按需启用参考图。"""
    saved = _cog.REF_IMAGE_OK
    try:
        _cog.REF_IMAGE_OK = None
        plain = _cog.request_hash(project, shot)
        _cog.REF_IMAGE_OK = True
        with_portrait = _cog.request_hash(project, shot)
    finally:
        _cog.REF_IMAGE_OK = saved
    return plain, with_portrait

ATTEMPTS = 4
# CogVideoX-Flash 免费档常见单条约 5 秒；4 秒下限兼容短输出并拒绝空片。
MIN_DURATION = 4.0
MAX_DURATION = 20.0


def digest(path: Path) -> str:
    handle = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            handle.update(block)
    return handle.hexdigest()


def safe_url(url: str) -> str:
    """Keep the storage path for diagnostics, but never print its signed query string."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    last_error = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "arena-chessboard64-refetch/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    out.write(block)
            temporary.replace(destination)
            return
        except Exception as error:  # noqa: BLE001 - retried below
            last_error = error
            temporary.unlink(missing_ok=True)
            if attempt < ATTEMPTS:
                print(f"  retry {attempt}/{ATTEMPTS - 1} after {type(error).__name__}", flush=True)
                time.sleep(attempt * 5)
    raise RuntimeError(f"Download failed for {safe_url(url)}: {type(last_error).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=HERE / "story.json")
    parser.add_argument("--results", type=Path, default=HERE / "results.json")
    parser.add_argument("--dest", type=Path, required=True, help="Directory for Sxx.mp4 clips")
    args = parser.parse_args()

    project = json.loads(args.project.read_text(encoding="utf-8"))
    results = json.loads(args.results.read_text(encoding="utf-8"))

    needed = [shot for shot in project["shots"] if shot["kind"] == "cogvideo"]
    report = {"requested": len(needed), "downloaded": [], "reused": [], "missing": []}

    for shot in needed:
        sid = shot["id"]
        receipt = results.get("shots", {}).get(sid, {})
        destination = args.dest / f"{sid}.mp4"
        wanted_hashes = set(cogvideox_request_hashes(project, shot))
        url = receipt.get("video_url")
        if receipt.get("status") != "completed" or not url \
                or receipt.get("request_hash") not in wanted_hashes:
            report["missing"].append(sid)
            print(f"MISSING_RECEIPT {sid}: no verified generation to fetch", flush=True)
            continue
        if destination.exists() and digest(destination) == receipt["sha256"]:
            report["reused"].append(sid)
            continue
        print(f"FETCH {sid} {safe_url(url)} [signed query redacted]", flush=True)
        download(url, destination)
        found = digest(destination)
        if found != receipt["sha256"]:
            raise RuntimeError(f"{sid}: downloaded bytes do not match the recorded SHA-256 "
                               f"({found} != {receipt['sha256']})")
        info = probe(destination)
        if not MIN_DURATION <= info["duration"] <= MAX_DURATION or info.get("width", 0) < 640:
            raise RuntimeError(f"{sid}: fetched clip is unusable: {info}")
        report["downloaded"].append({"id": sid, "bytes": destination.stat().st_size,
                                     "duration": round(info["duration"], 3),
                                     "size": f"{info.get('width')}x{info.get('height')}"})
        print(f"  OK {sid} {destination.stat().st_size} bytes / {info['duration']:.2f}s", flush=True)

    if report["missing"]:
        raise RuntimeError("Clips without a verified generation (regeneration required): "
                           + ", ".join(report["missing"]))
    if len(report["downloaded"]) + len(report["reused"]) != len(needed):
        raise RuntimeError("Not all CogVideoX-Flash clips were restored: " + json.dumps(report, ensure_ascii=False))
    print("FETCH_COMPLETE " + json.dumps({"downloaded": len(report["downloaded"]),
                                          "reused": len(report["reused"]),
                                          "clips": len(needed)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
