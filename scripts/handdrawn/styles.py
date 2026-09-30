"""Access to the 327-asset hand-drawn style catalog.

The catalog itself (297 style recipes + 30 theme palettes) ships as
``references/handdrawn-style-library.json`` and is redistributed unmodified from
the upstream project under its own license -- see
``references/handdrawn-styles-LICENSE.txt``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

DEFAULT_STYLE_ID = "colored-pencil-diary"


class StyleLibrary:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"style library missing: {self.path}")
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.styles: List[dict] = self.data.get("styles", [])
        self.palettes: List[dict] = self.data.get("palettes", [])
        self.featured: List[str] = self.data.get("featured_styles", [])
        self.categories = {
            entry["id"]: entry.get("name_zh", entry["id"])
            for entry in self.data.get("categories", [])
        }
        self._index = {}
        for entry in [*self.styles, *self.palettes]:
            self._index[entry["id"].lower()] = entry
            for alias in entry.get("aliases", []) or []:
                self._index.setdefault(str(alias).lower(), entry)

    # -- lookup -------------------------------------------------------------

    def resolve(self, token: Optional[str]) -> dict:
        if not token:
            return self._index[DEFAULT_STYLE_ID]
        key = str(token).strip().lower()
        if key in self._index:
            return self._index[key]
        if key.isdigit():
            number = int(key)
            for entry in self.styles:
                if entry.get("order") == number:
                    return entry
        for entry in [*self.styles, *self.palettes]:
            if entry.get("name_zh", "").lower() == key or entry.get("name_en", "").lower() == key:
                return entry
        available = ", ".join(sorted(e["id"] for e in self.styles[:8]))
        raise SystemExit(f"未知画风：{token}（例如 {available} ...）")

    def palette(self, token: Optional[str]) -> Optional[dict]:
        if not token:
            return None
        entry = self.resolve(token)
        if entry.get("type") != "palette" and not entry["id"].startswith("C-"):
            raise SystemExit(f"{token} 不是主题配色，请用 C-01 … C-30")
        return entry

    def contains(self, entry: dict, query: str) -> bool:
        haystack = " ".join(str(entry.get(field, "")) for field in
                            ("id", "name_zh", "name_en", "summary", "group", "category"))
        haystack += " " + " ".join(str(a) for a in entry.get("aliases", []) or [])
        haystack += " " + " ".join(str(b) for b in entry.get("best_for", []) or [])
        return query.lower() in haystack.lower()

    # -- listing ------------------------------------------------------------

    def list(
        self,
        asset_type: str = "style",
        all_styles: bool = False,
        category: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[dict]:
        if asset_type == "palette":
            entries = list(self.palettes)
        elif asset_type == "all":
            entries = [*self.styles, *self.palettes]
        else:
            entries = list(self.styles)
            if not all_styles and not category and not query:
                by_id = {entry["id"]: entry for entry in self.styles}
                entries = [by_id[sid] for sid in self.featured if sid in by_id]
        if category:
            entries = [e for e in entries if e.get("category") == category]
        if query:
            entries = [e for e in entries if self.contains(e, query)]
        return entries

    def describe(self, entry: dict) -> str:
        if entry.get("type") == "palette":
            return f"{entry['id']}  {entry.get('name_zh','')} · {entry.get('category_zh','')}"
        number = entry.get("order")
        marker = " ★" if entry["id"] in self.featured else ""
        return f"{number:>3}. {entry['id']:<32} {entry.get('name_zh','')}{marker}"


def load(project_dir: Path) -> StyleLibrary:
    return StyleLibrary(project_dir / "references" / "handdrawn-style-library.json")
