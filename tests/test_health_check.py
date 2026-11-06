from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import health_check

POST = """---
layout: article
title: Test
date: 2026-01-01 00:00:00 +0000
lang: {lang}
categories: [architecture]
description: Test
translations:
  - lang: en
  - lang: de
  - lang: es
---
<p class="note">safe</p>
"""


class HealthCheckTests(unittest.TestCase):
    def write(self, root: Path, langs=("en", "de", "es"), text=POST) -> None:
        (root / "_posts").mkdir(exist_ok=True)
        for lang in langs:
            (root / f"_posts/2026-01-01-{lang}-test.md").write_text(text.format(lang=lang), encoding="utf-8")

    def test_repository_validates_itself(self):
        self.assertEqual(health_check.problems(), [])

    def test_complete_publication_set_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp))
            self.assertEqual(health_check.problems(Path(tmp)), [])

    def test_missing_language_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp), langs=("en", "de"))
            self.assertTrue(any("EN/DE/ES" in p for p in health_check.problems(Path(tmp))))

    def test_missing_anonymization_note_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp), text=POST.replace('<p class="note">safe</p>', "body"))
            self.assertEqual(len(health_check.problems(Path(tmp))), 3)

    def test_invalid_yaml_is_a_problem_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp), text="---\ntitle: [unclosed\n---\nbody\n")
            self.assertTrue(all("not valid YAML" in p for p in health_check.problems(Path(tmp))))


if __name__ == "__main__":
    unittest.main()
