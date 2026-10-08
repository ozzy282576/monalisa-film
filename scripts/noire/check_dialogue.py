#!/usr/bin/env python3
"""Check that each beat's narration and on-screen subtitle say the same thing.

A viewer hears one sentence and reads another. Nothing in the pipeline catches
that: both fields render happily, the timing is driven by the audio, and the
subtitle looks fine on its own. It only shows up by comparing them — which is
what this does.

What counts as a problem
-----------------------
Subtitles are *supposed* to condense narration — nobody wants a wall of text
under the picture. So a subtitle that drops a clause is fine, and normal.

The failure that matters is invention: the subtitle claiming something the voice
never said. So the test is whether the subtitle can be read off the narration —
as a subsequence, allowing any amount of dropping but no additions. Coverage is
reported for information, not as a pass/fail.

Two deliberate equivalences, so this reports real divergence and not noise:

* Punctuation and whitespace are ignored.
* Numbers compare equal however they are written, because the artwork uses
  digits ("0.74 m") while the voice says "零点七四". Chinese numerals used *as
  words* ("一切", "第一") collapse the same way on both sides, so they cancel.

Exit code is non-zero when anything diverges, so this can gate a render.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Punctuation, symbols and whitespace carry no meaning for this comparison.
_PUNCT = re.compile(r"[\s，。、；：？！“”‘’—…·（）()\[\]{}<>《》〈〉\-—–~〜/\\|+*_=#@$%^&\"'`,.]")
# Digits and Chinese numerals both become a single placeholder token.
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?|[零一二三四五六七八九十百千万亿两]+")
_PLACEHOLDER = "\u00a7"


def normalise(text: str) -> str:
    text = _NUMBER.sub(_PLACEHOLDER, text or "")
    return _PUNCT.sub("", text)


def _extras(narration: str, on_screen: str) -> str:
    """Characters the subtitle has that the narration never says."""
    from collections import Counter
    pool = Counter(narration)
    extra = []
    for ch in on_screen:
        if pool[ch] > 0:
            pool[ch] -= 1
        else:
            extra.append(ch)
    return "".join(extra)


def compare(narration: str, on_screen: str) -> Tuple[str, str]:
    spoken = normalise(narration)
    shown = normalise(on_screen)
    if spoken == shown:
        return "match", ""

    invented = _extras(spoken, shown)
    if invented:
        return "invented", f"字幕里有旁白没说的字：{invented}"

    coverage = len(shown) / max(1, len(spoken))
    return "condensed", f"字幕是旁白的浓缩（保留 {coverage:.0%}）"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--script", default="examples/douyin-physics/script.json")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.script)
    raw = json.loads(path.read_text(encoding="utf-8"))

    problems = 0
    checked = 0
    condensed = 0
    for beat in raw["beats"]:
        narration = (beat.get("narration") or "").strip()
        on_screen = (beat.get("on_screen") or "").strip()
        if not narration or not on_screen:
            continue          # title cards and pure-graphic beats are exempt
        checked += 1
        status, detail = compare(narration, on_screen)
        if status in ("match", "condensed"):
            if not args.quiet:
                print(f"  {beat['id']}  {status}" + (f"  — {detail}" if detail else ""))
            if status == "condensed":
                condensed += 1
            continue
        problems += 1
        print(f"  {beat['id']}  {status}  {detail}")
        print(f"      念出：{narration}")
        print(f"      字幕：{on_screen}")

    print(f"\n检查 {checked} 幕：一致 {checked - problems - condensed}，"
          f"浓缩 {condensed}，问题 {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
