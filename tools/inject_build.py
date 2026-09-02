"""Build the bilingual documentation site from an upstream clone.

Upstream owns the entire documentation toolchain (root mkdocs.yml, lifecycle
hooks, figure sources, executable tutorials, validators) and is single-locale
English. This repository owns the translations. Building therefore means:

1. clone upstream at the pinned commit and verify it matches upstream-docs/
2. append the language switcher to upstream's mkdocs.yml
3. build English exactly as upstream does (hooks generate and validate)
4. translate.py render writes docs/mkdocs/zh/ and tutorial-sources/zh/
5. build_zh_assets.py retargets upstream's tutorial builder at the zh trees
   and copies the language-neutral figures
6. build Chinese with overlay/mkdocs.zh.yml (INHERITs upstream's config)
7. assemble site/: en/ + zh/ + a root language-chooser page

If upstream restructures its toolchain, the guards here and in
build_zh_assets.py fail loudly instead of publishing a broken site.
"""

from __future__ import annotations

import argparse
import filecmp
import html
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PIN = REPO_ROOT / "UPSTREAM_COMMIT"

LOCALES = (("en", "English"), ("zh", "简体中文"))

ALTERNATE_BLOCK = """
# Injected by fatqat-doc-translator: header language selector.
extra:
  alternate:
    - name: English
      link: !ENV [FATQAT_EN_LINK, "/en/"]
      lang: en
    - name: 简体中文
      link: !ENV [FATQAT_ZH_LINK, "/zh/"]
      lang: zh
"""


def _run(command: list[str], **kwargs) -> None:
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def _remove_readonly(function, path, error) -> None:
    """Retry removal after clearing a Windows read-only file attribute."""

    del error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _clone_upstream(url: str, workdir: Path, commit: str) -> Path:
    clone = workdir / "upstream"
    if clone.exists():
        shutil.rmtree(clone, onexc=_remove_readonly)
    clone.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--quiet", str(clone)])
    _run(["git", "-C", str(clone), "remote", "add", "origin", url])
    _run(["git", "-C", str(clone), "fetch", "--depth", "1", "origin", commit])
    _run(["git", "-C", str(clone), "checkout", "--quiet", "FETCH_HEAD"])
    return clone


def _assert_layout(clone: Path) -> None:
    expected = (
        clone / "mkdocs.yml",
        clone / "docs" / "mkdocs" / "hooks.py",
        clone / "docs" / "mkdocs" / "tools" / "build_tutorials.py",
    )
    for path in expected:
        if not path.is_file():
            raise RuntimeError(
                f"upstream layout changed: {path.relative_to(clone)} missing; "
                "adapt inject_build.py"
            )


def _assert_snapshot_current(clone: Path) -> None:
    """The database was extracted against upstream-docs/; the clone must match."""

    pairs = (
        (REPO_ROOT / "upstream-docs" / "en", clone / "docs" / "mkdocs" / "en"),
        (
            REPO_ROOT / "upstream-docs" / "tutorial-sources" / "en",
            clone / "docs" / "mkdocs" / "tutorial-sources" / "en",
        ),
    )
    for snapshot, upstream in pairs:
        comparison = filecmp.dircmp(snapshot, upstream)
        stack = [comparison]
        while stack:
            node = stack.pop()
            if node.left_only or node.right_only or node.diff_files:
                raise RuntimeError(
                    "upstream-docs/ does not match the pinned upstream commit "
                    f"(first difference under {node.left}); run "
                    "tools/sync_upstream.py and re-extract before building"
                )
            stack.extend(node.subdirs.values())


def _append_alternate(clone: Path) -> None:
    config = clone / "mkdocs.yml"
    text = config.read_text(encoding="utf-8")
    if "\nextra:" in text or text.startswith("extra:"):
        raise RuntimeError(
            "upstream mkdocs.yml now defines extra:; merge the language "
            "switcher manually in inject_build.py"
        )
    config.write_text(text.rstrip() + "\n" + ALTERNATE_BLOCK, encoding="utf-8", newline="\n")


