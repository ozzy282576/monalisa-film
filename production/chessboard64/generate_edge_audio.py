#!/usr/bin/env python3
"""Create runner-side narration if the private-by-policy Release assets are absent.

The preferred source remains the selected ``voice-00`` MP3s in the
``chessboard64-audio-v1`` Release. This fallback keeps the film renderable when
that Release is empty/unreachable: one consistent Chinese male neural voice is
synthesized from the reviewed chapter text on the Actions runner. Generated MP3
files stay in the disposable runner workspace and render artifact, never Git.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORY = HERE / "story.json"
MANIFEST = HERE / "audio" / "manifest.json"
RAW = HERE / "audio" / "raw"
DEFAULT_VOICE = "zh-CN-YunyangNeural"


def retry_delay(attempt: int) -> int:
    return min(120, 20 + (attempt - 1) * 5)


async def synthesize(text: str, destination: Path, voice: str, attempts: int) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("edge-tts is required for the narration fallback") from exc

    temporary = destination.with_name(destination.stem + ".part.mp3")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        temporary.unlink(missing_ok=True)
        try:
            communicator = edge_tts.Communicate(text=text, voice=voice, rate="+0%")
            await communicator.save(str(temporary))
            if not temporary.is_file() or temporary.stat().st_size < 4096:
                raise RuntimeError("TTS service returned an empty/short MP3")
            temporary.replace(destination)
            return
        except Exception as exc:  # transient service/network failures are retried below
            last_error = exc
            temporary.unlink(missing_ok=True)
            if attempt == attempts:
                break
            delay = retry_delay(attempt)
            print(f"EDGE_TTS_RETRY {destination.stem} {attempt}/{attempts} wait={delay}s: "
                  f"{type(exc).__name__}: {str(exc)[:180]}", flush=True)
            await asyncio.sleep(delay)
    raise RuntimeError(f"TTS failed for {destination.stem} after {attempts} attempts: {last_error}")


async def generate(voice: str, attempts: int) -> None:
    story = json.loads(STORY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    chapters = {row["id"]: row["text"] for row in story.get("chapters", [])}
    clips = manifest.get("clips") or []
    if set(chapters) != {row.get("id") for row in clips}:
        raise ValueError("audio manifest clips do not match story chapters")
    for row in clips:
        if row.get("text") != chapters[row["id"]]:
            raise ValueError(f"Narration source text mismatch for {row['id']}")

    RAW.mkdir(parents=True, exist_ok=True)
    for row in clips:
        destination = RAW / f"{row['id']}.mp3"
        await synthesize(row["text"], destination, voice, attempts)
        row["voice_id"] = voice
        print(f"EDGE_TTS_READY {row['id']} {destination.stat().st_size} bytes voice={voice}", flush=True)

    manifest["voice_id"] = voice
    manifest["selection"] = (
        f"Runner-side fallback neural narrator {voice}; used only because the selected voice-00 "
        "Release assets were unavailable. All chapters use this same voice."
    )
    manifest["post_processing"] = (
        "Runner-side TTS from the reviewed script; atempo=0.80 pitch-preserving pacing, "
        "sentence-pause tightening, and measured clause/cut alignment."
    )
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", default=os.environ.get("EDGE_TTS_VOICE", DEFAULT_VOICE))
    parser.add_argument("--attempts", type=int, default=8)
    args = parser.parse_args()
    if args.attempts < 1:
        parser.error("--attempts must be >= 1")
    asyncio.run(generate(args.voice, args.attempts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
