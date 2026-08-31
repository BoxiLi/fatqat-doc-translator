"""Build the bilingual documentation site from an upstream clone.

The upstream repository owns the entire documentation toolchain (manage.py,
figure sources, executable tutorials, validators). This repository owns only
the translations. Building therefore means: clone upstream at the pinned
commit, inject the translation layer, render the Chinese trees, and run
upstream's own build untouched. If upstream restructures its toolchain, this
script fails loudly instead of publishing a broken site.

Injection steps:
1. translations/ and tools/translate.py -> docs/mkdocs/ inside the clone
2. overlay/mkdocs.zh.yml -> docs/mkdocs/mkdocs.zh.yml
3. overlay/gallery.zh.yml merged into docs/mkdocs/tutorial-sources/gallery.yml
4. zh registered in docs/mkdocs/locales.yml
5. a language switcher (extra.alternate) appended to mkdocs.base.yml
6. translate.py render creates zh/ and tutorial-sources/zh/
7. upstream manage.py build produces site/en + site/zh + the root chooser
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PIN = REPO_ROOT / "UPSTREAM_COMMIT"

ALTERNATE_BLOCK = """
# Injected by fatqat-doc-translator: header language selector. manage.py
# exports one FATQAT_MKDOCS_<LOCALE>_LINK per active locale.
extra:
  alternate:
    - name: English
      link: !ENV [FATQAT_MKDOCS_EN_LINK, "/en/"]
      lang: en
    - name: 简体中文
      link: !ENV [FATQAT_MKDOCS_ZH_LINK, "/zh/"]
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


def _inject(clone: Path) -> None:
    mkdocs = clone / "docs" / "mkdocs"
    if not (mkdocs / "manage.py").is_file():
        raise RuntimeError("upstream layout changed: docs/mkdocs/manage.py missing")

    destination = mkdocs / "translations"
    if destination.exists():
        raise RuntimeError("upstream now ships docs/mkdocs/translations; resolve the overlap")
    shutil.copytree(REPO_ROOT / "translations", destination)
    shutil.copy2(REPO_ROOT / "tools" / "translate.py", mkdocs / "tools" / "translate.py")
    shutil.copy2(REPO_ROOT / "overlay" / "mkdocs.zh.yml", mkdocs / "mkdocs.zh.yml")

    # Merge the zh gallery strings beside upstream's English ones.
    gallery_path = mkdocs / "tutorial-sources" / "gallery.yml"
    gallery = yaml.safe_load(gallery_path.read_text(encoding="utf-8"))
    overlay = yaml.safe_load(
        (REPO_ROOT / "overlay" / "gallery.zh.yml").read_text(encoding="utf-8")
    )
    gallery["ui"]["zh"] = overlay["ui"]["zh"]
    gallery["index"]["zh"] = overlay["index"]["zh"]
    for category, content in overlay["categories"].items():
        if category not in gallery["categories"]:
            raise RuntimeError(
                f"gallery overlay names unknown category {category!r}; update overlay/gallery.zh.yml"
            )
        gallery["categories"][category]["zh"] = content["zh"]
    gallery_path.write_text(
        yaml.safe_dump(gallery, allow_unicode=True, sort_keys=False, width=100000),
        encoding="utf-8",
        newline="\n",
    )

    # Register the generated locale. Upstream's loader requires the page tree
    # to exist, so translate.py render runs before manage.py imports it.
    registry_path = mkdocs / "locales.yml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if "zh" in registry["locales"]:
        raise RuntimeError("upstream already registers a zh locale; resolve the overlap")
    registry["locales"]["zh"] = {
        "label": "简体中文",
        "config": "mkdocs.zh.yml",
        "generated": True,
    }
    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False, width=100000),
        encoding="utf-8",
        newline="\n",
    )

    # The base config uses YAML tags safe_load cannot round-trip, so the
    # switcher is appended textually. Fail if upstream ever adds its own
    # extra: mapping - the two must then be merged by hand.
    base_path = mkdocs / "mkdocs.base.yml"
    base_text = base_path.read_text(encoding="utf-8")
    if "\nextra:" in base_text or base_text.startswith("extra:"):
        raise RuntimeError("upstream mkdocs.base.yml now defines extra:; merge the language switcher manually")
    base_path.write_text(base_text.rstrip() + "\n" + ALTERNATE_BLOCK, encoding="utf-8", newline="\n")


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
    _inject(clone)

    python = sys.executable
    if not args.skip_install:
        _run([python, "-m", "pip", "install", str(clone)])
        _run([python, "-m", "pip", "install", "-r", str(clone / "docs" / "mkdocs" / "requirements.txt"), "jieba"])

    # Render zh trees first: upstream's locale loader and tutorial builder
    # both require them to exist.
    _run([python, str(clone / "docs" / "mkdocs" / "tools" / "translate.py"), "render"], cwd=clone)

    build = [python, str(clone / "docs" / "mkdocs" / "manage.py"), "build", "--site-dir", str(Path(args.output).resolve())]
    if args.site_url:
        build.extend(["--site-url", args.site_url])
    environment = os.environ.copy()
    _run(build, cwd=clone, env=environment)
    print("inject_build: site written to", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
