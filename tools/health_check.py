#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml  # PyYAML, pinned in tools/requirements.txt

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


def front_matter(text: str) -> tuple[dict, str]:
    """The Jekyll front matter as PyYAML reads it, and the body; ({}, text) without a closed `---` block."""
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1])
    if data is None:
        return {}, parts[2]
    if not isinstance(data, dict):
        raise yaml.YAMLError("front matter must be a mapping")
    return data, parts[2]


def read_post(path: Path, problems: list[str]) -> tuple[dict, str] | None:
    """The post's front matter and body, or None after recording why its YAML does not parse."""
    try:
        return front_matter(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problems.append(f"{path.name}: front matter is not valid YAML: {str(exc).splitlines()[0]}")
        return None


def as_list(value: object) -> list:
    """A YAML value Jekyll accepts as a list or a single item (`redirect_from`, `translations`)."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


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
        by_date[day].add(filename_lang)
        post = read_post(path, problems)
        if post is None:
            continue
        fm, body = post
        for key in ("layout", "title", "date", "lang", "categories", "description", "translations"):
            if key not in fm:
                problems.append(f"{path.name}: missing front matter {key}")
        lang = fm.get("lang")
        if lang != filename_lang:
            problems.append(f"{path.name}: lang {lang!r} does not match filename")
        if fm.get("layout") != "article":
            problems.append(f"{path.name}: layout must be article")
        translated = {item.get("lang") for item in as_list(fm.get("translations")) if isinstance(item, dict)}
        for required_lang in sorted(LANGS - translated):
            problems.append(f"{path.name}: translations missing {required_lang}")
        if 'class="note"' not in body:
            problems.append(f"{path.name}: missing visible production-protection note")
    for day, langs in by_date.items():
        if langs != LANGS:
            problems.append(f"{day}: publication set must contain EN/DE/ES, found {sorted(langs)}")
    return result("post_contracts", problems)


def redirect_contracts(root: Path) -> dict[str, object]:
    """Each legacy URL is a site-local `redirect_from` entry of one canonical post, never a post's own URL.

    A post's own URL is the one its `translations` declare; html-proofer on the built site (tools/jekyll_build.sh)
    checks that every declared URL is where Jekyll put the post.
    """
    problems: list[str] = []
    posts: list[tuple[Path, dict]] = []
    for path in sorted((root / "_posts").glob("*.md")):
        post = read_post(path, problems)
        if post is not None:
            posts.append((path, post[0]))
    canonical = {str(item.get("url")) for _, fm in posts for item in as_list(fm.get("translations"))
                 if isinstance(item, dict) and item.get("url")}
    seen: dict[str, str] = {}
    for path, fm in posts:
        for source in map(str, as_list(fm.get("redirect_from"))):
            if not source.startswith("/") or source.startswith("//"):
                problems.append(f"{path.name}: redirect_from {source!r} must be a site-local path")
            elif source in canonical:
                problems.append(f"{path.name}: redirect_from {source} is a canonical post URL")
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
