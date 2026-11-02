# ABAP Craft

Human-owned publication · AI-operated publishing system · human-facing output.

ABAP Craft publishes practical SAP/ABAP architecture lessons from real experience. The public artifact is optimized for readers; the repository control plane is optimized for reliable AI operation and human audit.

Website: `https://nor001.github.io/ABAP_Keyflow/` (the URL keeps the former name ABAP Keyflow so published links stay stable).

## Publication plane

- `_posts/` — canonical article sources.
- `_layouts/` — article/redirect presentation.
- `index.html` and `posts.md` — public navigation/listing.
- `posts/` — legacy redirects only.
- `prompts/editorial-voice.md` — human-owned voice/positioning guidance.
- `prompts/templates/` — reusable article/front-matter input shapes.

## Human inspection

Articles, pages and Git diffs remain directly auditable. AI operating rules live in `ai/governance.md`; routing lives in `ai/repo-map.json`.

The author owns lived experience, architectural position, editorial voice and correction after publication. AI must never fabricate those inputs.
