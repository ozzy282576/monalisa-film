#!/usr/bin/env python3
"""Exhaustive frame-level technical/temporal QC for the delivered rabies film.

This checks every decoded output frame (not the source contact sheets):
  * frame count, PTS cadence, full-frame luma/contrast and frozen runs;
  * within-shot frame-difference, optical-flow residuals, and abrupt luminance changes;
  * per-frame MediaPipe face/hand detections plus hand-landmark sanity telemetry.

The automated checks are triage, not proof that an image is semantically correct or
anatomically flawless. Review the generated shot-middle and hand-contact sheets and
all flagged full-resolution frames before marking visual review complete.

Usage:
  work/lamkorwan/qc-env/bin/python production/lamkorwan/audit_frame_distortions.py \
    --film '交付/雨夜屠夫林过云_一卷菲林里的四条人命_三分钟_带声音.mp4' \
    --project production/lamkorwan
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import av
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS_FALLBACK = 30.0
ANALYSIS_W, ANALYSIS_H = 320, 180
DETECT_W, DETECT_H = 640, 360
ROI_HEIGHT_FRACTION = 0.78  # omit subtitle/lower-third band from motion/warp metrics
FREEZE_DELTA = 0.15          # 64x36 mean absolute difference in 0-255 luma space
FREEZE_MIN_SECONDS = 1.0
FACE_SCORE_REVIEW = 0.75
FACE_WIDTH_REVIEW = 0.06
HAND_CONFIDENCE_REVIEW = 0.60


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _load_segments(project: Path) -> list[dict[str, Any]]:
    path = project / "delivery" / "edit-decision-list.json"
    if not path.is_file():
        raise FileNotFoundError(f"缺少 EDL：{path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows = sorted(rows, key=lambda x: (int(x["start_frame"]), int(x["end_frame"])))
    for row in rows:
        row["start_frame"] = int(row["start_frame"])
        row["end_frame"] = int(row["end_frame"])
    return rows


def _segment_index(segments: list[dict[str, Any]], total_frames: int) -> list[int]:
    out = [-1] * total_frames
    for seg_i, seg in enumerate(segments):
        a, b = max(0, seg["start_frame"]), min(total_frames, seg["end_frame"])
        for i in range(a, b):
            if out[i] != -1:
                raise ValueError(f"EDL 帧段重叠：frame={i}")
            out[i] = seg_i
    missing = [i for i, v in enumerate(out) if v == -1]
    if missing:
        raise ValueError(f"EDL 未覆盖 {len(missing)} 帧，首个缺口 frame={missing[0]}")
    return out


def _safe_mean_abs(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())


def _hand_row(landmarks: Any, handedness: Any) -> dict[str, Any]:
    pts = np.asarray([[p.x, p.y, p.z] for p in landmarks.landmark], dtype=np.float32)
    xy = pts[:, :2]
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    palm_w = float(np.linalg.norm(xy[5] - xy[17]))
    palm_h = float(np.linalg.norm(xy[0] - xy[9]))
    finger_pairs = ((5, 8), (9, 12), (13, 16), (17, 20))
    ratios = [float(np.linalg.norm(xy[t] - xy[m]) / max(palm_w, 1e-6))
              for m, t in finger_pairs]
    score = None
    label = None
    if handedness and handedness.classification:
        cls = handedness.classification[0]
        score, label = float(cls.score), str(cls.label)
    out_of_bounds = int(np.logical_or(xy < -0.15, xy > 1.15).any(axis=1).sum())
    extreme = [i for i, r in enumerate(ratios) if not math.isfinite(r) or r > 2.5 or r < 0.025]
    return {
        "score": round(score, 4) if score is not None else None,
        "label": label,
        "bbox": [round(float(lo[0]), 4), round(float(lo[1]), 4),
                 round(float(hi[0] - lo[0]), 4), round(float(hi[1] - lo[1]), 4)],
        "palm_wh_ratio": round(palm_w / max(palm_h, 1e-6), 4),
        "finger_length_to_palm_width": [round(x, 4) for x in ratios],
        "out_of_bounds_landmarks": out_of_bounds,
        "extreme_finger_ratios": extreme,
    }


def _face_rows(result: Any) -> list[dict[str, Any]]:
    out = []
    for det in result.detections or []:
        box = det.location_data.relative_bounding_box
        out.append({
            "score": round(float(det.score[0]), 4),
            "bbox": [round(float(box.xmin), 4), round(float(box.ymin), 4),
                     round(float(box.width), 4), round(float(box.height), 4)],
        })
    return out


def _robust_threshold(values: list[float], floor: float, mad_multiple: float = 5.0) -> tuple[float, float, float]:
    if not values:
        return floor, 0.0, 0.0
    med = float(statistics.median(values))
    mad = float(statistics.median(abs(v - med) for v in values))
    return max(floor, med + mad_multiple * 1.4826 * mad), med, mad


def _compose_contact(items: list[tuple[str, Image.Image]], path: Path, columns: int,
                     cell_w: int, cell_h: int, label_height: int = 32) -> None:
    rows = int(math.ceil(len(items) / columns))
    sheet = Image.new("RGB", (columns * cell_w, rows * (cell_h + label_height)), "#111318")
    draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(items):
        im = im.convert("RGB").resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        x, y = (i % columns) * cell_w, (i // columns) * (cell_h + label_height)
        sheet.paste(im, (x, y))
        draw.text((x + 8, y + cell_h + 5), label, fill="#f5f5f5")
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=92)


def _run_length_events(rows: list[dict[str, Any]], fps: float, min_seconds: float,
                       key: str = "freeze_delta") -> list[dict[str, Any]]:
    limit = max(1, int(round(fps * min_seconds)))
    runs, start = [], None
    for i, row in enumerate(rows):
        is_low = row.get(key) is not None and row[key] < FREEZE_DELTA
        same_shot = i > 0 and row.get("shot") == rows[i - 1].get("shot")
        if is_low and (start is None or same_shot):
            if start is None:
                start = i
        else:
            if start is not None and i - start >= limit:
                runs.append((start, i - 1))
            start = i if is_low else None
    if start is not None and len(rows) - start >= limit:
        runs.append((start, len(rows) - 1))
    out = []
    for a, b in runs:
        out.append({
            "start_frame": a,
            "end_frame": b,
            "start_seconds": round(a / fps, 3),
            "end_seconds": round((b + 1) / fps, 3),
            "duration_seconds": round((b - a + 1) / fps, 3),
            "shot": rows[a].get("shot"),
            "kind": rows[a].get("kind"),
            "median_frame_delta": round(float(statistics.median(
                r[key] for r in rows[a:b + 1] if r.get(key) is not None)), 4),
        })
    return out


def _select_outliers(rows: list[dict[str, Any]], segments: list[dict[str, Any]],
                     frame_to_seg: list[int], fps: float) -> list[dict[str, Any]]:
    by_seg: dict[int, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        by_seg[frame_to_seg[i]].append(i)
    events = []
    metric_cfg = {
        "pair_diff": (4.0, "frame_difference_spike"),
        "flow_residual_p95": (2.5, "local_motion_residual_spike"),
        "flow_p95": (4.0, "optical_flow_spike"),
    }
    for seg_i, indices in by_seg.items():
        seg = segments[seg_i]
        # Ignore the first/last two frames of a planned cut/fade when fitting the baseline.
        usable = indices[2:-2] if len(indices) > 8 else indices
        for metric, (floor, flag) in metric_cfg.items():
            vals = [float(rows[i][metric]) for i in usable if rows[i].get(metric) is not None]
            threshold, med, mad = _robust_threshold(vals, floor)
            for i in usable:
                value = rows[i].get(metric)
                if value is not None and float(value) > threshold:
                    events.append({
                        "frame": i,
                        "seconds": round(i / fps, 3),
                        "shot": seg["id"],
                        "kind": seg["kind"],
                        "flag": flag,
                        "metric": metric,
                        "value": round(float(value), 4),
                        "threshold": round(threshold, 4),
                        "shot_median": round(med, 4),
                        "shot_mad": round(mad, 4),
                    })
        # A one-frame exposure/colour flash is measured independently of optical flow.
        jumps = [abs(float(rows[i]["luma_step"])) for i in usable
                 if rows[i].get("luma_step") is not None]
        jump_threshold, jump_med, jump_mad = _robust_threshold(jumps, 8.0)
        for i in usable:
            value = rows[i].get("luma_step")
            if value is not None and abs(float(value)) > jump_threshold:
                events.append({
                    "frame": i,
                    "seconds": round(i / fps, 3),
                    "shot": seg["id"],
                    "kind": seg["kind"],
                    "flag": "abrupt_luma_change",
                    "metric": "abs_luma_step",
                    "value": round(abs(float(value)), 4),
                    "threshold": round(jump_threshold, 4),
                    "shot_median": round(jump_med, 4),
                    "shot_mad": round(jump_mad, 4),
                })
    # Merge the flags at a frame; then consolidate nearby consecutive flags into review windows.
    per_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        per_frame[event["frame"]].append(event)
    frames = sorted(per_frame)
    groups: list[list[int]] = []
    for frame_i in frames:
        if (not groups or frame_i > groups[-1][-1] + 3 or
                rows[groups[-1][-1]]["shot"] != rows[frame_i]["shot"]):
            groups.append([frame_i])
        else:
            groups[-1].append(frame_i)
    merged = []
    for group in groups:
        entries = [e for idx in group for e in per_frame[idx]]
        merged.append({
            "start_frame": group[0],
            "end_frame": group[-1],
            "start_seconds": round(group[0] / fps, 3),
            "end_seconds": round((group[-1] + 1) / fps, 3),
            "shot": rows[group[0]].get("shot"),
            "flags": sorted({e["flag"] for e in entries}),
            "peak_values": {metric: round(max(e["value"] for e in entries if e["metric"] == metric), 4)
                            for metric in sorted({e["metric"] for e in entries})},
            "flagged_frame_count": len(group),
            "details": entries,
        })
    return merged


def _extract_suspects(film: Path, indices: set[int], out_dir: Path, max_images: int = 80) -> list[str]:
    if not indices:
        return []
    # Include immediate neighbours so a reviewer can see whether a flagged frame is a one-frame glitch.
    chosen = set()
    for i in indices:
        for j in range(max(0, i - 2), i + 3):
            chosen.add(j)
    selected = sorted(chosen)[:max_images]
    container = av.open(str(film))
    stream = container.streams.video[0]
    saved = []
    try:
        wanted = set(selected)
        for i, frame in enumerate(container.decode(stream)):
            if i in wanted:
                image = frame.to_image()
                path = out_dir / f"frame_{i:05d}_t{i/30:07.3f}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path, quality=95)
                saved.append(str(path))
            if i > max(selected):
                break
    finally:
        container.close()
    return saved


def run_audit(film: Path, project: Path, out_dir: Path, progress_every: int = 300) -> dict[str, Any]:
    segments = _load_segments(project)
    if not film.is_file():
        raise FileNotFoundError(f"找不到成片：{film}")
    container = av.open(str(film))
    stream = container.streams.video[0]
    fps = float(stream.average_rate or FPS_FALLBACK)
    expected = int(stream.frames or round(float(container.duration * av.time_base) * fps))
    if expected <= 0:
        expected = round(float(container.duration * av.time_base) * fps)
    total = expected
    frame_to_seg = _segment_index(segments, total)
    time_base = float(stream.time_base)
    expected_pts_step = int(round((1.0 / fps) / time_base)) if time_base else None
    rows: list[dict[str, Any]] = []
    pts_issues: list[dict[str, Any]] = []
    shot_middles: list[tuple[str, Image.Image]] = []
    handsamples: dict[str, list[tuple[str, Image.Image]]] = defaultdict(list)
    shot_hand_counts: dict[str, int] = defaultdict(int)
    shot_face_counts: dict[str, int] = defaultdict(int)
    hand_geom_events: list[dict[str, Any]] = []
    face_candidates: list[dict[str, Any]] = []
    hand_detection_candidates: list[dict[str, Any]] = []
    prev_gray: np.ndarray | None = None
    prev_small_sig: np.ndarray | None = None
    prev_pts: int | None = None
    started = time.time()
    decoded = 0
    active_seg = -1
    face_detector = None
    hand_detector = None
    failure = None

    try:
        for frame_i, frame in enumerate(container.decode(stream)):
            decoded += 1
            if frame_i >= total:
                pts_issues.append({"frame": frame_i, "issue": "extra_decoded_frame"})
                continue
            seg_i = frame_to_seg[frame_i]
            seg = segments[seg_i]
            if seg_i != active_seg:
                if face_detector is not None:
                    face_detector.close()
                    hand_detector.close()
                face_detector = mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=0.45)
                hand_detector = mp.solutions.hands.Hands(
                    static_image_mode=False, max_num_hands=4, model_complexity=0,
                    min_detection_confidence=0.45, min_tracking_confidence=0.4)
                active_seg = seg_i
                prev_gray = None
                prev_small_sig = None

            # All frames are decoded at native stream resolution; analysis views are reduced to
            # 320x180 / 640x360 for repeatable computer-vision measurements.
            rgb = frame.reformat(width=DETECT_W, height=DETECT_H, format="rgb24").to_ndarray()
            rgb = np.ascontiguousarray(rgb)
            gray640 = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            gray = cv2.resize(gray640, (ANALYSIS_W, ANALYSIS_H), interpolation=cv2.INTER_AREA)
            roi = gray[:int(ANALYSIS_H * ROI_HEIGHT_FRACTION), :]
            luma = float(gray.mean())
            contrast = float(gray.std())
            black_fraction = float((gray < 12).mean())
            sharpness = float(cv2.Laplacian(gray, cv2.CV_32F).var())
            sig = cv2.resize(roi, (64, 36), interpolation=cv2.INTER_AREA)
            freeze_delta = None if prev_small_sig is None else _safe_mean_abs(sig, prev_small_sig)
            pair_diff = changed_fraction = flow_median = flow_p95 = flow_resid_p95 = None
            luma_step = None
            if prev_gray is not None:
                prev_roi = prev_gray[:int(ANALYSIS_H * ROI_HEIGHT_FRACTION), :]
                diff = cv2.absdiff(roi, prev_roi)
                pair_diff = float(diff.mean())
                changed_fraction = float((diff > 8).mean())
                luma_step = luma - rows[-1]["luma"]
                flow = cv2.calcOpticalFlowFarneback(
                    prev_roi, roi, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mag = cv2.magnitude(flow[..., 0], flow[..., 1])
                flow_median = float(np.median(mag))
                flow_p95 = float(np.percentile(mag, 95))
                dx = float(np.median(flow[..., 0]))
                dy = float(np.median(flow[..., 1]))
                resid = cv2.magnitude(flow[..., 0] - dx, flow[..., 1] - dy)
                flow_resid_p95 = float(np.percentile(resid, 95))

            # Both detectors run on every output frame; they are triage signals, not a guarantee
            # that MediaPipe can recognize every deformed/occluded face or hand.
            face_result = face_detector.process(rgb)
            face_rows = _face_rows(face_result)
            hand_result = hand_detector.process(rgb)
            hand_rows = [_hand_row(lm, handed)
                         for lm, handed in zip(hand_result.multi_hand_landmarks or [],
                                               hand_result.multi_handedness or [])]
            sid = str(seg["id"])
            shot_hand_counts[sid] += len(hand_rows)
            shot_face_counts[sid] += len(face_rows)
            for face in face_rows:
                if face["score"] >= FACE_SCORE_REVIEW and face["bbox"][2] >= FACE_WIDTH_REVIEW:
                    face_candidates.append({"frame": frame_i, "seconds": round(frame_i / fps, 3),
                                            "shot": sid, **face})
            for hand_no, hand in enumerate(hand_rows):
                if hand["score"] is not None and hand["score"] >= HAND_CONFIDENCE_REVIEW:
                    hand_detection_candidates.append({"frame": frame_i, "seconds": round(frame_i / fps, 3),
                                                      "shot": sid, "hand": hand_no, **hand})
                if hand["extreme_finger_ratios"] or hand["out_of_bounds_landmarks"]:
                    hand_geom_events.append({"frame": frame_i, "seconds": round(frame_i / fps, 3),
                                             "shot": sid, "hand": hand_no, **hand})
            if frame.pts is not None and prev_pts is not None and expected_pts_step is not None:
                pts_step = int(frame.pts - prev_pts)
                if pts_step != expected_pts_step:
                    pts_issues.append({"frame": frame_i, "seconds": round(frame_i / fps, 4),
                                       "pts_step": pts_step, "expected_pts_step": expected_pts_step})
            prev_pts = frame.pts

            row = {
                "frame": frame_i,
                "seconds": round(frame_i / fps, 4),
                "pts": int(frame.pts) if frame.pts is not None else None,
                "shot": sid,
                "kind": seg["kind"],
                "luma": round(luma, 4),
                "contrast": round(contrast, 4),
                "black_fraction_luma_lt12": round(black_fraction, 6),
                "laplacian_variance": round(sharpness, 5),
                "freeze_delta": round(freeze_delta, 6) if freeze_delta is not None else None,
                "pair_diff": round(pair_diff, 6) if pair_diff is not None else None,
                "changed_fraction_gt8": round(changed_fraction, 6) if changed_fraction is not None else None,
                "luma_step": round(luma_step, 6) if luma_step is not None else None,
                "flow_median": round(flow_median, 6) if flow_median is not None else None,
                "flow_p95": round(flow_p95, 6) if flow_p95 is not None else None,
                "flow_residual_p95": round(flow_resid_p95, 6) if flow_resid_p95 is not None else None,
                "face_count": len(face_rows),
                "faces": face_rows,
                "hand_count": len(hand_rows),
                "hands": hand_rows,
            }
            rows.append(row)

            # One exact final-frame midpoint per EDL segment for a visual semantic/continuity pass.
            midpoint = (seg["start_frame"] + seg["end_frame"] - 1) // 2
            if frame_i == midpoint:
                thumb = Image.fromarray(rgb).resize((480, 270), Image.Resampling.LANCZOS)
                shot_middles.append((f"{sid}  t={frame_i/fps:.2f}s  {seg['kind']}", thumb))
            # Dense visual sampling only where a hand detector sees a hand (4 fps/shot), in
            # addition to the numerical analysis above on every frame.
            if hand_rows and (frame_i - seg["start_frame"]) % max(1, round(fps / 4)) == 0:
                thumb = Image.fromarray(rgb).resize((480, 270), Image.Resampling.LANCZOS)
                handsamples[sid].append((f"{sid}  t={frame_i/fps:.2f}s  hands={len(hand_rows)}", thumb))

            prev_gray = gray
            prev_small_sig = sig
            if progress_every and (frame_i + 1) % progress_every == 0:
                elapsed = time.time() - started
                rate = (frame_i + 1) / max(elapsed, 1e-9)
                print(f"  decoded + scanned {frame_i + 1}/{total} frames ({rate:.1f} fps)",
                      flush=True)
    except Exception as e:
        failure = f"{type(e).__name__}: {e}"
        raise
    finally:
        if face_detector is not None:
            face_detector.close()
        if hand_detector is not None:
            hand_detector.close()
        container.close()

    if decoded != total:
        pts_issues.append({"frame": decoded, "issue": "decoded_frame_count_mismatch",
                           "expected": total, "decoded": decoded})
    segments_by_id = {str(x["id"]): x for x in segments}
    outliers = _select_outliers(rows, segments, frame_to_seg, fps)
    freeze_runs = _run_length_events(rows, fps, FREEZE_MIN_SECONDS)
    non_graphic_freezes = [x for x in freeze_runs if x["kind"] == "agnes"]
    black_frames = [r for r in rows if r["luma"] < 12.0]
    unplanned_black = [r for r in black_frames
                       if not (r["shot"] == "END" or r["seconds"] < 0.10)]

    shot_summary = []
    for seg in segments:
        sid = str(seg["id"])
        selected = [r for r in rows if r["shot"] == sid]
        valid_flows = [r["flow_residual_p95"] for r in selected if r["flow_residual_p95"] is not None]
        shot_events = [e for e in outliers if e["shot"] == sid]
        shot_summary.append({
            "id": sid, "kind": seg["kind"],
            "start_frame": seg["start_frame"], "end_frame": seg["end_frame"],
            "start_seconds": round(seg["start_frame"] / fps, 3),
            "end_seconds": round(seg["end_frame"] / fps, 3),
            "frames_checked": len(selected),
            "purpose": seg.get("purpose", ""),
            "face_detections": shot_face_counts[sid],
            "hand_detections": shot_hand_counts[sid],
            "max_flow_residual_p95": round(max(valid_flows), 4) if valid_flows else None,
            "outlier_windows": len(shot_events),
        })

    # Full-resolution exact-frame extraction for flagged temporal events (neighbour frames included).
    suspect_indices = {i for event in outliers for i in range(event["start_frame"], event["end_frame"] + 1)}
    suspect_indices.update(int(x["frame"]) for x in face_candidates)
    suspect_indices.update(int(x["frame"]) for x in hand_geom_events)
    # Limit only image export, never the analysis; full per-frame metrics remain in the report.
    if len(suspect_indices) > 40:
        priority = sorted(suspect_indices, key=lambda i: (
            0 if any(e["start_frame"] <= i <= e["end_frame"] for e in outliers) else 1, i))
        suspect_indices = set(priority[:40])
    image_dir = out_dir / "suspect-frames"
    saved_suspects = _extract_suspects(film, suspect_indices, image_dir, max_images=120)

    contact_dir = out_dir / "contacts"
    if shot_middles:
        _compose_contact(shot_middles, contact_dir / "shot-midpoints.jpg", columns=4,
                         cell_w=480, cell_h=270, label_height=32)
    hand_sheets = []
    for sid, samples in sorted(handsamples.items()):
        if samples:
            sheet_path = contact_dir / f"hands-{sid}.jpg"
            _compose_contact(samples, sheet_path, columns=4, cell_w=480, cell_h=270,
                             label_height=32)
            hand_sheets.append(str(sheet_path))

    # Per-frame CSV is the audit trail; JSON also preserves boxes and landmark metrics.
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "frame-metrics.csv"
    fields = ["frame", "seconds", "pts", "shot", "kind", "luma", "contrast",
              "black_fraction_luma_lt12", "laplacian_variance", "freeze_delta", "pair_diff",
              "changed_fraction_gt8", "luma_step", "flow_median", "flow_p95",
              "flow_residual_p95", "face_count", "hand_count"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})

    status = ("PASS" if not pts_issues and not unplanned_black and not non_graphic_freezes
              and not outliers and not face_candidates and not hand_geom_events else "REVIEW")
    return {
        "film": str(film),
        "sha256": _sha256(film),
        "video": {
            "codec": stream.codec_context.name, "width": stream.width, "height": stream.height,
            "fps": fps, "expected_frames": expected, "decoded_frames": decoded,
            "duration_seconds": round(decoded / fps, 4),
            "analysis_resolution": f"{ANALYSIS_W}x{ANALYSIS_H}",
            "detector_resolution": f"{DETECT_W}x{DETECT_H}",
            "all_decoded_frames_scanned": decoded == expected,
        },
        "status": status,
        "checks": {
            "pts_issues": pts_issues,
            "black_frame_count_luma_lt12": len(black_frames),
            "unplanned_black_frame_count": len(unplanned_black),
            "unplanned_black_frames": [
                {"frame": r["frame"], "seconds": r["seconds"], "shot": r["shot"], "luma": r["luma"]}
                for r in unplanned_black
            ],
            "freeze_threshold": FREEZE_DELTA,
            "freeze_runs_over_1s": freeze_runs,
            "non_graphic_freeze_runs": non_graphic_freezes,
            "temporal_outlier_windows": outliers,
            "face_detections_total": sum(shot_face_counts.values()),
            "face_review_candidates": face_candidates,
            "hand_detections_total": sum(shot_hand_counts.values()),
            "hand_detection_candidates": hand_detection_candidates,
            "hand_landmark_extreme_events": hand_geom_events,
        },
        "shot_summary": shot_summary,
        "visual_artifacts": {
            "shot_midpoint_contact_sheet": str(contact_dir / "shot-midpoints.jpg"),
            "hand_contact_sheets": hand_sheets,
            "suspect_frame_images": saved_suspects,
            "per_frame_csv": str(csv_path),
        },
        "all_frames": rows,
        "method_notes": [
            "每个输出帧均被解码；固定在 EDL 场景内比较，镜头切点两帧不参与跳变基线。",
            "光流与帧差在 320x180、画面上方 78% 计算，以降低字幕和压缩噪声影响；人脸/手模型逐帧在 640x360 运行。",
            "阈值命中只代表需要复核，不等于畸变；模型无法证明手指数量、语义正确、构图或所有微小缺陷。",
            "图像语义和人体解剖仍须查看 shot-midpoints.jpg、逐帧异常邻帧和手部接触表；不要用 PASS 代替人工看片。",
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    c = report["checks"]
    v = report["video"]
    lines = [
        "# 成片逐帧畸变 / 时序 QC",
        "",
        f"- 成片：`{Path(report['film']).name}`",
        f"- SHA-256：`{report['sha256']}`",
        f"- 视频：{v['width']}×{v['height']} / {v['fps']:.3f} fps / {v['duration_seconds']:.3f} 秒",
        f"- 覆盖：解码并分析 **{v['decoded_frames']}/{v['expected_frames']} 帧**；逐帧 MediaPipe 人脸/手检测；{v['analysis_resolution']} 时序分析",
        f"- 自动状态：**{report['status']}**（机器结果，不等同于无任何视觉瑕疵）",
        "",
        "## 全片结果",
        "",
        f"- PTS 连续性异常：{len(c['pts_issues'])}",
        f"- 亮度低于 12 的帧：{c['black_frame_count_luma_lt12']}（片头/片尾淡入淡出需按时间线解释）",
        f"- 非计划黑帧：{c['unplanned_black_frame_count']}",
        f"- >1 秒近静止区段：{len(c['freeze_runs_over_1s'])}；其中非信息卡/片尾段：{len(c['non_graphic_freeze_runs'])}",
        f"- 帧差/光流/亮度突变待复核窗口：{len(c['temporal_outlier_windows'])}",
        f"- 人脸检测：逐帧总检测 {c['face_detections_total']}；达到复核阈值的候选 {len(c['face_review_candidates'])}",
        f"- 手部检测：逐帧总检测 {c['hand_detections_total']}；超出宽松几何边界的 landmark 事件 {len(c['hand_landmark_extreme_events'])}",
        "",
        "## 镜头统计",
        "",
        "| 镜头 | 类型 | 帧数 | 人脸检出 | 手检出 | 光流残差 P95 峰值 | 时序异常窗口 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["shot_summary"]:
        lines.append(f"| {row['id']} | {row['kind']} | {row['frames_checked']} | {row['face_detections']} | "
                     f"{row['hand_detections']} | {row['max_flow_residual_p95']} | {row['outlier_windows']} |")
    lines += [
        "",
        "## 复核文件",
        "",
        f"- 全 45 镜 + 片尾画面中帧：`{report['visual_artifacts']['shot_midpoint_contact_sheet']}`",
        f"- 逐帧指标 CSV：`{report['visual_artifacts']['per_frame_csv']}`",
        f"- 候选异常原始分辨率帧：`{report['visual_artifacts']['suspect_frame_images']}`",
    ]
    for name in report["visual_artifacts"]["hand_contact_sheets"]:
        lines.append(f"- 手部动态接触表：`{name}`")
    lines += [
        "",
        "## 限制",
        "",
        "自动检测会漏检遮挡、极小目标和模型本身识别不到的 AI 畸变；时序异常也可能是有意运镜、火焰、蒸汽或字幕变化。"
        "所以候选必须看原始分辨率前后帧，语义与解剖必须人工目检。没有候选不等于数学上证明‘完美无瑕疵’。",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--film", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--out", type=Path, default=None,
                        help="默认 production/lamkorwan/delivery/frame-distortion-audit.json")
    parser.add_argument("--work", type=Path, default=Path("work/lamkorwan/frame_distortion_audit"))
    parser.add_argument("--progress-every", type=int, default=300)
    args = parser.parse_args()
    out_json = args.out or args.project / "delivery" / "frame-distortion-audit.json"
    started = time.time()
    print(f"开始逐帧检查：{args.film}", flush=True)
    report = run_audit(args.film, args.project, args.work, args.progress_every)
    report["elapsed_seconds"] = round(time.time() - started, 2)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path = out_json.with_suffix(".md")
    write_markdown(report, md_path)
    c, v = report["checks"], report["video"]
    print(f"\n完成：{v['decoded_frames']}/{v['expected_frames']} 帧，{v['duration_seconds']:.3f}s")
    print(f"  PTS 异常 {len(c['pts_issues'])}；非计划黑帧 {c['unplanned_black_frame_count']}；"
          f"非图卡冻结段 {len(c['non_graphic_freeze_runs'])}")
    print(f"  时序异常候选 {len(c['temporal_outlier_windows'])}；人脸候选 {len(c['face_review_candidates'])}；"
          f"手部几何边界事件 {len(c['hand_landmark_extreme_events'])}")
    print(f"  逐帧 CSV：{report['visual_artifacts']['per_frame_csv']}")
    print(f"  报告：{out_json}\n  复核版：{md_path}\n  中帧表：{report['visual_artifacts']['shot_midpoint_contact_sheet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
