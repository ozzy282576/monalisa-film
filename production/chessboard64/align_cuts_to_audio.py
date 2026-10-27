#!/usr/bin/env python3
"""Re-anchor every shot boundary to the measured silence before its script clause.

The shot-to-clause mapping is reviewed once in ``audio/cut-clauses.json``. This
script only changes the chapter-local cut seconds: it chooses a point inside the
measured inter-clause pause, so a regenerated narrator can be used without
letting dialogue drift across shots. It fails closed if any mapped clause is
missing, merged into a different clause, or has no usable pause.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CUT_MAP = HERE / "audio" / "cut-clauses.json"
TIMES = HERE / "audio" / "clause-times.json"
RENDER = HERE / "render.py"


def normalize(text: str) -> str:
    return re.sub(r"[\s，。！？；：、—,.!?;:]+", "", text)


def align(mapping: dict, timings: dict, current_cuts: dict) -> dict:
    if set(mapping) != set(current_cuts) or set(timings) != set(current_cuts):
        raise ValueError("cut map, clause timings and render chapters must match exactly")
    result = {}
    for chapter, entries in current_cuts.items():
        targets = mapping.get(chapter, [])
        if len(targets) != len(entries) - 1:
            raise ValueError(f"{chapter}: expected {len(entries)-1} mapped cuts, got {len(targets)}")
        clauses = timings[chapter]["clauses"]
        new_entries = [(0.0, entries[0][1], entries[0][2])]
        last_clause = -1
        for entry, target in zip(entries[1:], targets):
            _old_time, shot_id, variant = entry
            if target.get("shot") != shot_id:
                raise ValueError(f"{chapter}/{shot_id}: cut-map order does not match render.py")
            wanted = normalize(str(target.get("clause", "")))
            matches = [i for i, row in enumerate(clauses)
                       if normalize(str(row.get("text", ""))) == wanted]
            matches = [i for i in matches if i > last_clause]
            if not matches:
                containing = [row.get("text", "") for row in clauses
                              if wanted and wanted in normalize(str(row.get("text", "")))]
                detail = f"; merged/containing rows={containing!r}" if containing else ""
                raise ValueError(f"{chapter}/{shot_id}: exact target clause not found: {target.get('clause')!r}{detail}")
            clause_index = matches[0]
            if clause_index == 0:
                raise ValueError(f"{chapter}/{shot_id}: cut target unexpectedly maps to first clause")
            prior_end = float(clauses[clause_index - 1]["end"])
            next_start = float(clauses[clause_index]["start"])
            gap = next_start - prior_end
            if not 0.0 < gap <= 0.70:
                raise ValueError(f"{chapter}/{shot_id}: unusable pause before clause ({gap:.3f}s)")
            # Stay inside the measured pause and within the approved 350 ms pre-roll.
            # A hand-reviewed per-cut pre_roll may use more of a long silence to balance a
            # fixed-duration source clip; ordinary cuts keep the conservative midpoint rule.
            requested_pre_roll = float(target.get("pre_roll", 0.15))
            if not 0.0 <= requested_pre_roll <= 0.35:
                raise ValueError(f"{chapter}/{shot_id}: pre_roll must be between 0 and 0.35s")
            if "pre_roll" in target:
                offset = min(requested_pre_roll, max(0.0, gap - 0.01))
            else:
                offset = min(0.15, gap / 2.0)
            cut = round(next_start - offset, 2)
            if (not next_start - 0.35 - 1e-6 <= cut <= next_start + 1e-6
                    or cut < prior_end - 1e-6):
                raise ValueError(f"{chapter}/{shot_id}: rounded cut left the measured silence/sync window")
            new_entries.append((cut, shot_id, variant))
            last_clause = clause_index
        if any(new_entries[i][0] >= new_entries[i + 1][0]
               for i in range(len(new_entries) - 1)):
            raise ValueError(f"{chapter}: aligned cuts are not strictly increasing")
        result[chapter] = new_entries
    return result


def render_source(cuts: dict) -> str:
    def fmt(value: float) -> str:
        if value == 0:
            return "0.0"
        return f"{value:.2f}".rstrip("0").rstrip(".")

    lines = ["CUTS = {"]
    for chapter, entries in cuts.items():
        encoded = ", ".join(f"({fmt(t)},{sid!r},{variant!r})" for t, sid, variant in entries)
        lines.append(f"    {chapter!r}: [{encoded}],")
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print aligned cuts without editing render.py")
    args = parser.parse_args()
    sys.path.insert(0, str(HERE))
    import render  # noqa: E402 - same project, loaded only after argparse setup

    mapping = json.loads(CUT_MAP.read_text(encoding="utf-8"))
    timings = json.loads(TIMES.read_text(encoding="utf-8"))
    aligned = align(mapping, timings, render.CUTS)
    for chapter, entries in aligned.items():
        print(chapter + " " + " ".join(f"{shot}={time:.2f}" for time, shot, _ in entries))
    if args.dry_run:
        return 0

    source = RENDER.read_text(encoding="utf-8")
    pattern = r"CUTS = \{.*?\n\}(?=\n# 看片后的镜头修正)"
    updated, count = re.subn(pattern, render_source(aligned), source, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not uniquely locate the CUTS block in render.py")
    RENDER.write_text(updated, encoding="utf-8")
    print("ALIGNED_CUTS_TO_MEASURED_SILENCES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
