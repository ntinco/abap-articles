#!/usr/bin/env python3
"""Publication contracts of `_posts/`: EN/DE/ES sets, front matter, and the visible anonymization note."""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml  # PyYAML, pinned in tools/requirements.txt

ROOT = Path(__file__).resolve().parents[1]
LANGS = {"en", "de", "es"}
KEYS = ("layout", "title", "date", "lang", "categories", "description", "translations")


def front_matter(text: str) -> tuple[dict, str]:
    """The Jekyll front matter as PyYAML reads it, and the body; ({}, text) without a closed `---` block."""
    parts = text.split("---\n", 2) if text.startswith("---\n") else []
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise yaml.YAMLError("front matter must be a mapping")
    return data, parts[2]


def problems(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    by_date: dict[str, set[str]] = defaultdict(set)
    posts = sorted((root / "_posts").glob("*.md"))
    if not posts:
        found.append("no canonical posts found")
    for path in posts:
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(en|de|es)-[a-z0-9-]+\.md", path.name)
        if not match:
            found.append(f"{path.name}: filename must be date-lang-lowercase-ascii-slug")
            continue
        day, lang = match.groups()
        by_date[day].add(lang)
        try:
            fm, body = front_matter(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            found.append(f"{path.name}: front matter is not valid YAML: {str(exc).splitlines()[0]}")
            continue
        found += [f"{path.name}: missing front matter {key}" for key in KEYS if key not in fm]
        if fm.get("lang") != lang:
            found.append(f"{path.name}: lang {fm.get('lang')!r} does not match filename")
        if fm.get("layout") != "article":
            found.append(f"{path.name}: layout must be article")
        translations = fm.get("translations") or []
        translated = {t.get("lang") for t in (translations if isinstance(translations, list) else [translations])
                      if isinstance(t, dict)}
        found += [f"{path.name}: translations missing {missing}" for missing in sorted(LANGS - translated)]
        if 'class="note"' not in body:
            found.append(f"{path.name}: missing visible production-protection note")
    found += [f"{day}: publication set must contain EN/DE/ES, found {sorted(langs)}"
              for day, langs in by_date.items() if langs != LANGS]
    return found


def main() -> int:
    found = problems()
    print("\n".join(f"FAIL {p}" for p in found) or "HEALTH PASS")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
