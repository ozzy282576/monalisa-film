#!/usr/bin/env python3
"""Concatenate Agnes clips in storyboard order. No Ken Burns / stills."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIPS = ROOT / "clips"
OUT = ROOT / "out"
WORK = ROOT / "work"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

story = json.loads((ROOT / "storyboard.json").read_text())
missing = []
paths = []
for item in story:
    p = CLIPS / f"{item['id']}.mp4"
    if not p.exists() or p.stat().st_size < 10_000:
        missing.append(item["id"])
    else:
        paths.append(p)

report = {"missing": missing, "n_ok": len(paths), "n_story": len(story)}
(WORK / "assemble.json").write_text(json.dumps(report, indent=2))
if missing:
    raise SystemExit(f"missing clips: {missing}")

lst = WORK / "concat.txt"
lst.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
out = OUT / "monalisa_theft.mp4"
subprocess.check_call(
    [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(lst),
        "-c",
        "copy",
        str(out),
    ]
)
print("wrote", out, "bytes", out.stat().st_size)
