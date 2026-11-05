# ABAP Craft AI Governance

## Identity

ABAP Craft is a human-owned publication, an AI-operated publishing system, and a human-facing public artifact.

AI-first optimization applies to the control plane. It must not make the repository unauditable, non-deterministic, unrecoverable, or dependent on a specific AI provider. Public output remains optimized for human readers because readers are the consumer of the artifact plane.

## Ownership

Human-owned:
- lived/project experience and factual claims about that experience;
- architectural position, opinions and conclusions attributed to the author;
- editorial voice and materially consequential positioning;
- correcting a published article after the fact when a claim or positioning is not theirs.

AI-operated:
- article structure and draft implementation after intent/evidence is supplied;
- front matter, translations and translation parity;
- internal links, redirects, formatting and publication mechanics;
- repository navigation, maintenance, validation and control-plane consistency.

## Routing

`routing` in `ai/repo-map.json` names the paths each task opens; open templates and layouts only as the task requires.

- Content work starts from the source material supplied/approved by the human; that material is the authority for every claim.
- Translation work treats the approved source-language article as the claims authority and preserves argument and technical meaning. English is the default source language unless the human explicitly chooses another workflow.
- `_posts/*.md` is the canonical article content. A legacy URL is a `redirect_from` entry of its post (jekyll-redirect-from); never duplicate article bodies elsewhere.
- Presentation is the stock cayman theme and the stock GitHub Pages plugins (jekyll-seo-tag, jekyll-feed, jekyll-sitemap, jekyll-redirect-from); our differences are overlays registered in `ai/upstreams.json`, never a hand-written copy of what a plugin or the theme renders.
- `prompts/editorial-voice.md` is human-owned editorial input that is costly to reconstruct, not a second governance surface; change it only when the human explicitly asks.
- `prompts/templates/` holds reusable input/front-matter shapes, not policy.

Do not create a second source of truth for article content or publishing policy.

## Evidence discipline

Never invent and attribute to the author:
- experiences or production situations;
- metrics or customer outcomes;
- opinions or architectural conclusions;
- technical patterns the source material does not support.

If a stronger claim would require unsupported evidence, omit it or request human input. Repository evidence outranks prior conversation memory.

Protect production/customer information: no real client/company names, live system identifiers, internal URLs, credentials, private payloads, ticket identifiers, colleague names or other identifying details unless explicitly safe and intended for publication. No passwords, tokens, private keys or private `.env` belong in the repository. Public URLs intentionally used by the publication are allowed.

Generic/anonymized examples such as `ZXX_*`, `SYSTEM_A`, `SYSTEM_B`, `MIDDLEWARE`, `TX01` and `TX02` are acceptable when they cannot identify a real environment.

## Publication invariants

- Published article sets maintain EN/DE/ES variants with the same architectural argument.
- Public URLs should remain stable when practical.
- Filenames and slugs, front matter, layout, translation links, the visible production-protection note and `redirect_from` sources are specified and enforced by `tools/health_check.py` (front matter read with PyYAML); that every link of the built site resolves, translation pills and hreflang alternates included, is checked by html-proofer in `tools/jekyll_build.sh`, after `jekyll doctor` fails on two files sharing one URL.
- Do not machine-score editorial quality; validate mechanical publication contracts only.
- Secrets are scanned by gitleaks, not by `tools/health_check.py`: locally by the workspace's shared pre-commit hook on every staged tree, and in CI by `.github/workflows/health-check.yml` on every push and pull request.
- GitHub Actions are pinned by full commit SHA (version in a trailing comment), every workflow token is read-only unless a job declares more, and Dependabot (`.github/dependabot.yml`) bumps the pins by pull request.

## Completion

Content and mechanical changes alike are merged, pushed and published without waiting once validation passes; preserve author intent and keep every published text anonymized. The human reviews after publication and corrects.

Run the `validators` in `ai/repo-map.json` before completion; the last builds the site in Docker, and the GitHub Pages workflow deploys the public artifact.
