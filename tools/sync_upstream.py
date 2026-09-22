"""Refresh the English documentation snapshot and exact upstream source pin.

Synchronize the MkDocs configuration, authored pages, tutorial sources, and
gallery settings. Advance the pin for every upstream revision so API docstrings,
examples, and build dependencies also come from the selected source version.
Pending translations still need processing when the source is unchanged.
"""

from __future__ import annotations

import argparse
import filecmp
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from site_config import upstream_config

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "upstream-docs"
PIN = REPO_ROOT / "UPSTREAM_COMMIT"

# (path inside upstream, path inside the snapshot)
SYNCED = (
    ("mkdocs.yml", "mkdocs.yml"),
    ("docs/mkdocs/en", "en"),
    ("docs/mkdocs/tutorial-sources/en", "tutorial-sources/en"),
    ("docs/mkdocs/tutorial-sources/gallery.yml", "tutorial-sources/gallery.yml"),
)


def _trees_identical(left: Path, right: Path) -> bool:
    if left.is_file() or right.is_file():
        return left.is_file() and right.is_file() and filecmp.cmp(left, right, shallow=False)
    if not (left.is_dir() and right.is_dir()):
        return False
    comparison = filecmp.dircmp(left, right)
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        return False
    return all(
        _trees_identical(left / name, right / name)
        for name in comparison.common_dirs
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=upstream_config()["repository"],
        help="upstream repository URL or local path",
    )
    parser.add_argument("--ref", default=upstream_config()["ref"], help="upstream ref to sync from")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="fatqat-sync-") as scratch:
        clone = Path(scratch) / "upstream"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", args.ref, args.repo, str(clone)],
            check=True,
        )
        head = subprocess.run(
            ["git", "-C", str(clone), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        changed = any(
            not _trees_identical(clone / source, SNAPSHOT / target)
            for source, target in SYNCED
        )
        pin_changed = not PIN.exists() or PIN.read_text().strip() != head
        if not changed and not pin_changed:
            print(f"sync: documentation unchanged (upstream at {head[:12]})")
            (REPO_ROOT / "UPSTREAM_REF").write_text(args.ref + "\n", encoding="utf-8")
            print("changed=false")
            return 0

        for source, target in SYNCED:
            destination = SNAPSHOT / target
            if SNAPSHOT.resolve() not in destination.resolve().parents:
                raise RuntimeError("snapshot destination escapes repository")
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.is_file():
                destination.unlink()
            destination.parent.mkdir(parents=True, exist_ok=True)
            origin = clone / source
            if origin.is_dir():
                shutil.copytree(origin, destination)
            else:
                shutil.copy2(origin, destination)

    PIN.write_text(head + "\n", encoding="utf-8", newline="\n")
    (REPO_ROOT / "UPSTREAM_REF").write_text(args.ref + "\n", encoding="utf-8")
    print(f"sync: documentation updated to upstream {head[:12]}")
    print("changed=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
