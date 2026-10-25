#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

import edge_tts

VOICE = "zh-CN-YunjianNeural"
VOICE_RATE = "+5%"
VOICE_PITCH = "-8Hz"
MOVIE_VOLUME = 0.0
BGM_VOLUME = 0.05
BGM_LOOP_SECONDS = 96.0
SINGLE_LINE_SUBTITLE_CHARS = 24


def run(command):
    print("+", " ".join(map(str, command[:12])), "..." if len(command) > 12 else "", flush=True)
    subprocess.run([str(value) for value in command], check=True)


def media_duration(path: Path) -> float:
    output = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    )
    return float(output.strip())


def parse_scenes(path: Path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = next(index for index, line in enumerate(lines) if line.startswith("Scene Number,"))
    return [
        (float(row["Start Time (seconds)"]), float(row["End Time (seconds)"]))
        for row in csv.DictReader(lines[header:])
    ]


def measure_reference_rhythm(reference: Path, work: Path) -> float:
    fallback = 3.7
    if not reference.exists():
        print("Reference video unavailable; using 3.7-second measured fallback rhythm.")
        return fallback
    output_dir = work / "reference_scan"
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_file = output_dir / "reference-scenes.csv"
    try:
        run(
            [
                "scenedetect",
                "-q",
                "-i",
                reference,
                "-o",
                output_dir,
                "detect-content",
                "-t",
                "27",
                "list-scenes",
                "-f",
                scene_file.name,
            ]
        )
        scenes = parse_scenes(scene_file)
        lengths = [b - a for a, b in scenes if 0.6 <= b - a <= 15]
        measured = statistics.fmean(lengths)
        rhythm = max(2.8, min(4.2, measured))
        print(
            f"Reference scan: {len(scenes)} shots, mean usable shot {measured:.2f}s; "
            f"target rhythm {rhythm:.2f}s",
            flush=True,
        )
        return rhythm
    except Exception as exc:
        print(f"Reference scan failed ({exc}); using {fallback:.1f}s fallback.")
        return fallback


def visible_length(text: str) -> int:
    return len(re.sub(r"[^\u3400-\u9fffA-Za-z0-9]", "", text))


def split_caption_clauses(text: str):
    """Split at every spoken punctuation mark for short, single-line captions."""
    clauses = [
        part.strip()
        for part in re.findall(r"[^，。！？；：]+[，。！？；：]?", text)
        if part.strip()
    ]
    return clauses or [text]


def format_single_line_caption(text: str):
    """Keep one clause on one line, shrinking only exceptionally long clauses."""
    length = max(1, visible_length(text))
    if length > SINGLE_LINE_SUBTITLE_CHARS:
        font_size = max(34, min(42, int(1120 / length)))
        return f"[[SINGLE:{font_size}]]{text}"
    return "[[SINGLE:42]]" + text


def cue_subtitle_timeline(cues, cue_durations):
    timeline = []
    cursor = 0.0
    for cue, duration in zip(cues, cue_durations):
        clauses = split_caption_clauses(cue["text"])
        weights = [max(3, visible_length(clause)) + 1.0 for clause in clauses]
        scale = duration / sum(weights)
        clause_start = cursor
        for index, (clause, weight) in enumerate(zip(clauses, weights)):
            clause_end = cursor + duration if index == len(clauses) - 1 else clause_start + weight * scale
            timeline.append(
                (clause_start, clause_end, format_single_line_caption(clause))
            )
            clause_start = clause_end
        cursor += duration
    return timeline


def ass_time(seconds):
    hours = int(seconds // 3600)
    seconds -= hours * 3600
    minutes = int(seconds // 60)
    seconds -= minutes * 60
    return f"{hours}:{minutes:02d}:{seconds:05.2f}"


def write_ass(path: Path, timeline):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narration,Noto Sans CJK SC,42,&H00FFFFFF,&H000000FF,&H00101010,&H78000000,1,0,0,0,100,100,0,0,1,2.8,0,2,40,40,18,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for start, end, text in timeline:
        size_match = re.match(r"^\[\[SINGLE:(\d+)\]\]", text)
        font_size = size_match.group(1) if size_match else "42"
        if size_match:
            text = text[size_match.end() :]
        text = text.replace("\\", "\\\\").replace("{", "（").replace("}", "）").replace("\n", "")
        # \q2 disables wrapping. Each event is one punctuation-delimited clause.
        text = rf"{{\q2\fs{font_size}}}" + text
        rows.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Narration,,0,0,0,,{text}")
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def subtract_used(start, end, used, padding=0.35):
    segments = [(start, end)]
    for used_start, used_end in sorted(used):
        blocked_start = used_start - padding
        blocked_end = used_end + padding
        revised = []
        for a, b in segments:
            if blocked_end <= a or blocked_start >= b:
                revised.append((a, b))
                continue
            if blocked_start > a:
                revised.append((a, min(b, blocked_start)))
            if blocked_end < b:
                revised.append((max(a, blocked_end), b))
        segments = revised
    return [(a, b) for a, b in segments if b - a >= 0.25]


def pick_shots(scenes, start, end, target, used, anchor, shot_duration):
    candidates = []
    for scene_start, scene_end in scenes:
        a, b = max(scene_start, start), min(scene_end, end)
        if b - a < 0.9:
            continue
        candidates.extend(
            (free_start, free_end)
            for free_start, free_end in subtract_used(a, b, used)
            if free_end - free_start >= 0.9
        )
    if not candidates:
        candidates = [
            segment
            for segment in subtract_used(start, end, used)
            if segment[1] - segment[0] >= 0.4
        ]
    if not candidates:
        raise RuntimeError(f"No unused source footage remains inside cue range {start}-{end}")

    # Choose real shots closest to the exact subtitle/event anchor. This avoids
    # sampling unrelated establishing shots from elsewhere in the same scene.
    ranked = sorted(
        candidates,
        key=lambda item: (abs((item[0] + item[1]) / 2 - anchor), item[0]),
    )
    count = max(1, math.ceil(target / shot_duration))
    while True:
        selected = sorted(ranked[:count], key=lambda item: item[0])
        caps = [min(shot_duration * 1.25, b - a - 0.03) for a, b in selected]
        if sum(caps) >= target - 0.01:
            break
        if count >= len(ranked):
            # A single long take may need to remain on screen longer, but it
            # must still stay inside the exact event window.
            caps = [b - a - 0.03 for a, b in selected]
            if sum(caps) < target - 0.01:
                raise RuntimeError(
                    f"Cue audio ({target:.2f}s) is longer than unused event footage "
                    f"inside {start}-{end} ({sum(caps):.2f}s)"
                )
            break
        count += 1

    durations = [0.0] * len(selected)
    remaining = target
    active = set(range(len(selected)))
    while active and remaining > 1e-6:
        share = remaining / len(active)
        saturated = False
        for index in list(active):
            room = caps[index] - durations[index]
            addition = min(share, room)
            durations[index] += addition
            remaining -= addition
            if room <= share + 1e-6:
                active.remove(index)
                saturated = True
        if not saturated and active:
            for index in active:
                durations[index] += remaining / len(active)
            remaining = 0

    shots = []
    for (a, b), duration in zip(selected, durations):
        if duration < 0.12:
            continue
        # Keep the anchor inside one of the selected shots whenever possible.
        if a <= anchor <= b and duration < b - a:
            clip_start = min(max(a, anchor - duration / 2), b - duration)
        else:
            clip_start = a + max(0, (b - a - duration) / 2)
        shots.append((clip_start, clip_start + duration))

    actual = sum(b - a for a, b in shots)
    if abs(actual - target) > 0.02:
        raise RuntimeError(
            f"Frame allocation mismatch in {start}-{end}: {actual:.3f}s != {target:.3f}s"
        )
    if any(a < start - 0.01 or b > end + 0.01 for a, b in shots):
        raise RuntimeError(f"Shot escaped its exact cue range {start}-{end}")
    return shots


async def generate_cue_tts(sections, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    total = sum(len(cue["clip_texts"]) for section in sections for cue in section["cues"])
    completed = 0
    for section_index, section in enumerate(sections, 1):
        for cue_index, cue in enumerate(section["cues"], 1):
            for clip_index, text in enumerate(cue["clip_texts"], 1):
                completed += 1
                target = directory / (
                    f"section_{section_index:02d}_cue_{cue_index:02d}_clip_{clip_index:02d}.mp3"
                )
                if target.exists() and target.stat().st_size:
                    continue
                print(
                    f"Generating Yunjian clip {completed}/{total}: {text}", flush=True
                )
                for attempt in range(4):
                    try:
                        communication = edge_tts.Communicate(
                            text,
                            VOICE,
                            rate=VOICE_RATE,
                            volume="+2%",
                            pitch=VOICE_PITCH,
                        )
                        await communication.save(str(target))
                        break
                    except Exception:
                        if attempt == 3:
                            raise
                        await asyncio.sleep(2**attempt)
                await asyncio.sleep(0.12)


def build_section_audio(section_index, cue_paths, directory: Path):
    concat_list = directory / f"section_{section_index:02d}_audio.txt"
    concat_list.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in cue_paths) + "\n",
        encoding="utf-8",
    )
    output = directory / f"section_{section_index:02d}.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-ac",
            "2",
            "-ar",
            "44100",
            "-c:a",
            "pcm_s16le",
            output,
        ]
    )
    return output


