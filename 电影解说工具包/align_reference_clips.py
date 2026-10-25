#!/usr/bin/env python3
"""Transcribe a commentary source and align new narration beats to its scenes."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def normalize(text: str) -> str:
    text = text.lower()
    # Common Traditional -> Simplified forms seen in Chinese commentary transcripts.
    table = str.maketrans(
        "體這個來說時為會發現後裡與們從將開關學術實驗讓聽見過還對進氣網絡號頭畫聲應變動車門間離帶長萬達處經殺傷擊險難點總統區層歡緊張燒覺觀眾據隻識",
        "体这个来说时为会发现后里与们从将开关学术实验让听见过还对进气网络号头画声应变动车门间离带长万达处经杀伤击险难点总统区层欢紧张烧觉观众据只识",
    )
    text = text.translate(table)
    return re.sub(r"[^0-9a-z\u3400-\u9fff]", "", text)


def transcribe(source: Path, work: Path):
    transcript_path = work / "reference-transcript.json"
    if transcript_path.exists():
        return json.loads(transcript_path.read_text(encoding="utf-8"))
    print("Installing local speech recognition for commentary alignment...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "faster-whisper==1.2.1"],
        check=True,
    )
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
    raw_segments, info = model.transcribe(
        str(source), language="zh", beam_size=3, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350},
    )
    segments = [
        {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip()}
        for segment in raw_segments
        if segment.text.strip()
    ]
    transcript_path.write_text(
        json.dumps({"language": info.language, "segments": segments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Transcribed {len(segments)} commentary segments.", flush=True)
    return {"language": info.language, "segments": segments}


def group_matches(text: str, group) -> bool:
    return any(normalize(option) in text for option in group.split("|") if option)


def align_sections(source: Path, sections, work: Path, source_duration: float):
    transcript = transcribe(source, work)
    segments = transcript["segments"]
    normalized = [normalize(segment["text"]) for segment in segments]
    cursor = 0
    last_clip_end = 0.0
    alignment_rows = []

    all_cues = [(si, ci, cue) for si, section in enumerate(sections, 1) for ci, cue in enumerate(section["cues"], 1)]
    for order, (section_index, cue_index, cue) in enumerate(all_cues, 1):
        groups = [] if cue.get("fixed_sequence") else cue.get("keywords", [])
        if not groups:
            raise RuntimeError(
                f"Beat {order} has neither verified manual clips nor alignment keywords"
            )
        best = None
        # Keep the search monotonic and local; each event must follow the one before it.
        search_end = min(len(segments), cursor + 180)
        for index in range(cursor, search_end):
            window_text = "".join(normalized[index : min(len(segments), index + 4)])
            score = sum(1 for group in groups if group_matches(window_text, group))
            if best is None or score > best[0]:
                best = (score, index)
                if score == len(groups):
                    break
        if not best or best[0] == 0:
            raise RuntimeError(
                f"Beat {order} could not be matched safely after source segment {cursor}; "
                "refusing proportional fallback because it can pair unrelated footage"
            )
        score, index = best
        matched = segments[index]
        planned = max(4.2, len(cue["text"]) / 5.1)
        center = (matched["start"] + matched["end"]) / 2
        start = max(last_clip_end + 0.15, center - planned / 2)
        end = start + planned
        if end > source_duration:
            raise RuntimeError(f"Aligned clip exceeds source duration at beat {order}")
        cue["anchors"] = [round(center, 3)]
        cue["clips"] = [[round(start, 3), round(end, 3)]]
        cue["clip_texts"] = [cue["text"]]
        cue["planned_duration"] = round(planned, 3)
        last_clip_end = end
        cursor = min(len(segments) - 1, index + 1)
        alignment_rows.append(
            {
                "order": order,
                "section": section_index,
                "cue": cue_index,
                "score": score,
                "source_start": round(start, 3),
                "source_end": round(end, 3),
                "matched_transcript": matched["text"],
                "new_narration": cue["text"],
            }
        )
        print(
            f"Aligned {order}/{len(all_cues)} at {start:.1f}-{end:.1f}s "
            f"(score {score}/{len(groups)}): {matched['text']}",
            flush=True,
        )

    (work / "reference-alignment.json").write_text(
        json.dumps(alignment_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sections
