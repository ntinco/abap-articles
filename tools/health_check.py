#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# agent-core runs the workspace contract check for every repository; none commits a copy of it.
SHARED_CONTRACT = ROOT.parent / "agent-core" / "shared/workspace_contract.py"
# Checks whose skip is printed as a notice, since a skipped check there leaves a contract unverified.
NOTICE_ON_SKIP = {"workspace_contract"}
LANGS = {"en", "de", "es"}
REQUIRED = [
    "AGENTS.md", "README.md", "ai/governance.md", "ai/repo-map.json",
    "_posts", "_layouts/article.html", "_includes/head-custom.html", "assets/css/style.scss", "index.html", "posts.md",
    "_config.yml", "ai/upstreams.json", "prompts/README.md", "prompts/editorial-voice.md", "prompts/templates",
    "tools/health_check.py", "tests/test_health_check.py", ".github/workflows/jekyll-gh-pages.yml",
]
FORBIDDEN_CONTROL = [
    ".github/copilot-instructions.md",
    "prompts/abap-keyflow-writing-prompt.md",
    "prompts/abap-keyflow-publishing-prompt.md",
    "prompts/system",
    "prompts/workflows",
    "prompts/operations",
    "prompts/checklists",
    "prompts/simulations",
    "docs/rag-content-strategy.md",
    "docs/simple-content-system.md",
    # Legacy URLs are `redirect_from` entries of the canonical post (jekyll-redirect-from); a local `redirect` layout
    # would replace the plugin's stock redirect page.
    "posts",
    "_layouts/redirect.html",
]


def result(name: str, problems: list[str]) -> dict[str, object]:
    return {"check": name, "status": "fail" if problems else "pass", "detail": problems or "ok"}


def required_paths(root: Path) -> dict[str, object]:
    return result("required_paths", [p for p in REQUIRED if not (root / p).exists()])


def forbidden_surfaces(root: Path) -> dict[str, object]:
    return result("forbidden_control_surfaces", [p for p in FORBIDDEN_CONTROL if (root / p).exists()])