def render_section(
    index,
    section,
    scenes,
    source: Path,
    tts_directory: Path,
    directory: Path,
    used_intervals,
    shot_duration,
):
    output = directory / f"section_{index:02d}.mp4"
    ass = directory / f"section_{index:02d}.ass"

    clip_records = []
    clip_paths = []
    for cue_index, cue in enumerate(section["cues"], 1):
        if len(cue["clips"]) != len(cue["clip_texts"]):
            raise RuntimeError(f"Cue {index}.{cue_index} clip/text count mismatch")
        for clip_index, ((source_in, source_out), text) in enumerate(
            zip(cue["clips"], cue["clip_texts"]), 1
        ):
            path = tts_directory / (
                f"section_{index:02d}_cue_{cue_index:02d}_clip_{clip_index:02d}.mp3"
            )
            clip_paths.append(path)
            clip_records.append(
                {
                    "cue": cue_index,
                    "clip": clip_index,
                    "source_in": float(source_in),
                    "source_out": float(source_out),
                    "text": text,
                }
            )

    clip_durations = [media_duration(path) for path in clip_paths]
    narration_audio = build_section_audio(index, clip_paths, tts_directory)
    section_duration = media_duration(narration_audio)
    clip_durations[-1] += section_duration - sum(clip_durations)
    subtitle_items = [{"text": record["text"]} for record in clip_records]
    write_ass(ass, cue_subtitle_timeline(subtitle_items, clip_durations))

    # Each selected movie clip now owns exactly one narration recording. The
    # video cannot cut to the next clip until that recording has ended.
    shots = []
    edl_rows = []
    output_cursor = 0.0
    for record, audio_duration in zip(clip_records, clip_durations):
        source_in = record["source_in"]
        source_out = record["source_out"]
        source_duration = source_out - source_in
        speed_factor = audio_duration / source_duration
        if not 0.55 <= speed_factor <= 1.70:
            raise RuntimeError(
                f"Clip {index}.{record['cue']}.{record['clip']} requires excessive retiming: "
                f"factor={speed_factor:.3f}, audio={audio_duration:.3f}s, "
                f"footage={source_duration:.3f}s"
            )
        if any(
            source_in < used_end and source_out > used_start
            for used_start, used_end in used_intervals
        ):
            raise RuntimeError(f"Duplicate fixed source clip: {source_in}-{source_out}")
        used_intervals.append((source_in, source_out))
        shots.append((source_in, source_out, speed_factor, audio_duration))
        edl_rows.append(
            {
                "section": index,
                "cue": record["cue"],
                "clip": record["clip"],
                "source_in": round(source_in, 3),
                "source_out": round(source_out, 3),
                "speed_factor": round(speed_factor, 5),
                "output_in": round(output_cursor, 3),
                "output_out": round(output_cursor + audio_duration, 3),
                "narration": record["text"],
            }
        )
        output_cursor += audio_duration

    if abs(output_cursor - section_duration) > 0.03:
        raise RuntimeError(
            f"Section {index} clip/audio timeline mismatch: "
            f"{output_cursor:.3f}s != {section_duration:.3f}s"
        )

    with (directory / f"section_{index:02d}_edl.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=edl_rows[0].keys())
        writer.writeheader()
        writer.writerows(edl_rows)

    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for source_in, source_out, _, _ in shots:
        command += [
            "-ss", f"{source_in:.3f}", "-t", f"{source_out-source_in:.3f}",
            "-i", str(source),
        ]
    command += ["-i", str(narration_audio)]

    filters, pairs = [], []
    for shot_index, (source_in, source_out, speed_factor, output_duration) in enumerate(shots):
        source_length = source_out - source_in
        audio_tempo = 1.0 / speed_factor
        filters.append(
            f"[{shot_index}:v]trim=duration={source_length:.4f},"
            f"setpts=(PTS-STARTPTS)*{speed_factor:.8f},"
            # The new 1280x720 recap keeps its creator mark in the top 56
            # pixels and baked captions below y=664. Retain only the clean
            # movie image, then reserve a fresh lower band for our subtitles.
            "crop=1280:608:0:56,pad=1280:720:0:30:black,"
            f"setsar=1,fps=24,trim=duration={output_duration:.4f},format=yuv420p[v{shot_index}]"
        )
        filters.append(
            f"[{shot_index}:a]atrim=duration={source_length:.4f},"
            f"asetpts=PTS-STARTPTS,atempo={audio_tempo:.8f},"
            f"atrim=duration={output_duration:.4f},aresample=44100[a{shot_index}]"
        )
        pairs.append(f"[v{shot_index}][a{shot_index}]")
    filters.append("".join(pairs) + f"concat=n={len(shots)}:v=1:a=1[vcat][acat]")
    ass_name = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    filters.append(f"[vcat]subtitles=filename='{ass_name}'[vout]")
    narration_index = len(shots)
    filters.append(
        f"[{narration_index}:a]atrim=duration={section_duration:.4f},"
        "asetpts=PTS-STARTPTS,aresample=44100,highpass=f=70,lowpass=f=12000,"
        "equalizer=f=160:t=q:w=1:g=2,"
        "acompressor=threshold=0.125:ratio=2.2:attack=15:release=140:makeup=1.4[narr]"
    )
    filters.append(
        f"[acat]volume={MOVIE_VOLUME}[movie];[movie][narr]"
        "amix=inputs=2:duration=first:weights=1 1:normalize=0,"
        "alimiter=limit=0.96[aout]"
    )
    command += [
        "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "2200k",
        "-maxrate", "2800k", "-bufsize", "4400k", "-pix_fmt", "yuv420p",
        "-r", "24", "-g", "48", "-c:a", "aac", "-b:a", "128k",
        "-ar", "44100", "-movflags", "+faststart", "-t", f"{section_duration:.4f}",
        str(output),
    ]
    print(
        f"Rendering clip-locked section {index}: {section_duration:.1f}s / "
        f"{len(shots)} clips with independent Yunjian tracks",
        flush=True,
    )
    run(command)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--scenes", required=True, type=Path)
    parser.add_argument("--narration", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    sections = json.loads(args.narration.read_text(encoding="utf-8"))

    # This production uses a reviewed, event-level EDL. Never guess a clip from
    # keywords or proportional source position: a missing range is a hard error.
    source_duration = media_duration(args.source)
    selected = []
    cue_count = 0
    for section_index, section in enumerate(sections, 1):
        for cue_index, cue in enumerate(section["cues"], 1):
            cue_count += 1
            clips = cue.get("clips") or []
            clip_texts = cue.get("clip_texts") or []
            if len(clips) != 1 or len(clip_texts) != 1:
                raise RuntimeError(
                    f"Cue {section_index}.{cue_index} must own exactly one reviewed clip and narration"
                )
            if clip_texts[0] != cue["text"]:
                raise RuntimeError(f"Cue {section_index}.{cue_index} text differs from its clip narration")
            start, end = map(float, clips[0])
            if not (0 <= start < end <= source_duration):
                raise RuntimeError(f"Cue {section_index}.{cue_index} has invalid source range {start}-{end}")
            for previous_start, previous_end, previous_name in selected:
                if start < previous_end and end > previous_start:
                    raise RuntimeError(
                        f"Cue {section_index}.{cue_index} overlaps reviewed cue {previous_name}: "
                        f"{start}-{end} vs {previous_start}-{previous_end}"
                    )
            selected.append((start, end, f"{section_index}.{cue_index}"))
    print(
        f"Verified manual EDL: {cue_count} narration events / {len(selected)} exclusive source clips.",
        flush=True,
    )

    tts_directory = args.work / "tts"
    render_directory = args.work / "render"
    render_directory.mkdir(parents=True, exist_ok=True)

    asyncio.run(generate_cue_tts(sections, tts_directory))
    scenes = parse_scenes(args.scenes)
    reference = args.source.parent / "reference.mp4"
    shot_duration = measure_reference_rhythm(reference, args.work)
    outputs = []
    used_intervals = []
    for index, section in enumerate(sections, 1):
        outputs.append(
            render_section(
                index,
                section,
                scenes,
                args.source,
                tts_directory,
                render_directory,
                used_intervals,
                shot_duration,
            )
        )

    concat_list = render_directory / "sections.txt"
    concat_list.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in outputs) + "\n",
        encoding="utf-8",
    )
    raw_output = args.work / "raw.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            raw_output,
        ]
    )

    from generate_horror_bgm import generate_horror_bgm

    bgm = args.work / "original-horror-loop.wav"
    generate_horror_bgm(bgm, BGM_LOOP_SECONDS)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mix_filter = (
        f"[0:a]asplit=2[main][side];"
        f"[1:a]volume={BGM_VOLUME}[bg];"
        "[bg][side]sidechaincompress=threshold=0.02:ratio=3:attack=25:release=350[ducked];"
        "[main][ducked]amix=inputs=2:duration=first:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            raw_output,
            "-stream_loop",
            "-1",
            "-i",
            bgm,
            "-filter_complex",
            mix_filter,
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "44100",
            "-movflags",
            "+faststart",
            args.output,
        ]
    )
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            args.output,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ]
    )
    print(
        f"FINAL: {args.output} / {media_duration(args.output):.2f}s / "
        f"{args.output.stat().st_size/1048576:.1f}MB"
    )


if __name__ == "__main__":
    main()
