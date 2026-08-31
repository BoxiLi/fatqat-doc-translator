"""Maintain generated documentation locales from the translation database.

The English tree is canonical. For every generated locale (marked
``generated: true`` in ``locales.yml``), prose is stored segment-by-segment in
``translations/`` and the locale's page tree is rendered, never authored.

Subcommands:

* ``extract`` - scan English sources and add new segments as ``pending``
  entries; entries whose English text disappeared become ``retired``.
* ``render`` - write the generated locale trees by splicing translations into
  a byte-copy of each English source. Untranslated segments keep English.
* ``check`` - report translation status and verify structural invariants
  (identity round-trip, link-destination parity, duplicates, glossary).
* ``find`` - locate the database entry containing a text snippet.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
import sys
from typing import Iterable, Mapping, Sequence

import yaml

# The tool runs in two contexts. Standalone (this repository): sources live in
# upstream-docs/ and the database in translations/, both beside tools/.
# Injected (copied to docs/mkdocs/tools/ inside an upstream clone by
# inject_build.py): everything resolves relative to docs/mkdocs/ as upstream
# expects. The environment overrides let one file serve both without edits.
HERE = Path(__file__).resolve().parent
_DEFAULT_ROOT = (
    HERE.parent / "upstream-docs"
    if (HERE.parent / "upstream-docs").is_dir()
    else HERE.parent
)
MKDOCS_ROOT = Path(os.environ.get("FATQAT_MKDOCS_ROOT", _DEFAULT_ROOT))
LOCALE_REGISTRY = MKDOCS_ROOT / "locales.yml"
TRANSLATIONS_ROOT = Path(
    os.environ.get("FATQAT_TRANSLATIONS_ROOT", "")
    or (
        HERE.parent / "translations"
        if (HERE.parent / "translations").is_dir()
        else MKDOCS_ROOT / "translations"
    )
)
GLOSSARY = TRANSLATIONS_ROOT / "glossary.yml"
TUTORIAL_SOURCE_ROOT = MKDOCS_ROOT / "tutorial-sources"
CODE_CELL_PLACEHOLDER = "<!-- tutorial-code-cell -->"

FRONT_MATTER = re.compile(r"\A---\r?\n(?P<yaml>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
HEADING = re.compile(r"^(?P<prefix>#{1,6} +)(?P<text>.*?)(?P<suffix> *\{[^}]*\})?$")
BLOCK_TITLE = re.compile(
    r'^(?P<prefix>\s*(?:!!!|\?\?\?\+?|===)\s+[^"\n]*")(?P<text>[^"\n]+)(?P<suffix>")\s*$'
)
LIST_MARKER = re.compile(r"^(?P<marker>\s*(?:[-*+]|\d+\.|:|\[\^[^\]]+\]:)\s+)(?P<rest>\S.*)$")
FENCE = re.compile(r"^(?P<indent>\s*)(?P<fence>```+|~~~+)(?P<info>.*)$")
FIGCAPTION = re.compile(r"^(?P<prefix><figcaption>)(?P<text>.+)(?P<suffix></figcaption>)$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}.*$")
SNIPPET_INCLUDE = re.compile(r"^\s*--8<--")
HTML_ONLY_LINE = re.compile(r"^\s*</?[a-zA-Z][^>]*>\s*$")
COMMENT_LINE = re.compile(r"^\s*<!--.*-->\s*$")
# Mirrors validate_content.py so destination parity is checked identically.
MARKDOWN_DESTINATION = re.compile(
    r"\[!\[[^\]]*\]\((?P<linked_image>[^)\n]+)\)"
    r"(?:\{[^}\n]*\})?\]\((?P<linked_target>[^)\n]+)\)"
    r"|!?\[[^\]]*\]\((?P<destination>[^)\n]+)\)"
)
WORD = re.compile(r"[A-Za-z]")
INLINE_NOISE = re.compile(
    r"`[^`]*`"  # inline code
    r"|\(([^)\s]+)\)"  # link destinations
    r"|:[\w-]+:"  # icon shortcodes
    r"|\{[^}]*\}"  # attribute lists
    r"|\$[^$]*\$"  # inline math
)

# Front-matter keys whose string values are prose. `icon`, `template`, and
# `hide` intentionally stay canonical.
FRONT_MATTER_PROSE_KEYS = {"title", "description", "tip", "summary"}
FRONT_MATTER_PROSE_MAPPINGS = {"hero"}
FRONT_MATTER_PROSE_LISTS = {"figure_alts"}


def _load_registry() -> tuple[str, dict[str, dict]]:
    # Standalone mode has no locale registry: only the canonical English
    # sources exist here, which is all extract/check/find need. render is
    # meaningful only in the injected context, where the registry exists.
    if not LOCALE_REGISTRY.is_file():
        return "en", {"en": {"label": "English"}}
    payload = yaml.safe_load(LOCALE_REGISTRY.read_text(encoding="utf-8"))
    return payload["canonical"], payload["locales"]


def normalize(text: str) -> str:
    """Collapse whitespace so rewrapping the English never churns hashes."""

    return re.sub(r"\s+", " ", text).strip()


def segment_id(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]


def is_translatable(text: str) -> bool:
    """Keep only segments with prose left after stripping inline syntax."""

    return bool(WORD.search(INLINE_NOISE.sub(" ", text)))


@dataclass(frozen=True)
class Span:
    """One translatable region of a source file's body."""

    start: int  # first body line index, inclusive
    end: int  # last body line index, exclusive
    text: str  # normalized English prose (the database key text)
    prefix: str = ""  # literal emitted before the translation
    suffix: str = ""  # literal emitted after the translation

    @property
    def id(self) -> str:
        return segment_id(self.text)