def repo_map(root: Path) -> dict[str, object]:
    problems: list[str] = []
    try:
        data = json.loads((root / "ai/repo-map.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return result("repo_map", [str(exc)])
    if data.get("schema_version") != "1.0":
        problems.append("schema_version must be 1.0")
    routing = data.get("routing")
    if not isinstance(routing, dict):
        problems.append("routing must be an object")
        routing = {}
    for task, paths in routing.items():
        if not isinstance(paths, list) or not paths:
            problems.append(f"routing {task!r} must contain paths")
            continue
        for routed in paths:
            if not (root / str(routed).rstrip("/")).exists():
                problems.append(f"{task}: missing routed path {routed}")
    return result("repo_map", problems)


def front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return "", text
    return parts[1], parts[2]


def scalar(fm: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", fm)
    return match.group(1).strip().strip('"\'') if match else ""


def post_contracts(root: Path) -> dict[str, object]:
    problems: list[str] = []
    by_date: dict[str, set[str]] = defaultdict(set)
    posts = sorted((root / "_posts").glob("*.md"))
    if not posts:
        problems.append("no canonical posts found")
    for path in posts:
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(en|de|es)-([a-z0-9-]+)\.md", path.name)
        if not match:
            problems.append(f"{path.name}: filename must be date-lang-lowercase-ascii-slug")
            continue
        day, filename_lang, _ = match.groups()
        fm, body = front_matter(path.read_text(encoding="utf-8"))
        for key in ("layout", "title", "date", "lang", "categories", "description", "translations"):
            if not re.search(rf"(?m)^{re.escape(key)}:", fm):
                problems.append(f"{path.name}: missing front matter {key}")
        lang = scalar(fm, "lang")
        if lang != filename_lang:
            problems.append(f"{path.name}: lang {lang!r} does not match filename")
        if scalar(fm, "layout") != "article":
            problems.append(f"{path.name}: layout must be article")
        by_date[day].add(filename_lang)
        for required_lang in LANGS:
            if not re.search(rf"(?m)^\s*- lang:\s*{required_lang}\s*$", fm):
                problems.append(f"{path.name}: translations missing {required_lang}")
        if 'class="note"' not in body:
            problems.append(f"{path.name}: missing visible production-protection note")
    for day, langs in by_date.items():
        if langs != LANGS:
            problems.append(f"{day}: publication set must contain EN/DE/ES, found {sorted(langs)}")
    return result("post_contracts", problems)


def post_permalinks(root: Path) -> set[str]:
    """Jekyll URLs of the canonical posts, for the `_config.yml` permalink pattern.

    Supports what the posts use: inline-list or scalar categories, a front matter `date`, `slug` or `permalink`.
    """
    config = root / "_config.yml"
    pattern = scalar(config.read_text(encoding="utf-8"), "permalink") if config.exists() else ""
    pattern = pattern or "/:categories/:year/:month/:day/:title/"
    urls: set[str] = set()
    for path in sorted((root / "_posts").glob("*.md")):
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(.+)\.md", path.name)
        if not match:
            continue
        fm, _ = front_matter(path.read_text(encoding="utf-8"))
        if scalar(fm, "permalink"):
            urls.add(scalar(fm, "permalink"))
            continue
        dated = re.match(r"(\d{4})-(\d{2})-(\d{2})", scalar(fm, "date")) or re.match(r"(\d{4})-(\d{2})-(\d{2})", path.name)
        year, month, day = dated.groups()
        raw = scalar(fm, "categories")
        items = raw[1:-1].split(",") if raw.startswith("[") else raw.split()
        categories = dict.fromkeys(c.strip().strip('"\'').lower() for c in items if c.strip())
        values = {"categories": "/".join(categories), "year": year, "month": month, "day": day,
                  "title": scalar(fm, "slug") or match.group(2)}
        url = re.sub(r":(categories|year|month|day|title)", lambda m: values[m.group(1)], pattern)
        urls.add(re.sub(r"/{2,}", "/", url))
    return urls


def block_list(fm: str, key: str) -> list[str]:
    """Items of a YAML block list (`key:` then `  - item` lines; a trailing `# comment` is ignored), or a scalar `key: item`."""
    match = re.search(rf"(?m)^{re.escape(key)}:[ \t]*(.*)\n((?:[ \t]+-[ \t]*.*\n?)*)", fm)
    if not match:
        return []
    inline = re.sub(r"(^|\s)#.*$", "", match.group(1)).strip()
    if inline:
        return [inline.strip('"\'')]
    return [re.sub(r"^\s*-\s*", "", line).strip().strip('"\'') for line in match.group(2).splitlines() if line.strip()]


def redirect_contracts(root: Path) -> dict[str, object]:
    """Each legacy URL is a site-local `redirect_from` entry of one canonical post, never a post's own URL."""
    problems: list[str] = []
    permalinks = post_permalinks(root)
    seen: dict[str, str] = {}
    for path in sorted((root / "_posts").glob("*.md")):
        fm, _ = front_matter(path.read_text(encoding="utf-8"))
        for source in block_list(fm, "redirect_from"):
            if not source.startswith("/") or source.startswith("//"):
                problems.append(f"{path.name}: redirect_from {source!r} must be a site-local path")
            elif source in permalinks:
                problems.append(f"{path.name}: redirect_from {source} is a canonical post permalink")
            elif source in seen:
                problems.append(f"{path.name}: redirect_from {source} already redirects to {seen[source]}")
            else:
                seen[source] = path.name
    return result("redirect_contracts", problems)


def load_shared_contract(path: Path = SHARED_CONTRACT):
    """agent-core's workspace_contract module, or None when agent-core is not beside this repository."""
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("workspace_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace_contract(root: Path, path: Path = SHARED_CONTRACT) -> dict[str, object]:
    """Skipped with a notice, not failed, in a clone without agent-core beside it (CI clones this repository alone)."""
    shared = load_shared_contract(path)
    if shared is None:
        return {"check": "workspace_contract", "status": "skip",
                "detail": f"{path} not found: clone agent-core beside this repository to check the workspace contract"}
    return result("workspace_contract", shared.problems(root))


def build(root: Path = ROOT) -> dict[str, object]:
    checks = [required_paths(root), forbidden_surfaces(root), repo_map(root), post_contracts(root), redirect_contracts(root), workspace_contract(root)]
    failures = sum(c["status"] == "fail" for c in checks)
    return {"structural_status": "fail" if failures else "pass", "failure_count": failures, "checks": checks}


def brief(summary: dict) -> str:
    checks = summary["checks"]
    failed = [c for c in checks if c["status"] == "fail"]
    passed = sum(c["status"] == "pass" for c in checks)
    skipped = len(checks) - passed - len(failed)
    status = "FAIL" if summary["failure_count"] else "PASS"
    lines = [f"HEALTH {status}: {passed}/{len(checks)} checks pass" + (f", {skipped} skipped" if skipped else "")]
    lines += [f"{c['status'].upper()} {c['check']}: {c['detail']}" for c in failed]
    lines += [f"NOTICE {c['check']} skipped: {c['detail']}" for c in checks if c["check"] in NOTICE_ON_SKIP
              and c["status"] in ("skip", "skipped")]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", help="print every check as JSON")
    args = parser.parse_args()
    summary = build()
    print(json.dumps(summary, indent=2) if args.json else brief(summary))
    return 1 if summary["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
