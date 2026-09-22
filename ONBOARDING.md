# Set up Chinese FatQat documentation

The English Read the Docs project is `fatqat`:
https://fatqat.readthedocs.io/en/latest/.

The local build and version pinning are implemented. The replacement scheduler
and automatic publisher are not enabled yet. The existing `sync.yml` predates
this setup; do not use its subscription-credential cache for this public repo.

## Hosting

1. Import `BoxiLi/fatqat-doc-translator` into Read the Docs as `fatqat-zh`
   (or another available project name).
2. Set its language to Simplified Chinese and its default branch to `main`.
3. In the parent `fatqat` project's Translations settings, add the Chinese project.
4. Activate `latest`. To publish releases automatically, add an automation rule
   for branches with semantic-version names: Activate version.
5. Enable PR previews if review builds are wanted. Do not publish `sync/*`
   staging branches as release versions.

RTD supplies the canonical language/version URL. The build puts Chinese HTML
straight in `$READTHEDOCS_OUTPUT/html`; there is no extra `/zh/` directory.
The English language link points to the corresponding upstream version.
A `translation-source.json` file records the upstream ref and exact commit.

Official RTD references:
- https://docs.readthedocs.com/platform/stable/localization.html
- https://docs.readthedocs.com/platform/stable/versions.html
- https://docs.readthedocs.com/platform/stable/automation-rules.html

## Subscription-based translation

For a maintainer with a Codex subscription and no API key, a Codex desktop
scheduled task can work in this repository using the signed-in account.
The computer must remain on and the app running. Connecting the GitHub repository
to Codex does not itself schedule translation jobs.

Before enabling recurring execution, approve its cadence and whether it can
push validated updates to this repository's `main` and version branches.
Keep account credentials local. Do not put `auth.json` in GitHub Actions caches.
No translation credentials are needed on Read the Docs.

For an always-on GitHub Actions runner, API authentication is a separate option.
The current local changes do not enable such a workflow or configure secrets.

Official OpenAI references:
- https://learn.chatgpt.com/docs/automations
- https://learn.chatgpt.com/docs/non-interactive-mode#authenticate-in-automation

## Update latest

Run in a clean checkout with a dedicated Python 3.12+ environment:

```sh
python -m pip install -r requirements.txt
python tools/sync_upstream.py
python tools/translate.py extract
```

Then use Codex with `tools/TRANSLATE_PROMPT.md` to translate pending entries.
The renderer can fall back to English during local previews; a complete update
must pass these checks before publication:

```sh
python tools/translate.py check --require-complete
python -m unittest discover -s tests -v
python tools/inject_build.py --output site --require-complete
```

The full build installs the pinned upstream documentation dependencies and
executes its tutorials. Use a dedicated environment, not another FatQat
checkout's environment. `--skip-install` is available after installation.

## Versioned documentation

`main` in this repository tracks the latest upstream `main`. List available
release tags with `python tools/list_versions.py`. No FatQat release tags existed
when this setup was prepared.

For an upstream release such as `v0.1.0`, create a translator branch with exactly
that name, run `python tools/sync_upstream.py --ref v0.1.0`, extract and translate,
then validate before publishing that branch. Do this in a clean, separate checkout.
Never run a release sync on the translator's `main` branch.

Each version branch keeps its own `UPSTREAM_REF`, `UPSTREAM_COMMIT`, snapshot, and
translation database. Builds fetch that exact commit, not the current upstream
branch or a potentially moved tag. Translation corrections can update the version
branch while preserving its upstream pin. New releases get new branches.
RTD can then expose `latest`, each version, and its automatic `stable` alias.
