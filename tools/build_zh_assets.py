"""Generate the Chinese tutorial pages and assets inside an upstream clone.

Upstream's documentation toolchain became single-locale when it moved to one
root mkdocs.yml: build_tutorials.py hard-wires its source and output paths to
the ``en`` tree and its gallery strings to the ``en`` key. This driver imports
that module unchanged, retargets its module-level constants at the rendered
``zh`` trees, swaps the gallery strings for the Chinese overlay, and runs the
same build. Executable code cells are byte-identical to English, so the shared
tutorial-results cache is reused and nothing re-executes.

Guide and homepage figures are language-neutral; they are copied from the
``en`` assets the upstream build already generated.

Run AFTER upstream's English build (which fills the caches) and BEFORE the
Chinese MkDocs build. Fails loudly when upstream's module shape changes.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
GALLERY_OVERLAY = REPO_ROOT / "overlay" / "gallery.zh.yml"

# Module constants the driver retargets; their absence means upstream
# restructured build_tutorials.py again and this driver needs updating.
RETARGETED = ("SOURCE_ROOT", "PAGE_ROOT", "DOWNLOAD_ROOT", "ASSET_ROOT")
SWAPPED_STRINGS = ("GALLERY", "GALLERY_UI", "GALLERY_INDEX")


def _swap_locale_strings(module, overlay: dict) -> None:
    for key in ("ui", "index"):
        english = module.GALLERY[key]["en"]
        chinese = overlay[key]["zh"]
        if set(chinese) != set(english):
            raise RuntimeError(
                f"gallery overlay {key} keys {sorted(chinese)} do not match "
                f"upstream {sorted(english)}; update overlay/gallery.zh.yml"
            )
    module.GALLERY_UI = overlay["ui"]["zh"]
    module.GALLERY_INDEX = overlay["index"]["zh"]
    categories = module.GALLERY["categories"]
    for category, content in overlay["categories"].items():
        if category not in categories:
            raise RuntimeError(
                f"gallery overlay names unknown category {category!r}; "
                "update overlay/gallery.zh.yml"
            )
        categories[category]["en"] = content["zh"]
    missing = set(categories) - set(overlay["categories"])
    if missing:
        raise RuntimeError(
            f"categories missing Chinese strings: {sorted(missing)}; "
            "update overlay/gallery.zh.yml"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, help="root of the upstream clone")
    args = parser.parse_args()

    clone = Path(args.clone).resolve()
    mkdocs_root = clone / "docs" / "mkdocs"
    if not (clone / "mkdocs.yml").is_file() or not (mkdocs_root / "en").is_dir():
        raise RuntimeError(f"{clone} does not look like an upstream clone")
    if not (mkdocs_root / "zh").is_dir():
        raise RuntimeError("run translate.py render before build_zh_assets.py")

    sys.path.insert(0, str(clone))
    from docs.mkdocs.tools import build_tutorials  # noqa: PLC0415

    for name in RETARGETED + SWAPPED_STRINGS:
        if not hasattr(build_tutorials, name):
            raise RuntimeError(
                f"upstream build_tutorials.py no longer defines {name}; "
                "adapt build_zh_assets.py to the new layout"
            )

    build_tutorials.SOURCE_ROOT = mkdocs_root / "tutorial-sources" / "zh"
    build_tutorials.PAGE_ROOT = mkdocs_root / "zh" / "tutorials"
    build_tutorials.DOWNLOAD_ROOT = mkdocs_root / "zh" / "downloads" / "tutorials"
    build_tutorials.ASSET_ROOT = (
        mkdocs_root / "zh" / "assets" / "generated" / "tutorials"
    )
    overlay = yaml.safe_load(GALLERY_OVERLAY.read_text(encoding="utf-8"))
    _swap_locale_strings(build_tutorials, overlay)

    build_tutorials.build_all(execute_if_needed=True)

    # Guide and homepage figures are language-neutral build products.
    for folder in ("guide", "home"):
        source = mkdocs_root / "en" / "assets" / "generated" / folder
        if not source.is_dir():
            raise RuntimeError(
                f"{source} missing; run the English build before this driver"
            )
        destination = mkdocs_root / "zh" / "assets" / "generated" / folder
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

    print("build_zh_assets: Chinese tutorials and assets generated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
