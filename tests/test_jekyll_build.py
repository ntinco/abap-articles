"""Cheap checks of tools/jekyll_build.sh that need no Docker: it parses, passes shellcheck, mounts read-only and takes the image tag from the workflow pin."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "jekyll_build.sh"


class JekyllBuildTests(unittest.TestCase):
    def test_script_parses(self):
        result = subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck not installed")
    def test_script_passes_shellcheck(self):
        result = subprocess.run(["shellcheck", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_source_is_mounted_read_only_and_never_deployed(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('-v "$root":/src:ro', text)
        self.assertIn("test -f /src/_config.yml", text)
        self.assertNotIn("git push", text)

    def test_image_tag_follows_the_workflow_pin(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"jekyll-build-pages:v\d")
        tag_line = next(line for line in text.splitlines() if line.startswith("tag=$("))
        workflow = SCRIPT.parents[1] / ".github" / "workflows" / "jekyll-gh-pages.yml"
        result = subprocess.run(["sh", "-c", f'root={SCRIPT.parents[1]}; {tag_line}; echo "$tag"'],
                                capture_output=True, text=True)
        pinned = re.search(r"jekyll-build-pages@[0-9a-f]{40} # (v[\d.]+)", workflow.read_text(encoding="utf-8"))
        self.assertIsNotNone(pinned)
        self.assertEqual(result.stdout.strip(), pinned.group(1))


if __name__ == "__main__":
    unittest.main()
