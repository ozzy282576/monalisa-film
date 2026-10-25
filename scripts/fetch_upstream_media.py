#!/usr/bin/env python3
"""按 scripts/upstream-media-manifest.json 恢复上游媒体素材（成片 / 抽帧 / 配音 / 定妆照）。

这些文件被 .gitignore 排除、不进 git；本脚本从上游 tag 的 codeload 快照下载并逐文件
做 SHA-256 校验后放回仓库对应路径。

用法：
    python3 scripts/fetch_upstream_media.py                # 只下载缺失或校验失败的文件
    python3 scripts/fetch_upstream_media.py --verify       # 只校验当前已有文件，不下载
    python3 scripts/fetch_upstream_media.py --force        # 全部重新下载覆盖
    python3 scripts/fetch_upstream_media.py --tarball X.gz # 使用已下载好的快照压缩包
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "scripts", "upstream-media-manifest.json")


def sha256_file(path: str, buf_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(buf_size), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def verify_present(manifest: dict) -> tuple[list[str], list[str]]:
    """返回 (缺失文件, 校验失败文件) 列表。"""
    missing: list[str] = []
    mismatched: list[str] = []
    total = len(manifest["files"])
    for i, entry in enumerate(manifest["files"], 1):
        rel = entry["path"]
        dst = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(dst):
            missing.append(rel)
        elif sha256_file(dst) != entry["sha256"]:
            mismatched.append(rel)
        if i % 200 == 0 or i == total:
            print(f"  校验进度 {i}/{total}", flush=True)
    return missing, mismatched


def download_tarball(url: str, expected_sha: str, cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, os.path.basename(url) or "snapshot.tar.gz")
    if os.path.isfile(dest) and sha256_file(dest) == expected_sha:
        print(f"[i] 已存在校验通过的快照：{dest}")
        return dest
    print(f"[i] 下载快照：{url}")
    req = urllib.request.Request(url, headers={"User-Agent": "fetch-upstream-media/1.0"})
    tmp = dest + ".part"
    with urllib.request.urlopen(req) as resp, open(tmp, "wb") as out:
        copied = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            copied += len(chunk)
            if copied % (50 * 1 << 20) < (1 << 20):
                print(f"  已下载 {copied / 1e6:.0f} MB", flush=True)
    actual = sha256_file(tmp)
    if actual != expected_sha:
        os.remove(tmp)
        raise SystemExit(f"[x] 快照 SHA-256 不匹配：期望 {expected_sha}，实际 {actual}")
    os.replace(tmp, dest)
    print(f"[i] 快照校验通过（SHA-256 {actual[:12]}…）")
    return dest


def extract_tarball(tarball: str, work_dir: str) -> str:
    print("[i] 解压快照……")
    with tarfile.open(tarball, "r:gz") as tf:
        try:
            tf.extractall(work_dir, filter="data")  # Python 3.12+
        except TypeError:
            tf.extractall(work_dir)
    entries = os.listdir(work_dir)
    if len(entries) != 1:
        raise SystemExit(f"[x] 快照顶层目录异常：{entries}")
    root = os.path.join(work_dir, entries[0])
    if not os.path.isdir(root):
        raise SystemExit(f"[x] 快照顶层不是目录：{root}")
    return root


def restore(manifest: dict, snapshot_root: str, force: bool) -> None:
    total = len(manifest["files"])
    restored = skipped = failed = 0
    for i, entry in enumerate(manifest["files"], 1):
        rel = entry["path"]
        dst = os.path.join(REPO_ROOT, rel)
        if not force and os.path.isfile(dst) and sha256_file(dst) == entry["sha256"]:
            skipped += 1
            continue
        src = os.path.join(snapshot_root, rel)
        if not os.path.isfile(src):
            print(f"  [x] 快照中找不到 {rel}")
            failed += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if sha256_file(dst) != entry["sha256"]:
            print(f"  [x] 放回后校验失败：{rel}")
            failed += 1
            continue
        restored += 1
        if i % 100 == 0 or i == total:
            print(f"  恢复进度 {i}/{total}（本次新放回 {restored}）", flush=True)
    print(f"[i] 完成：新放回 {restored}，已存在跳过 {skipped}，失败 {failed}，共 {total} 个媒体文件")
    if failed:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="恢复上游媒体素材（按需下载，SHA-256 校验）")
    parser.add_argument("--verify", action="store_true", help="只校验已有文件，不下载")
    parser.add_argument("--force", action="store_true", help="全部重新下载覆盖")
    parser.add_argument("--tarball", help="使用本地快照压缩包，不联网下载")
    args = parser.parse_args()

    manifest = load_manifest()
    print(f"[i] 清单：{manifest['source_repo']} @ {manifest['source_ref']}")
    print(f"[i] 媒体文件 {manifest['media_file_count']} 个，合计 "
          f"{manifest['media_total_bytes'] / 1e6:.1f} MB")

    if args.verify:
        missing, mismatched = verify_present(manifest)
        print(f"[i] 校验结果：缺失 {len(missing)}，校验失败 {len(mismatched)}")
        for rel in (missing + mismatched)[:20]:
            print(f"  - {rel}")
        raise SystemExit(1 if (missing or mismatched) else 0)

    missing, mismatched = verify_present(manifest)
    if not args.force and not missing and not mismatched:
        print("[i] 所有媒体文件已存在且校验通过，无需下载。")
        return
    print(f"[i] 待恢复：缺失 {len(missing)}，校验失败 {len(mismatched)}")

    cache_dir = os.path.join(REPO_ROOT, ".cache", "upstream")
    if args.tarball:
        tarball = os.path.abspath(args.tarball)
        if sha256_file(tarball) != manifest["tarball_sha256"]:
            raise SystemExit("[x] 本地快照 SHA-256 与清单记录不一致")
    else:
        tarball = download_tarball(manifest["tarball_url"], manifest["tarball_sha256"], cache_dir)

    with tempfile.TemporaryDirectory(prefix="upstream-media-", dir=cache_dir) as work_dir:
        snapshot_root = extract_tarball(tarball, work_dir)
        restore(manifest, snapshot_root, force=args.force)

    print("[i] 再跑一次 --verify 可确认全量一致。")


if __name__ == "__main__":
    main()
