from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import health_check


class HealthCheckTests(unittest.TestCase):
    def test_repository_validates_itself(self):
        summary = health_check.build(health_check.ROOT)
        self.assertEqual(summary["structural_status"], "pass", summary["checks"])

    def test_post_requires_translation_symmetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "_posts"
            posts.mkdir()
            fm = """---
layout: article
title: Test
date: 2026-01-01 00:00:00 +0000
lang: en
categories: [architecture]
description: Test
translations:
  - lang: en
    url: /architecture/2026/01/01/en-test/
---
<p class=\"note\">safe</p>
"""
            (posts / "2026-01-01-en-test.md").write_text(fm, encoding="utf-8")
            self.assertEqual(health_check.post_contracts(root)["status"], "fail")

    def test_local_redirect_pages_and_layout_are_forbidden(self):
        for surface in ("posts", "_layouts/redirect.html"):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / surface).parent.mkdir(parents=True, exist_ok=True)
                (root / surface).mkdir() if surface == "posts" else (root / surface).write_text("x", encoding="utf-8")
                self.assertEqual(health_check.forbidden_surfaces(root)["detail"], [surface])

    def test_provider_specific_control_surface_is_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".github"
            path.mkdir()
            (path / "copilot-instructions.md").write_text("duplicate", encoding="utf-8")
            self.assertEqual(health_check.forbidden_surfaces(root)["status"], "fail")

    def test_repo_map_requires_existing_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ai").mkdir()
            (root / "ai/repo-map.json").write_text(json.dumps({"schema_version": "1.0", "routing": {"article": ["_posts/"]}}), encoding="utf-8")
            self.assertEqual(health_check.repo_map(root)["status"], "fail")


def article(lang: str, day: str = "2026-01-01", category: str = "architecture", **overrides: str) -> str:
    fields = {"layout": "article", "title": "Test", "date": f"{day} 00:00:00 +0000", "lang": lang,
              "categories": f"[{category}]", "description": "Test", **overrides}
    lines = [f"{key}: {value}" for key, value in fields.items()]
    lines += ["translations:"] + [f"  - lang: {other}\n    url: /{category}/{day.replace('-', '/')}/{other}-test/"
                                  for other in ("en", "de", "es")]
    return "---\n" + "\n".join(lines) + "\n---\n<p class=\"note\">safe</p>\n"


class FrontMatterTests(unittest.TestCase):
    def test_front_matter_is_read_as_yaml(self):
        self.assertEqual(health_check.front_matter('---\ntitle: "A"\ncategories: [x, y]\n---\nbody\n'),
                         ({"title": "A", "categories": ["x", "y"]}, "body\n"))

    def test_unclosed_or_absent_front_matter_is_all_body(self):
        for text in ("title: A\nbody\n", "---\ntitle: A\nbody\n"):
            self.assertEqual(health_check.front_matter(text), ({}, text))

    def test_invalid_yaml_is_a_problem_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_posts").mkdir()
            (root / "_posts/2026-01-01-en-test.md").write_text("---\ntitle: [unclosed\n---\nbody\n", encoding="utf-8")
            for check in (health_check.post_contracts, health_check.redirect_contracts):
                detail = check(root)["detail"]
                self.assertTrue(any("front matter is not valid YAML" in d for d in detail), detail)


class PostContractTests(unittest.TestCase):
    def problems(self, posts: dict[str, str]) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_posts").mkdir()
            for name, text in posts.items():
                (root / "_posts" / name).write_text(text, encoding="utf-8")
            detail = health_check.post_contracts(root)["detail"]
            return [] if detail == "ok" else detail

    def complete_set(self, **overrides: str) -> dict[str, str]:
        return {f"2026-01-01-{lang}-test.md": article(lang) for lang in ("en", "de", "es")} | overrides

    def test_complete_publication_set_passes(self):
        self.assertEqual(self.problems(self.complete_set()), [])

    def test_each_post_rule_fails_on_its_own(self):
        en = "2026-01-01-en-test.md"
        cases = {
            "filename must be date-lang-lowercase-ascii-slug": {"2026-01-01-en-Bad_Slug.md": article("en")},
            "missing front matter description": {en: article("en").replace("description: Test\n", "")},
            "lang 'de' does not match filename": {en: article("de")},
            "layout must be article": {en: article("en", layout="page")},
            "translations missing es": {en: article("en").replace("  - lang: es\n", "")},
            "missing visible production-protection note": {en: article("en").replace(' class="note"', "")},
        }
        for phrase, override in cases.items():
            with self.subTest(phrase):
                problems = self.problems(self.complete_set(**override))
                self.assertTrue(any(phrase in problem for problem in problems), problems)

    def test_publication_set_needs_every_language_and_some_post(self):
        posts = self.complete_set()
        del posts["2026-01-01-es-test.md"]
        self.assertEqual(self.problems(posts), ["2026-01-01: publication set must contain EN/DE/ES, found ['de', 'en']"])
        self.assertEqual(self.problems({}), ["no canonical posts found"])