def _chooser_page() -> str:
    supported = json.dumps([code for code, _ in LOCALES])
    links = "\n".join(
        f'        <a href="{code}/" hreflang="{code}">{html.escape(label)}</a>'
        for code, label in LOCALES
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>FatQat documentation</title>
    <script>
      const supported = {supported};
      const preferred = (navigator.languages?.[0] || navigator.language || "en")
        .toLowerCase();
      const target = supported.find(
        locale => preferred === locale || preferred.startsWith(`${{locale}}-`)
      ) || "en";
      window.location.replace(new URL(`${{target}}/`, window.location.href));
    </script>
    <style>
      :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
      body {{ display: grid; min-height: 100vh; margin: 0; place-items: center; }}
      main {{ max-width: 36rem; padding: 2rem; text-align: center; }}
      nav {{ display: flex; flex-wrap: wrap; gap: 1rem; justify-content: center; }}
      a {{ border: 1px solid currentColor; border-radius: .5rem; padding: .7rem 1rem; }}
    </style>
  </head>
  <body>
    <main>
      <h1>FatQat documentation</h1>
      <p>Select a language if automatic redirection does not start.</p>
      <nav aria-label="Language selection">
{links}
      </nav>
    </main>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="directory for the built site")
    parser.add_argument(
        "--upstream-url",
        default="https://github.com/BoxiLi/fatqat.git",
        help="upstream repository URL or local path",
    )
    parser.add_argument(
        "--workdir",
        default=str(REPO_ROOT / ".build"),
        help="scratch directory for the upstream clone",
    )
    parser.add_argument("--site-url", default="", help="canonical base URL of the published site")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="assume upstream and its documentation dependencies are already installed",
    )
    args = parser.parse_args()

    commit = PIN.read_text(encoding="utf-8").strip()
    clone = _clone_upstream(args.upstream_url, Path(args.workdir), commit)
    _assert_layout(clone)
    _assert_snapshot_current(clone)
    _append_alternate(clone)
    shutil.copy2(REPO_ROOT / "overlay" / "mkdocs.zh.yml", clone / "mkdocs.zh.yml")

    python = sys.executable
    if not args.skip_install:
        _run([python, "-m", "pip", "install", str(clone)])
        _run(
            [python, "-m", "pip", "install", "-r",
             str(clone / "docs" / "mkdocs" / "requirements.txt"), "jieba"]
        )

    output = Path(args.output).resolve()
    if output.exists():
        shutil.rmtree(output, onexc=_remove_readonly)
    output.mkdir(parents=True)

    base_url = args.site_url.rstrip("/")
    environment = os.environ.copy()
    if base_url:
        environment["READTHEDOCS_CANONICAL_URL"] = f"{base_url}/en/"
        environment["FATQAT_ZH_SITE_URL"] = f"{base_url}/zh/"
        environment["FATQAT_EN_LINK"] = f"{base_url}/en/"
        environment["FATQAT_ZH_LINK"] = f"{base_url}/zh/"

    # English first: upstream's hooks generate figures and tutorials, fill the
    # execution caches, and validate the canonical content.
    _run(
        [python, "-m", "mkdocs", "build", "-f", "mkdocs.yml", "--strict",
         "-d", str(output / "en")],
        cwd=clone,
        env=environment,
    )

    render_env = environment.copy()
    render_env["FATQAT_MKDOCS_ROOT"] = str(clone / "docs" / "mkdocs")
    render_env["FATQAT_TRANSLATIONS_ROOT"] = str(REPO_ROOT / "translations")
    _run(
        [python, str(REPO_ROOT / "tools" / "translate.py"), "render",
         "--out-root", str(clone / "docs" / "mkdocs")],
        cwd=REPO_ROOT,
        env=render_env,
    )
    _run(
        [python, str(REPO_ROOT / "tools" / "build_zh_assets.py"), "--clone", str(clone)],
        cwd=clone,
        env=environment,
    )
    _run(
        [python, "-m", "mkdocs", "build", "-f", "mkdocs.zh.yml", "--strict",
         "-d", str(output / "zh")],
        cwd=clone,
        env=environment,
    )

    (output / "index.html").write_text(_chooser_page(), encoding="utf-8", newline="\n")
    (output / ".nojekyll").touch()
    print("inject_build: site written to", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