@dataclass(frozen=True)
class SourcePage:
    """A parsed English source file."""

    path: Path
    relative: Path  # e.g. guide/quickstart.md or tutorial-sources/foundations/x.md
    front_matter_raw: str  # original block including delimiters, may be ""
    front_matter_segments: tuple[tuple[str, str], ...]  # (keypath, text)
    body_lines: tuple[str, ...]
    spans: tuple[Span, ...]
    code_cell_spans: tuple[tuple[int, int], ...]  # tutorial python fences

    @property
    def is_tutorial(self) -> bool:
        return self.relative.parts[0] == "tutorial-sources"


def _front_matter_segments(metadata: Mapping) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    for key, value in metadata.items():
        if key in FRONT_MATTER_PROSE_KEYS and isinstance(value, str):
            segments.append((key, value))
        elif key in FRONT_MATTER_PROSE_MAPPINGS and isinstance(value, dict):
            for inner_key, inner in value.items():
                if isinstance(inner, str):
                    segments.append((f"{key}.{inner_key}", inner))
        elif key in FRONT_MATTER_PROSE_LISTS and isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    segments.append((f"{key}[{index}]", item))
    return segments


def _split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or TABLE_SEPARATOR.match(stripped):
        return None
    return stripped.strip("|").split("|")


def _parse_body(lines: Sequence[str], *, tutorial: bool) -> tuple[list[Span], list[tuple[int, int]]]:
    spans: list[Span] = []
    code_cells: list[tuple[int, int]] = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        stripped = line.strip()

        if not stripped or SNIPPET_INCLUDE.match(line) or COMMENT_LINE.match(line):
            index += 1
            continue

        fence = FENCE.match(line)
        if fence:
            closer = fence.group("fence")
            start = index
            index += 1
            while index < total:
                candidate = FENCE.match(lines[index])
                if candidate and candidate.group("fence")[0] == closer[0] and len(
                    candidate.group("fence")
                ) >= len(closer) and not candidate.group("info").strip():
                    index += 1
                    break
                index += 1
            if (
                tutorial
                and not fence.group("indent")
                and fence.group("info").strip().startswith("python")
            ):
                code_cells.append((start, index))
            continue

        if stripped == "$$":
            index += 1
            while index < total and lines[index].strip() != "$$":
                index += 1
            index += 1
            continue

        if stripped in {"---", "***", "___"}:
            index += 1
            continue

        # mkdocstrings directives and their indented options blocks are code,
        # not prose; a collapsed options block breaks API rendering.
        if stripped.startswith(":::"):
            index += 1
            while index < total:
                candidate = lines[index]
                if candidate.strip() and candidate[:1] in {" ", "\t"}:
                    index += 1
                    continue
                if not candidate.strip():
                    lookahead = index + 1
                    while lookahead < total and not lines[lookahead].strip():
                        lookahead += 1
                    if lookahead < total and lines[lookahead][:1] in {" ", "\t"}:
                        index = lookahead
                        continue
                break
            continue

        caption = FIGCAPTION.match(stripped)
        if caption:
            indent = line[: len(line) - len(line.lstrip())]
            spans.append(
                Span(
                    start=index,
                    end=index + 1,
                    text=normalize(caption.group("text")),
                    prefix=indent + caption.group("prefix"),
                    suffix=caption.group("suffix"),
                )
            )
            index += 1
            continue

        if HTML_ONLY_LINE.match(line):
            index += 1
            continue

        heading = HEADING.match(stripped)
        if heading and line == stripped:
            spans.append(
                Span(
                    start=index,
                    end=index + 1,
                    text=normalize(heading.group("text")),
                    prefix=heading.group("prefix"),
                    suffix=heading.group("suffix") or "",
                )
            )
            index += 1
            continue

        block_title = BLOCK_TITLE.match(line)
        if block_title:
            spans.append(
                Span(
                    start=index,
                    end=index + 1,
                    text=normalize(block_title.group("text")),
                    prefix=block_title.group("prefix"),
                    suffix=block_title.group("suffix"),
                )
            )
            index += 1
            continue

        # One entry per table row: cells stay together so entries read as
        # complete phrases and inline code containing pipes is never split.
        if _split_table_row(line) is not None:
            indent = line[: len(line) - len(line.lstrip())]
            spans.append(
                Span(
                    start=index,
                    end=index + 1,
                    text=normalize(line),
                    prefix=indent,
                )
            )
            index += 1
            continue

        marker = LIST_MARKER.match(line)
        if marker:
            start = index
            parts = [marker.group("rest")]
            item_indent = len(marker.group("marker"))
            index += 1
            while index < total:
                follower = lines[index]
                if not follower.strip():
                    break
                follower_indent = len(follower) - len(follower.lstrip())
                if follower_indent < item_indent or LIST_MARKER.match(follower):
                    break
                if FENCE.match(follower) or _split_table_row(follower) is not None:
                    break
                parts.append(follower.strip())
                index += 1
            spans.append(
                Span(
                    start=start,
                    end=index,
                    text=normalize(" ".join(parts)),
                    prefix=marker.group("marker"),
                )
            )
            continue

        # Default: a paragraph block of contiguous prose lines.
        start = index
        indent = line[: len(line) - len(line.lstrip())]
        parts = [stripped]
        index += 1
        while index < total:
            follower = lines[index]
            follower_stripped = follower.strip()
            if (
                not follower_stripped
                or FENCE.match(follower)
                or HEADING.match(follower_stripped)
                or BLOCK_TITLE.match(follower)
                or LIST_MARKER.match(follower)
                or COMMENT_LINE.match(follower)
                or HTML_ONLY_LINE.match(follower)
                or SNIPPET_INCLUDE.match(follower)
                or _split_table_row(follower) is not None
                or follower_stripped == "$$"
            ):
                break
            parts.append(follower_stripped)
            index += 1
        spans.append(
            Span(
                start=start,
                end=index,
                text=normalize(" ".join(parts)),
                prefix=indent,
            )
        )
    return spans, code_cells


