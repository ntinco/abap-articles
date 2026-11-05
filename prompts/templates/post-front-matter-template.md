# Jekyll Post Front Matter Template

Use this template for canonical post files under `_posts/`.

```yaml
---
layout: article
title: "<localized title>"
date: YYYY-MM-DD 00:00:00 +0000
lang: en
categories: [architecture]
description: "<short architecture-focused summary>"
back_label: "Back to ABAP Craft"
discuss_label: "Discuss this article"
comments_intro: "Comments are powered by GitHub Discussions."
redirect_from:
  - /posts/en-<slug>.html
translations:
  - lang: en
    label: English
    url: /architecture/YYYY/MM/DD/en-<slug>/
  - lang: de
    label: Deutsch
    url: /architektur/YYYY/MM/DD/de-<slug>/
  - lang: es
    label: Espanol
    url: /arquitectura/YYYY/MM/DD/es-<slug>/
---
```

Notes:

- Keep filenames lowercase and ASCII-only.
- Keep `lang` and `translations` fully aligned.
- `redirect_from` is optional: legacy URLs that must keep working (jekyll-redirect-from).
- `description` feeds the page, Open Graph and Twitter meta (jekyll-seo-tag).
- Localize the title, category, description, labels, and intro strings for DE and ES versions.
