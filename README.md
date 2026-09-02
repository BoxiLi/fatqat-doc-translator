# fatqat-doc-translator

Simplified-Chinese documentation for [FatQat](https://github.com/BoxiLi/fatqat),
maintained as a segment-level translation database that tracks the upstream
English docs automatically. The published site serves `/en/` and `/zh/` side
by side with a header language switcher and a browser-language redirect at
the root.

The upstream repository stays entirely English and needs no knowledge of this
one. This repository never forks the upstream documentation toolchain: it
holds only the translations plus thin sync/build glue, and builds by cloning
upstream at a pinned commit and injecting the translation layer into it.

## How it works

```
BoxiLi/fatqat ──(daily sync of docs only)──▶ upstream-docs/ snapshot + UPSTREAM_COMMIT pin
                                                  │
                                                  ▼ translate.py extract
                                       translations/  (source of truth)
                                                  │  pending segments auto-translated,
                                                  │  PR opened for human review
                                                  ▼ merge
Read the Docs build: clone upstream @ pin ── build en (upstream mkdocs + hooks) ── render zh + retarget upstream tutorial builder ── build zh ──▶ /en/ + /zh/
```

| Path | Role |
| --- | --- |
| `upstream-docs/` | Committed snapshot of upstream's English sources (`en/`, `tutorial-sources/en/`, `gallery.yml`). Updated only when the docs actually change. |
| `UPSTREAM_COMMIT` | The upstream commit the snapshot (and every build) is pinned to — the last commit that changed the docs. |
| `translations/` | The translation database: one YAML file per English page, one entry per prose segment (`id` = hash of the English text, `en`, `zh`, `status: pending → machine → reviewed`). Plus `glossary.yml` (fixed terminology) and `STYLE.md` (binding style contract). |
| `tools/translate.py` | Core tool: `extract` registers new/changed English segments, `render --out-root` splices translations into byte-copies of the English sources, `check` validates everything, `find` locates an entry by text. Reads `upstream-docs/` standalone, or an upstream clone via `FATQAT_MKDOCS_ROOT`. |
| `tools/sync_upstream.py` | Refreshes the snapshot; reports `changed=true/false`. |
| `tools/build_zh_assets.py` | Retargets upstream's single-locale tutorial builder at the rendered zh trees (paths + gallery strings) and copies the language-neutral figures. Runs between the English and Chinese builds. |
| `tools/inject_build.py` | Clones upstream at the pin, builds English with upstream's own root `mkdocs.yml` + hooks, renders the zh trees, drives `build_zh_assets.py`, builds Chinese from `overlay/mkdocs.zh.yml`, and assembles the bilingual site. Used by `.readthedocs.yaml`. |
| `tools/api_translate.py` | Fallback translation engine for any OpenAI-compatible endpoint. |
| `overlay/` | `mkdocs.zh.yml` (the zh MkDocs config, translated nav) and `gallery.zh.yml` (zh gallery strings), injected at build time. |
| `.github/workflows/sync.yml` | Daily: sync docs → extract → auto-translate pending → open a review PR. Exits immediately when the docs did not change. |
| `.github/workflows/checks.yml` | PR/main validation of the database. |
| `AGENTS.md` | Standing instructions for coding agents (Codex, Claude Code): the update loop, the hard rules, and what an agent must never touch. Auto-loaded by Codex when connected to this repo. |

## Key properties

- **Cost is linear in what changed.** Segments are keyed by a hash of their
  English text; an upstream typo fix re-translates exactly one segment and
  leaves every other entry — including all hand-tuning — byte-for-byte
  untouched.
- **English never blocks on translation.** Untranslated segments render as
  English on the site; `check` reports them.
- **Structure is guaranteed, not promised.** Rendering splices translations
  into byte-copies of the English files, so upstream's strict validators
  (page/link/code/figure parity) pass by construction. `check` additionally
  verifies a byte-exact identity round-trip of the segmentation, link
  destinations inside translations, table-row structure, and glossary use.
- **Machine output is always reviewed.** The sync workflow opens a PR; a
  human merges. Fine-tuning is editing a `zh:` field — status `reviewed`
  marks it human-approved.

## Day-to-day

- **Polish a translation**: find the entry
  (`python tools/translate.py find "some text"`), edit its `zh:` field, set
  `status: reviewed`, commit (directly or via PR). The next RTD build picks
  it up.
- **The daily sync PR**: review the machine translations it contains
  (everything it touched is `status: machine`), adjust wording in place,
  merge. Merging triggers the RTD build.
- **Build locally**:
  `python tools/inject_build.py --output site` (add `--skip-install` if the
  upstream package and docs requirements are already installed in the active
  environment). The full build executes upstream's tutorials on first run.
- **Validate locally**: `python -m pip install pyyaml`, then
  `python tools/translate.py check`.

## Translation engines

The sync workflow selects an engine through the `TRANSLATE_ENGINE` repository
variable (default `codex`):

| Engine | Credential | Notes |
| --- | --- | --- |
| `codex` | `CODEX_AUTH_JSON` secret (from `codex login` on the plan holder's machine) | Uses a ChatGPT/Codex subscription. The workflow seeds the credential only when missing and caches `~/.codex` so refreshed tokens persist; the daily run keeps the token alive. |
| `claude` | `CLAUDE_CODE_OAUTH_TOKEN` secret (from `claude setup-token`, valid one year) | Uses a Claude Pro/Max subscription. |
| `api` | `TRANSLATE_API_KEY` secret + `TRANSLATE_API_BASE` / `TRANSLATE_MODEL` variables | Any OpenAI-compatible endpoint, pay per token. |

With no credential configured the pipeline still works: sync PRs open with
segments left `pending`, and the site falls back to English for them.

See `ONBOARDING.md` for the one-time setup steps (credentials, Read the
Docs, ownership).
