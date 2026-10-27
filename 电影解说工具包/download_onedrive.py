#!/usr/bin/env python3
"""Assemble the newly uploaded commentary video from verified Git chunks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PARTS_DIR = Path(__file__).resolve().parent / "new_source_parts"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Retained for workflow compatibility")
    parser.add_argument("output")
    args = parser.parse_args()

    manifest_path = PARTS_DIR / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"New source manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_size = int(manifest["size"])
    expected_sha256 = manifest["sha256"].upper()
    inventory = []
    for part_name in manifest["parts"]:
        part = PARTS_DIR / part_name
        inventory.append(f"{part_name}:{part.stat().st_size if part.exists() else 'missing'}")
    print(f"::notice title=New source part inventory::{', '.join(inventory)}", flush=True)

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with output.open("wb") as destination:
        for part_name in manifest["parts"]:
            part = PARTS_DIR / part_name
            if not part.exists():
                raise RuntimeError(f"New source part is missing: {part}")
            print(f"Assembling {part.name} ({part.stat().st_size} bytes)...", flush=True)
            with part.open("rb") as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    destination.write(block)
                    digest.update(block)

    actual_size = output.stat().st_size
    actual_sha256 = digest.hexdigest().upper()
    if actual_size != expected_size:
        raise RuntimeError(f"New source size mismatch: {actual_size} != {expected_size}")
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"New source checksum mismatch: {actual_sha256} != {expected_sha256}")
    print(
        f"::notice title=New source verified::{manifest['name']} / {actual_size} bytes / "
        f"SHA256 {actual_sha256}",
        flush=True,
    )


if __name__ == "__main__":
    main()
