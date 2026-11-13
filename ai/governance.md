# ABAP Craft governance

Public repository: human-owned publication, AI-operated publishing. The workspace contract (`~/gh/AGENTS.md`) binds.

- `_posts/*.md` is the only article source; every publication set is EN/DE/ES with the same argument (English is the source unless the human picks another). A legacy URL is a `redirect_from` entry of its post.
- Presentation is the stock cayman theme and stock GitHub Pages plugins; our differences are overlays registered in `ai/upstreams.json`.
- `prompts/editorial-voice.md` is human-owned; change it only when the human asks.
- Never invent experiences, metrics, outcomes, opinions or patterns and attribute them to the author; the supplied source material is the authority for every claim.
- Anonymize everything: no real client/company/colleague names, system identifiers, internal URLs, tickets, payloads or credentials. Generic names (`ZXX_*`, `SYSTEM_A`, `TX01`) are fine. Every post carries the visible `class="note"` protection note.
- Checks: `tools/health_check.py` (filenames, front matter, translations, protection note; run by the tests), `tools/jekyll_build.sh` (Docker build, `jekyll doctor`, html-proofer; daily), gitleaks in CI. Actions stay SHA-pinned, tokens read-only; pins move by hand (ai/upstreams.json).
- Publish without waiting; the human reviews after publication and corrects.
