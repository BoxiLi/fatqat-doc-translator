# Set up Chinese FatQat documentation

The English Read the Docs project is `fatqat`:
https://fatqat.readthedocs.io/en/latest/.

The local build and version pinning are implemented. The replacement scheduler
and automatic publisher are not enabled yet. The existing `sync.yml` predates
this setup; do not use its subscription-credential cache for this public repo.

## Hosting

1. The Chinese RTD project is `fatqat-translations`, linked to
   `BoxiLi/fatqat-doc-translator`.
2. Set its language to Simplified Chinese and its default branch to `main`.
3. In the parent `fatqat` project's Translations settings, add the Chinese project.
4. Activate `latest` and the release tags you want to publish. Match the English
   project's version slugs: it serves the `v0.1.x` branch as `stable`, alongside
   `v0.1.0a1` and `v0.1.0a2`. Configure the Chinese `stable` version to track the
   same release branch.
5. Enable PR previews if review builds are wanted. Do not publish `sync/*`
   staging branches as release versions.

RTD supplies the canonical language/version URL. The build puts Chinese HTML
straight in `$READTHEDOCS_OUTPUT/html`; there is no extra `/zh/` directory.
The RTD flyout lists languages and versions. Source versions that include the
Material language menu also retain that menu and its current-version links.
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

Mirror upstream's release history: `main` tracks upstream `main`, `v0.1.x`
tracks the release branch, and translator tags `v0.1.0a1` and `v0.1.0a2`
pin the corresponding published source versions. RTD uses the same version
slugs in both language projects. Alpha tags do not automatically create a
`stable` alias; English explicitly serves `v0.1.x` as `stable`, so configure
that same mapping in the Chinese project.

Prepare releases in upstream ancestry order. Start from the existing translation
database, sync the oldest missing release, and translate only pending segments.
The extractor reuses exact English segments, including retired translations.
Advance the release branch to the next source version and repeat; do not translate
unchanged text again. If a release tag and branch point to the same upstream
commit, share their translation and build validation.

Every snapshot records its own `UPSTREAM_REF`, `UPSTREAM_COMMIT`, English source,
and translation database. Set `upstream.yml`'s `ref` to the same source ref so the
default sync command stays on that release. The build always uses the exact
commit pin, even after the upstream branch advances. Never run a release sync
on translator `main`.

For an existing release branch, use a clean, separate checkout:

```sh
python tools/sync_upstream.py --ref v0.1.x
python tools/translate.py extract
# Translate pending entries, then run the validation commands above.
```

For a new release tag, sync its exact upstream tag, validate, and commit before
creating the matching translator tag. Then restore the moving branch's sync ref.
Published tags remain immutable. Apply later translation corrections to the
maintained release branch, carrying the same correction across identical English
segments on other maintained branches. Do not merge another version's source pin
or entire snapshot just to share a wording correction.

Push the branch and tags after validation. In each RTD project's Versions page,
activate the corresponding tag versions and map `stable` to `v0.1.x`. One
Chinese project serves all of them;
no additional project is needed per release. These steps do not enable scheduled
release updates.
