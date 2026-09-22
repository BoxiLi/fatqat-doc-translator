# FatQat Chinese documentation

This repository translates documentation from `spaceqat/fatqat` into Simplified
Chinese and builds a Chinese Read the Docs translation of the English `fatqat`
project. English sources stay upstream.

Translations live in `translations/` as segment records (`id`, `en`, `zh`, `status`).
The extractor reuses unchanged translations. New English text becomes `pending`;
Codex fills the Chinese text and marks it `machine`. Only a human marks an entry
`reviewed`. Missing translations remain English in local previews.

## Build and validate

Use a dedicated Python 3.12+ virtual environment:

```sh
python -m pip install -r requirements.txt
python tools/translate.py check
python -m unittest discover -s tests -v
python tools/inject_build.py --output site
```

The build clones the upstream commit in `UPSTREAM_COMMIT`, verifies its source
snapshot, builds upstream assets and executable tutorials, then renders and
builds Chinese documentation. It reuses tutorial caches on repeated local builds.
Add `--require-complete` to reject untranslated segments before publishing.
No translation service is called during an RTD build.

Translated headings preserve their English anchors. Navigation and tutorial
categories are generated from the pinned source and use the same segment database.
Examples remain executable and unchanged. Generated Python API docstrings and
plot labels currently remain English.
Every Chinese page includes an LLM translation notice above its main content,
with a link to this repository's GitHub Issues for translation feedback.

## Sources and versions

- `upstream.yml`: canonical repository, main ref, release-tag pattern, English URL.
- `UPSTREAM_REF` / `UPSTREAM_COMMIT`: exact source version for this branch.
- `upstream-docs/`: machine-managed snapshot; update with `tools/sync_upstream.py`.
- `translations/`: authored translation database and terminology/style rules.
- `tools/`: extraction, validation, rendering, and build tools.
- `overlay/mkdocs.zh.yml`: minimal Chinese theme settings; navigation is generated.
- `overlay/assets/`: Chinese typography adjustments; homepage structure and assets
  continue to use the pinned upstream templates.

`main` is the latest documentation. Release branches use the upstream release
name and keep a separate source pin and translations. Read the Docs handles the
language/version URLs; this build publishes Chinese directly at the version root.

See [ONBOARDING.md](ONBOARDING.md) for RTD configuration, version handling, and the
subscription-based scheduling proposal. Recurring execution and automatic
publication are awaiting explicit approval; the legacy GitHub sync workflow has
not been replaced or enabled by this setup work.