def parse_source(path: Path, relative: Path) -> SourcePage:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(text)
    front_raw = match.group(0) if match else ""
    metadata = yaml.safe_load(match.group("yaml")) if match else {}
    body = text[len(front_raw) :]
    lines = body.split("\n")
    tutorial = relative.parts[0] == "tutorial-sources"
    spans, code_cells = _parse_body(lines, tutorial=tutorial)
    return SourcePage(
        path=path,
        relative=relative,
        front_matter_raw=front_raw,
        front_matter_segments=tuple(_front_matter_segments(metadata or {})),
        body_lines=tuple(lines),
        spans=tuple(spans),
        code_cell_spans=tuple(code_cells),
    )


# Build products inside a locale tree (created by the figure and tutorial
# generators) are never translation sources.
GENERATED_PAGE_DIRS = {"assets", "downloads", "tutorials"}


def discover_sources(canonical: str) -> list[SourcePage]:
    """Parse every authored canonical page and tutorial source, in stable order."""

    pages: list[SourcePage] = []
    page_root = MKDOCS_ROOT / canonical
    for path in sorted(page_root.rglob("*.md")):
        relative = path.relative_to(page_root)
        if relative.parts[0] in GENERATED_PAGE_DIRS:
            continue
        pages.append(parse_source(path, relative))
    tutorial_root = TUTORIAL_SOURCE_ROOT / canonical
    for path in sorted(tutorial_root.rglob("*.md")):
        relative = Path("tutorial-sources") / path.relative_to(tutorial_root)
        pages.append(parse_source(path, relative))
    return pages


