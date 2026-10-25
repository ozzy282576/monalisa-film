#!/usr/bin/env python3
"""按需恢复旁白媒体：从 chessboard64-audio-v1 GitHub Release 下载并校验 MP3。

音频二进制不进入 Git；story.json 与 manifest.json 入库，真实旁白作为 release asset 保存。
渲染工作流临时下载到 production/chessboard64/audio/，按 SHA-256 和脚本文本双重核验。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
OWNER_REPO = "ozzy282576/monalisa-film"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def download_with_gh(tag: str, files: list[str], dest: Path) -> bool:
    if not shutil.which("gh"):
        return False
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["gh", "release", "download", tag, "--repo", OWNER_REPO, "--dir", str(dest)]
    for name in files:
        cmd += ["--pattern", name]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError("gh release download failed: " + (proc.stderr or proc.stdout).strip())
    return True


def download_public(template: str, name: str, dest: Path) -> None:
    url = template.format(file=name)
    request = Request(url, headers={"User-Agent": "chessboard64-audio-restore/1.0"})
    with urlopen(request, timeout=120) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=HERE / "story.json")
    parser.add_argument("--manifest", type=Path, default=HERE / "audio/manifest.json")
    parser.add_argument("--dest", type=Path, default=HERE / "audio")
    args = parser.parse_args()
    project = json.loads(args.project.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = {c["id"]: c["text"] for c in project["chapters"]}
    clips = manifest.get("clips") or []
    if set(expected) != {c.get("id") for c in clips}:
        raise RuntimeError("audio/manifest.json clips do not match story.json chapters")
    for clip in clips:
        if clip.get("text") != expected[clip["id"]]:
            raise RuntimeError("Narration text mismatch: " + clip["id"])
        sha = clip.get("sha256", "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha.lower()):
            raise RuntimeError("Missing SHA-256 receipt for " + clip["id"] + " (audio has not been finalized yet)")
    args.dest.mkdir(parents=True, exist_ok=True)
    pending = [c for c in clips
               if not (args.dest / c["file"]).is_file()
               or digest(args.dest / c["file"]) != c["sha256"]]
    if pending:
        tag = manifest.get("release_tag")
        if not tag:
            raise RuntimeError("audio manifest is missing release_tag")
        with tempfile.TemporaryDirectory(prefix="chessboard64-audio-") as tmp:
            tmpdir = Path(tmp)
            names = [c["file"] for c in pending]
            downloaded_by_gh = download_with_gh(tag, names, tmpdir)
            for clip in pending:
                src = tmpdir / clip["file"]
                if not downloaded_by_gh or not src.is_file():
                    src = tmpdir / clip["file"]
                    download_public(manifest["asset_url_template"], clip["file"], src)
                actual = digest(src)
                if actual != clip["sha256"]:
                    raise RuntimeError(f"SHA-256 mismatch for {clip['file']}: {actual} != {clip['sha256']}")
                shutil.copyfile(src, args.dest / clip["file"])
                print(f"FETCHED {clip['id']} {actual}")
    for clip in clips:
        path = args.dest / clip["file"]
        if digest(path) != clip["sha256"]:
            raise RuntimeError("Audio failed final SHA-256 check: " + clip["id"])
        print(f"VERIFIED {clip['id']} {path.stat().st_size} bytes")
    print(f"AUDIO_COMPLETE {len(clips)} narration clips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
