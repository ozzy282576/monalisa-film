#!/usr/bin/env python3
"""Restore the already-generated footage (Agnes 或智谱 CogVideoX-Flash) on a fresh runner.

Generated clips are never committed to Git: they live on the provider CDN and in
Actions artifacts. Every generation is recorded in ``results.json`` with its
request hash, byte size and SHA-256, so a re-render can pull the exact same
footage back instead of spending new generation quota — and, crucially, cannot
quietly substitute something else when a clip is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from media import probe  # noqa: E402
# 2026-10-11：本片 38 镜改走智谱 CogVideoX-Flash 后，收据里的 request_hash 是
# generate_cogvideox 的 payload 哈希；且 5 个露脸镜（S06/S12/S16/S27/S40）实测
# 被 flash 收下 image_url、以定妆照图生视频，其收据哈希是「带定妆照」版本。
# 旧代码只认 Agnes 哈希，会把整批智谱收据判成 MISSING_RECEIPT、render 直接缺料。
# 三种合法哈希都认（Agnes / 智谱纯文生 / 智谱带定妆照），防掉包的严格性不变。
from generate import request_hash as agnes_request_hash  # noqa: E402
import generate_cogvideox as _cog  # noqa: E402


def cogvideox_request_hashes(project, shot):
    """同一镜头的两种智谱哈希：纯文生 与 带定妆照（image_url）。"""
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
# 4.0 与 media.inspect_clip / jeong2000 实证窗口对齐：CogVideoX-Flash 出片 5.108 s，
# 旧值 6.0 按 Agnes（6–12 s）定的，会把智谱素材全部判成 unusable。
MIN_DURATION = 4.0
MAX_DURATION = 20.0


def digest(path: Path) -> str:
    handle = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            handle.update(block)
    return handle.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    last_error = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "arena-kitakyushu2002-refetch/1.0"})
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
                print(f"  retry {attempt}/{ATTEMPTS - 1} after {type(error).__name__}: {error}", flush=True)
                time.sleep(attempt * 5)
    raise RuntimeError(f"Download failed for {url}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=HERE / "story.json")
    parser.add_argument("--results", type=Path, default=HERE / "results.json")
    parser.add_argument("--dest", type=Path, required=True, help="Directory for Sxx.mp4 clips")
    args = parser.parse_args()

    project = json.loads(args.project.read_text(encoding="utf-8"))
    results = json.loads(args.results.read_text(encoding="utf-8"))
    from generate import request_hash  # noqa: E402 - imports the Agnes client config

    needed = [shot for shot in project["shots"] if shot["kind"] == "agnes"]
    report = {"requested": len(needed), "downloaded": [], "reused": [], "missing": []}

    for shot in needed:
        sid = shot["id"]
        receipt = results.get("shots", {}).get(sid, {})
        destination = args.dest / f"{sid}.mp4"
        wanted_hashes = {agnes_request_hash(project, shot),
                         *cogvideox_request_hashes(project, shot)}
        url = receipt.get("video_url")
        if receipt.get("status") != "completed" or not url \
                or receipt.get("request_hash") not in wanted_hashes:
            report["missing"].append(sid)
            print(f"MISSING_RECEIPT {sid}: no verified generation to fetch", flush=True)
            continue
        if destination.exists() and digest(destination) == receipt["sha256"]:
            report["reused"].append(sid)
            continue
        print(f"FETCH {sid} {url}", flush=True)
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
        raise RuntimeError("Not all Agnes clips were restored: " + json.dumps(report, ensure_ascii=False))
    print("FETCH_COMPLETE " + json.dumps({"downloaded": len(report["downloaded"]),
                                          "reused": len(report["reused"]),
                                          "clips": len(needed)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