def _page_segments(page: SourcePage) -> list[str]:
    """Return the ordered English texts a page needs translations for."""

    texts = [text for _, text in page.front_matter_segments]
    texts.extend(
        span.text for span in page.spans if is_translatable(span.text)
    )
    return texts


# --------------------------------------------------------------------------
# Translation database


@dataclass
class Entry:
    id: str
    en: str
    zh: str
    status: str  # pending | machine | reviewed | retired


def _entry_file(relative: Path) -> Path:
    return (TRANSLATIONS_ROOT / relative).with_suffix(".yml")


def load_database() -> dict[Path, list[Entry]]:
    database: dict[Path, list[Entry]] = {}
    if not TRANSLATIONS_ROOT.is_dir():
        return database
    for path in sorted(TRANSLATIONS_ROOT.rglob("*.yml")):
        if path == GLOSSARY:
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        database[path] = [
            Entry(
                id=item["id"],
                en=item["en"],
                zh=item.get("zh") or "",
                status=item.get("status", "pending"),
            )
            for item in raw
        ]
    return database


def save_database_file(path: Path, entries: Iterable[Entry]) -> None:
    payload = [
        {"id": entry.id, "en": entry.en, "zh": entry.zh, "status": entry.status}
        for entry in entries
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            width=100000,
            default_flow_style=False,
        ),
        encoding="utf-8",
        newline="\n",
    )


def global_map(database: Mapping[Path, list[Entry]]) -> dict[str, Entry]:
    merged: dict[str, Entry] = {}
    for entries in database.values():
        for entry in entries:
            existing = merged.get(entry.id)
            if existing is None or (
                existing.status == "retired" and entry.status != "retired"
            ):
                merged[entry.id] = entry
    return merged


# --------------------------------------------------------------------------
# extract


def run_extract(*, dry_run: bool) -> int:
    canonical, _ = _load_registry()
    pages = discover_sources(canonical)
    database = load_database()
    merged = global_map(database)

    needed: set[str] = set()
    new_by_file: dict[Path, list[Entry]] = {}
    for page in pages:
        for text in _page_segments(page):
            sid = segment_id(text)
            needed.add(sid)
            entry = merged.get(sid)
            if entry is None:
                entry = Entry(id=sid, en=text, zh="", status="pending")
                merged[sid] = entry
                new_by_file.setdefault(_entry_file(page.relative), []).append(entry)
            elif entry.status == "retired":
                entry.status = "reviewed" if entry.zh else "pending"

    retired = 0
    for entries in database.values():
        for entry in entries:
            if entry.id not in needed and entry.status != "retired":
                entry.status = "retired"
                retired += 1

    added = sum(len(entries) for entries in new_by_file.values())
    print(f"extract: {added} new segments, {retired} newly retired")
    if dry_run:
        return 1 if added else 0

    for path, fresh in new_by_file.items():
        database.setdefault(path, []).extend(fresh)
    for path, entries in database.items():
        save_database_file(path, entries)
    return 0


