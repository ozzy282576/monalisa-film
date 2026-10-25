#!/usr/bin/env python3
"""Render every decoded final-video frame into ordered per-shot contact sheets.

This is a visual companion to audit_frame_distortions.py: it does not sample the
video. Every frame is included once, in presentation order, with its frame number.
Use 160x90 thumbnails to scan the full timeline, then inspect flagged frames at
native resolution with the frame-audit's suspect-frame exports.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import av
from PIL import Image, ImageDraw

CELL_W, CELL_H = 160, 90
LABEL_H = 22
COLS = 12
BG = (17, 19, 24)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", type=Path, required=True)
    ap.add_argument("--project", type=Path, default=Path("production/rabies1885"))
    ap.add_argument("--out", type=Path, default=Path("work/rabies1885/all-frame-sheets"))
    args = ap.parse_args()
    edl_path = args.project / "delivery" / "edit-decision-list.json"
    segments = json.loads(edl_path.read_text(encoding="utf-8"))
    segments.sort(key=lambda r: (int(r["start_frame"]), int(r["end_frame"])))
    for row in segments:
        row["start_frame"], row["end_frame"] = int(row["start_frame"]), int(row["end_frame"])
    if not segments or segments[0]["start_frame"] != 0:
        raise SystemExit("EDL must start at frame 0")
    for a, b in zip(segments, segments[1:]):
        if a["end_frame"] != b["start_frame"]:
            raise SystemExit(f"EDL gap/overlap between {a['id']} and {b['id']}")

    args.out.mkdir(parents=True, exist_ok=True)
    stream = None
    frames_total = 0
    saved = []
    with av.open(str(args.film)) as container:
        stream = next(s for s in container.streams if s.type == "video")
        seg_i = 0
        thumbs: list[tuple[int, Image.Image]] = []

        def save_segment(seg, items):
            if not items:
                raise RuntimeError(f"No decoded frames for {seg['id']}")
            rows = (len(items) + COLS - 1) // COLS
            sheet = Image.new("RGB", (COLS * CELL_W, rows * (CELL_H + LABEL_H)), BG)
            draw = ImageDraw.Draw(sheet)
            for i, (frame_no, image) in enumerate(items):
                x = (i % COLS) * CELL_W
                y = (i // COLS) * (CELL_H + LABEL_H)
                image = image.convert("RGB").resize((CELL_W, CELL_H), Image.Resampling.LANCZOS)
                sheet.paste(image, (x, y))
                draw.text((x + 4, y + CELL_H + 3), f"f{frame_no:05d}", fill=(245, 245, 245))
            path = args.out / f"{seg['id']}-all-frames.jpg"
            sheet.save(path, quality=82, optimize=True)
            saved.append({"shot": seg["id"], "kind": seg.get("kind"),
                          "start_frame": seg["start_frame"], "end_frame": seg["end_frame"],
                          "frames_in_sheet": len(items), "file": str(path)})
            print(f"SAVED {seg['id']} {len(items)} frames -> {path}", flush=True)

        for frame_no, frame in enumerate(container.decode(stream)):
            while seg_i < len(segments) and frame_no >= segments[seg_i]["end_frame"]:
                save_segment(segments[seg_i], thumbs)
                thumbs = []
                seg_i += 1
            if seg_i >= len(segments):
                raise RuntimeError(f"Decoded extra frame {frame_no} beyond EDL")
            seg = segments[seg_i]
            if frame_no < seg["start_frame"]:
                raise RuntimeError(f"EDL gap before frame {frame_no}")
            thumb = frame.to_image().convert("RGB")
            thumb.thumbnail((CELL_W, CELL_H), Image.Resampling.LANCZOS)
            thumbs.append((frame_no, thumb))
            frames_total += 1
        if seg_i < len(segments):
            save_segment(segments[seg_i], thumbs)
            thumbs = []
            seg_i += 1
            while seg_i < len(segments):
                raise RuntimeError(f"EDL segment {segments[seg_i]['id']} has no decoded frames")
    if frames_total != segments[-1]["end_frame"]:
        raise RuntimeError(f"Decoded {frames_total} frames, EDL expects {segments[-1]['end_frame']}")
    manifest_path = args.out / "manifest.json"
    manifest = {"film": str(args.film), "frames_included": frames_total,
                "sampling": "none; every decoded frame exactly once",
                "cell_size": f"{CELL_W}x{CELL_H}", "sheets": saved}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    # Attach the atlas to the machine report so reviewers can reach all-frame evidence
    # from one place. This explicitly remains pending until a person reviews it.
    report_path = args.project / "delivery" / "frame-distortion-audit.json"
    markdown_path = report_path.with_suffix(".md")
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report.setdefault("visual_artifacts", {})["all_frame_contact_sheets"] = [x["file"] for x in saved]
        report["visual_artifacts"]["all_frame_contact_sheet_manifest"] = str(manifest_path)
        report["visual_review_status"] = "pending"
        report.setdefault("method_notes", []).append(
            "全帧可视接触表包含每个解码帧一次（无抽样），每格为 160x90 缩略图；它用于全片扫查，"
            "不能代替异常帧原始分辨率复核，也不代表人工审核已完成。")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if markdown_path.is_file():
            lines = [
                "", "## 全部输出帧的视觉接触表", "",
                f"全片 {frames_total} 帧按时间顺序逐帧收录、没有抽样；{len(saved)} 张分镜头接触表，"
                f"每格 {CELL_W}×{CELL_H} 像素。缩略图用于扫查，异常仍须查看原始分辨率。",
                "", f"- 清单：`../qa/final-frame-review/all-frames/manifest.json`", "",
            ]
            lines.extend(f"- [{item['shot']}](../qa/final-frame-review/all-frames/{Path(item['file']).name})"
                         for item in saved)
            lines += ["", "人工逐帧视觉复核状态：**PENDING**。自动结果或缩略接触表都不等于无瑕疵。", ""]
            with markdown_path.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines))
    print(f"COMPLETE {frames_total} frames in {len(saved)} ordered sheets", flush=True)

if __name__ == "__main__":
    main()