class RedirectContractTests(unittest.TestCase):
    def problems(self, sources: list[str], post: str = article("en"), other: list[str] | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_posts").mkdir()
            block = "redirect_from:\n" + "".join(f"  - {s}\n" for s in sources) if sources else ""
            (root / "_posts/2026-01-01-en-test.md").write_text(post.replace("translations:\n", block + "translations:\n"), encoding="utf-8")
            if other is not None:
                block = "redirect_from:\n" + "".join(f"  - {s}\n" for s in other)
                (root / "_posts/2026-01-01-de-test.md").write_text(article("de").replace("translations:\n", block + "translations:\n"), encoding="utf-8")
            detail = health_check.redirect_contracts(root)["detail"]
            return [] if detail == "ok" else detail

    def test_site_local_legacy_urls_pass(self):
        self.assertEqual(self.problems(["/posts/en-test.html", '"/old/"']), [])

    def test_comment_after_the_key_is_ignored(self):
        post = article("en").replace("translations:\n", "redirect_from:  # legacy URLs\n  - /old/\ntranslations:\n")
        self.assertEqual(self.problems([], post, other=["/old/"]),
                         ["2026-01-01-en-test.md: redirect_from /old/ already redirects to 2026-01-01-de-test.md"])

    def test_scalar_redirect_source_is_checked(self):
        post = article("en").replace("translations:\n", "redirect_from: old.html\ntranslations:\n")
        self.assertEqual(self.problems([], post), ["2026-01-01-en-test.md: redirect_from 'old.html' must be a site-local path"])

    def test_redirect_source_must_be_site_local(self):
        for source in ("https://example.com/old/", "old.html", "//example.com/old/"):
            with self.subTest(source=source):
                self.assertEqual(self.problems([source]),
                                 [f"2026-01-01-en-test.md: redirect_from {source!r} must be a site-local path"])

    def test_redirect_source_cannot_be_a_post_url(self):
        for source in ("/architecture/2026/01/01/en-test/", "/architecture/2026/01/01/de-test/"):
            with self.subTest(source=source):
                self.assertEqual(self.problems([source], other=[]),
                                 [f"2026-01-01-en-test.md: redirect_from {source} is a canonical post URL"])

    def test_redirect_source_belongs_to_one_post(self):
        self.assertEqual(self.problems(["/old/"], other=["/old/"]),
                         ["2026-01-01-en-test.md: redirect_from /old/ already redirects to 2026-01-01-de-test.md"])


class BriefTests(unittest.TestCase):
    def test_brief_output_lists_only_failures(self):
        summary = {"failure_count": 1, "checks": [
            {"check": "a", "status": "pass", "detail": "ok"},
            {"check": "b", "status": "fail", "detail": "broken"}]}
        self.assertEqual(health_check.brief(summary), "HEALTH FAIL: 1/2 checks pass\nFAIL b: broken")

    def test_brief_output_counts_skipped_checks_without_listing_them(self):
        summary = {"failure_count": 0, "checks": [
            {"check": "a", "status": "pass", "detail": "ok"},
            {"check": "shell_syntax", "status": "skip", "detail": "bash not found"}]}
        self.assertEqual(health_check.brief(summary), "HEALTH PASS: 1/2 checks pass, 1 skipped")

    def test_skipped_workspace_contract_is_reported_as_a_notice(self):
        with tempfile.TemporaryDirectory() as temp:
            check = health_check.workspace_contract(Path(temp), Path(temp) / "agent-core/shared/workspace_contract.py")
        self.assertEqual(check["status"], "skip")
        summary = {"failure_count": 0, "checks": [{"check": "a", "status": "pass", "detail": "ok"}, check]}
        self.assertEqual(health_check.brief(summary).splitlines(),
                         ["HEALTH PASS: 1/2 checks pass, 1 skipped", f"NOTICE workspace_contract skipped: {check['detail']}"])

    def test_workspace_contract_runs_agent_cores_check(self):
        with tempfile.TemporaryDirectory() as temp:
            shared = Path(temp) / "workspace_contract.py"
            shared.write_text("def problems(root):\n    return [f'broken {root.name}']\n")
            check = health_check.workspace_contract(Path(temp) / "repo", shared)
        self.assertEqual((check["status"], check["detail"]), ("fail", ["broken repo"]))


if __name__ == "__main__":
    unittest.main()