# --------------------------------------------------------------------------
# render


def _render_front_matter(page: SourcePage, merged: Mapping[str, Entry]) -> str:
    if not page.front_matter_raw:
        return ""
    translations = {}
    for keypath, text in page.front_matter_segments:
        entry = merged.get(segment_id(text))
        if entry and entry.zh and entry.status != "retired":
            translations[keypath] = entry.zh
    if not translations:
        return page.front_matter_raw

    metadata = yaml.safe_load(FRONT_MATTER.match(page.front_matter_raw).group("yaml"))
    for keypath, translated in translations.items():
        target = metadata
        parts = re.findall(r"[^.\[\]]+|\[\d+\]", keypath)
        for part in parts[:-1]:
            target = target[int(part[1:-1])] if part.startswith("[") else target[part]
        last = parts[-1]
        if last.startswith("["):
            target[int(last[1:-1])] = translated
        else:
            target[last] = translated
    dumped = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
        width=100000,
        default_flow_style=False,
    )
    return f"---\n{dumped}---\n"


def _lookup(merged: Mapping[str, Entry], text: str) -> str | None:
    entry = merged.get(segment_id(text))
    if entry and entry.zh and entry.status != "retired":
        return entry.zh
    return None


def render_page(
    page: SourcePage, merged: Mapping[str, Entry], *, as_tutorial_source: bool
) -> tuple[str, int]:
    """Return the rendered locale file and its English-fallback count."""

    fallbacks = 0
    for _, text in page.front_matter_segments:
        if _lookup(merged, text) is None:
            fallbacks += 1

    replacements: dict[int, tuple[int, list[str]]] = {}
    code_cell_bounds = dict(page.code_cell_spans)
    for span in page.spans:
        if not is_translatable(span.text):
            continue
        translated = _lookup(merged, span.text)
        if translated is None:
            fallbacks += 1
            continue
        replacements[span.start] = (
            span.end,
            [span.prefix + translated + span.suffix],
        )

    output: list[str] = []
    index = 0
    lines = page.body_lines
    while index < len(lines):
        if as_tutorial_source and index in code_cell_bounds:
            output.append(CODE_CELL_PLACEHOLDER)
            index = code_cell_bounds[index]
            continue
        if index in replacements:
            end, rendered = replacements[index]
            output.extend(rendered)
            index = end
            continue
        output.append(lines[index])
        index += 1
    return _render_front_matter(page, merged) + "\n".join(output), fallbacks


def run_render(*, strict: bool) -> int:
    canonical, locales = _load_registry()
    targets = [
        code
        for code, config in locales.items()
        if code != canonical and config.get("generated")
    ]
    if not targets:
        print("render: no generated locales are active")
        return 0

    pages = discover_sources(canonical)
    merged = global_map(load_database())
    total_fallbacks = 0
    for locale in targets:
        for page in pages:
            rendered, fallbacks = render_page(
                page, merged, as_tutorial_source=page.is_tutorial
            )
            total_fallbacks += fallbacks
            if page.is_tutorial:
                destination = (
                    TUTORIAL_SOURCE_ROOT
                    / locale
                    / Path(*page.relative.parts[1:])
                )
            else:
                destination = MKDOCS_ROOT / locale / page.relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"render: wrote locale {locale!r} ({len(pages)} files)")
    if total_fallbacks:
        message = f"render: {total_fallbacks} segments fell back to English"
        if strict:
            print(f"error: {message}", file=sys.stderr)
            return 1
        print(message)
    return 0


# --------------------------------------------------------------------------
# check


def _destinations(text: str) -> list[str]:
    found: list[str] = []
    for match in MARKDOWN_DESTINATION.finditer(text):
        if match.group("linked_image"):
            found.append(match.group("linked_image").strip())
            found.append(match.group("linked_target").strip())
        else:
            found.append(match.group("destination").strip())
    return found


