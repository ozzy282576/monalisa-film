#!/usr/bin/env python3
"""Export a compact, deterministic visual-review pack from a completed frame audit.

The full 5400-frame contact sheets are useful for scanning. This helper adds
larger (at most 960-pixel-wide) frames at every machine-selected temporal,
face, and hand-geometry review point, so a reviewer does not need to retrieve a
large ephemeral GitHub Actions artifact to inspect the candidates.

It deliberately exports evidence only. It never changes the audit result or
marks a human review approved.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

import av
from PIL import Image


MAX_WIDTH = 960
JPEG_QUALITY = 90


def _add(selected: dict[int, set[str]], frame: int, reason: str) -> None:
    if frame < 0:
        return
    selected[frame].add(reason)


def _collect(audit: dict) -> dict[int, set[str]]:
    selected: dict[int, set[str]] = defaultdict(set)
    checks = audit.get("checks", {})

    for event in checks.get("temporal_outlier_windows", []):
        start, end = int(event["start_frame"]), int(event["end_frame"])
        shot = str(event.get("shot", "unknown"))
        for frame, part in ((start, "start"), ((start + end) // 2, "middle"), (end, "end")):
            _add(selected, frame, f"temporal-{shot}-{part}")

    for event in checks.get("face_review_candidates", []):
        _add(selected, int(event["frame"]), f"face-{event.get('shot', 'unknown')}")

    # Hundreds of adjacent detector events in a single shot do not need hundreds
    # of exports. Retain the median event of every affected shot, plus its reason.
    by_shot: dict[str, list[dict]] = defaultdict(list)
    for event in checks.get("hand_landmark_extreme_events", []):
        by_shot[str(event.get("shot", "unknown"))].append(event)
    for shot, events in sorted(by_shot.items()):
        events.sort(key=lambda row: int(row["frame"]))
        event = events[len(events) // 2]
        _add(selected, int(event["frame"]), f"hand-geometry-{shot}")

    return dict(sorted(selected.items()))


def _safe_reason(reason: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", reason).strip("-")[:72]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--film", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    selected = _collect(audit)
    if not selected:
        raise SystemExit("No review candidates in audit; refusing to create an empty evidence pack")
    if not args.film.is_file():
        raise SystemExit(f"Missing film: {args.film}")

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    expected = set(selected)
    saved: list[dict] = []
    with av.open(str(args.film)) as container:
        stream = container.streams.video[0]
        for frame_no, frame in enumerate(container.decode(stream)):
            if frame_no not in expected:
                continue
            image = frame.to_image().convert("RGB")
            if image.width > MAX_WIDTH:
                image = image.resize(
                    (MAX_WIDTH, round(image.height * MAX_WIDTH / image.width)),
                    Image.Resampling.LANCZOS,
                )
            reasons = sorted(selected[frame_no])
            path = args.out / f"f{frame_no:05d}_{_safe_reason(reasons[0])}.jpg"
            image.save(path, quality=JPEG_QUALITY, optimize=True)
            saved.append({
                "frame": frame_no,
                "seconds": round(frame_no / 30.0, 3),
                "reasons": reasons,
                "file": path.name,
                "width": image.width,
                "height": image.height,
            })
            expected.remove(frame_no)
            if not expected:
                break

    if expected:
        raise SystemExit(f"Could not decode requested evidence frames: {sorted(expected)}")

    manifest = {
        "film_sha256": audit.get("sha256"),
        "source_audit": str(args.audit),
        "selection_policy": (
            "start/middle/end of each temporal window; each face candidate; "
            "median hand-geometry event per affected shot"
        ),
        "max_width": MAX_WIDTH,
        "frames": saved,
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"EXPORTED {len(saved)} review candidate frames -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
