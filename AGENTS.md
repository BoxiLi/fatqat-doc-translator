# Agent instructions for fatqat-doc-translator

This repository maintains the Simplified-Chinese translation of the FatQat
documentation. The English docs live upstream in spaceqat/fatqat; this repo
holds a synced English snapshot, a segment-level translation database, and
the build pipeline that publishes the Chinese RTD translation.

## What is source of truth (and what is not)

- `translations/**.yml` — THE source of truth. One file per English page;
  one entry per prose segment: `{id, en, zh, status}`.
- `upstream-docs/` + `UPSTREAM_COMMIT` — a machine-managed snapshot of
  upstream English docs. Never edit by hand; only `tools/sync_upstream.py`
  writes here.
- The Chinese page trees do not exist in this repo at all — they are rendered
  at build time. Never commit rendered `zh/` output.

## The standard update loop

1. `python tools/sync_upstream.py` — refresh the English snapshot and source pin.
   Even when the source is unchanged, finish any existing pending translations.
2. `python tools/translate.py extract` — register changed segments. Entries
   whose English changed become `status: pending`; their previous versions
   stay as `status: retired` in the same file.
3. Translate every `pending` entry: fill `zh:`, set `status: machine`.
   Follow `tools/TRANSLATE_PROMPT.md` (the prompt contract),
   `translations/STYLE.md` (style rules), and `translations/glossary.yml`
   (fixed terminology). When a retired entry's English overlaps the new
   English, reuse its `zh` phrasing — updates should read as minimal
   revisions, not fresh translations.
4. `python tools/translate.py check --require-complete` — must exit 0.
   Fix every error it reports; glossary warnings deserve a look but do not
   block.
5. Prepare the snapshot and database changes for review. Publish directly only
   when the maintainer has explicitly authorized publication for the run.
   Keep machine translations marked `machine`, even when publication is authorized.

## Hard rules

- NEVER modify `id:` or `en:` fields, entry order, or non-pending entries.
  Those belong to the extractor.
- `zh:` is one line. Inline Markdown passes through untouched: code spans,
  bold/italic, icon tokens, attribute lists `{...}`, `$...$` math, HTML.
  In `[text](destination)` translate only the text. In
  `` [`Name`][fatqat.Name] `` crossrefs translate nothing.
- Table-row entries (starting with `|`) keep the exact pipe structure:
  translate cell contents in place, never add or remove `|`.
- Code identifiers, gate names, and product names stay English with
  half-width spaces around them. Full-width punctuation in Chinese prose.
- Trust `translate.py check` over your own judgment — if it fails, the
  change is wrong, not the checker.
- Do not modify `tools/`, `overlay/`, or the workflows as part of a
  translation update. Toolchain changes are separate, human-reviewed work.
- Never force-push; never rewrite published history.

## Verifying a single file after editing

From the repo root:

```sh
python -c "import sys,yaml,pathlib; sys.path.insert(0,'tools'); import translate; p=pathlib.Path('translations/<FILE>'); d=yaml.safe_load(p.read_text(encoding='utf-8')); assert all(translate.segment_id(e['en'])==e['id'] for e in d); assert not [e for e in d if e['status']=='pending']; print(len(d),'ok')"
```

## Build (usually not the agent's job)

`.readthedocs.yaml` builds the site by cloning upstream at `UPSTREAM_COMMIT`
and injecting the translations (`tools/inject_build.py`). CI (`checks.yml`)
validates the database on every PR. If a build breaks after an upstream
toolchain change, that is a human/toolchain task — report it, do not attempt
sweeping fixes inside a translation PR.

## Versions and scheduling

`upstream.yml` identifies the canonical repository. `UPSTREAM_REF` and
`UPSTREAM_COMMIT` record the source for each translator branch. Main tracks
upstream main; a release branch keeps its release source pin. Do not replace
main with a release snapshot. Read ONBOARDING.md before configuring scheduling.
Recurring execution and automatic publication have not been enabled by the
current setup work. Never copy subscription credentials to public CI caches.