def run_check() -> int:
    canonical, _ = _load_registry()
    pages = discover_sources(canonical)
    database = load_database()
    errors: list[str] = []
    warnings: list[str] = []

    # Identity round-trip: with no translation applied, every rendered page
    # must reproduce its English source byte-for-byte (code placeholders
    # aside for tutorials). This pins the segmentation itself.
    for page in pages:
        rendered, _ = render_page(page, {}, as_tutorial_source=False)
        original = page.front_matter_raw + "\n".join(page.body_lines)
        if rendered != original:
            errors.append(f"{page.relative}: identity round-trip differs")

    # Duplicate definitions must agree.
    seen: dict[str, tuple[Path, Entry]] = {}
    for path, entries in database.items():
        for entry in entries:
            if segment_id(entry.en) != entry.id:
                errors.append(f"{path.name}: entry {entry.id} does not match its en text")
            previous = seen.get(entry.id)
            if previous and previous[1].zh and entry.zh and previous[1].zh != entry.zh:
                errors.append(
                    f"{entry.id}: conflicting translations in "
                    f"{previous[0].name} and {path.name}"
                )
            seen.setdefault(entry.id, (path, entry))

    # Translations must preserve link and image destinations in order, and a
    # table-row translation must keep the row's column structure.
    for path, entries in database.items():
        for entry in entries:
            if not entry.zh or entry.status == "retired":
                continue
            if _destinations(entry.en) != _destinations(entry.zh):
                errors.append(
                    f"{path.relative_to(TRANSLATIONS_ROOT)}: {entry.id} changes "
                    "link or image destinations"
                )
            if entry.en.startswith("|") and entry.en.count("|") != entry.zh.count("|"):
                errors.append(
                    f"{path.relative_to(TRANSLATIONS_ROOT)}: {entry.id} changes "
                    "the table row's column structure"
                )

    # Glossary consistency (warning only).
    if GLOSSARY.is_file():
        glossary = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8")) or {}
        for term, translation in (glossary.get("terms") or {}).items():
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            for path, entries in database.items():
                for entry in entries:
                    if not entry.zh or entry.status == "retired":
                        continue
                    if pattern.search(entry.en) and translation not in entry.zh:
                        if term.lower() not in entry.zh.lower():
                            warnings.append(
                                f"{path.relative_to(TRANSLATIONS_ROOT)}: {entry.id} "
                                f"mentions {term!r} without {translation!r}"
                            )

    counts = {"pending": 0, "machine": 0, "reviewed": 0, "retired": 0}
    for entries in database.values():
        for entry in entries:
            counts[entry.status] = counts.get(entry.status, 0) + 1
    print(
        "check: "
        + ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    )
    for warning in warnings[:40]:
        print(f"warning: {warning}")
    if len(warnings) > 40:
        print(f"warning: ... and {len(warnings) - 40} more glossary warnings")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    return 0


# --------------------------------------------------------------------------
# find


def run_find(snippet: str) -> int:
    lowered = snippet.lower()
    hits = 0
    for path, entries in load_database().items():
        for entry in entries:
            if lowered in entry.en.lower() or lowered in entry.zh.lower():
                print(f"{path.relative_to(TRANSLATIONS_ROOT).as_posix()}: {entry.id}")
                print(f"  en: {entry.en}")
                print(f"  zh: {entry.zh or '(untranslated)'}  [{entry.status}]")
                hits += 1
    if not hits:
        print("find: no matching entries")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract", help="register new English segments in the database"
    )
    extract_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report new and retired segments without writing; exit 1 if any",
    )

    render_parser = subparsers.add_parser(
        "render", help="write generated locale trees from the database"
    )
    render_parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when any segment falls back to English",
    )

    subparsers.add_parser("check", help="validate the translation database")

    find_parser = subparsers.add_parser(
        "find", help="locate database entries containing a text snippet"
    )
    find_parser.add_argument("snippet")

    args = parser.parse_args(argv)
    if args.command == "extract":
        return run_extract(dry_run=args.dry_run)
    if args.command == "render":
        return run_render(strict=args.strict)
    if args.command == "check":
        return run_check()
    return run_find(args.snippet)


if __name__ == "__main__":
    raise SystemExit(main())
