"""Translate pending segments through an OpenAI-compatible chat API.

Fallback engine for environments without a Codex or Claude subscription
credential. Configuration comes from the environment:

  TRANSLATE_API_BASE   e.g. https://api.openai.com/v1 (required)
  TRANSLATE_API_KEY    bearer token (required)
  TRANSLATE_MODEL      model name (required)
  TRANSLATE_MAX_SEGMENTS  per-run cap (default 200)

Each pending entry is translated in one request carrying the style rules and
glossary; results are written back with status: machine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import urllib.request

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = REPO_ROOT / "translations"

SYSTEM_PROMPT = """You translate quantum-computing SDK documentation from English to Simplified Chinese.
Rules (binding):
- Output ONLY the translation, one single line, no quotes, no explanations.
- Preserve inline Markdown exactly and in place: backtick code spans and their contents, bold/italic markers, icon tokens like :material-x:{ .lg .middle }, attribute lists { ... }, inline math $...$, raw HTML.
- In [text](destination) translate only the text, never the destination. In [`Name`][fatqat.Name] cross-references translate nothing.
- If the source starts with |, it is a table row: keep every | exactly where it is and translate cell contents in place.
- Code identifiers, gate names, class/function/parameter names, and product names stay English, embedded with half-width spaces around them.
- Use full-width Chinese punctuation in prose.
- Terminology (en -> zh), apply strictly:
{glossary}
"""


def _request(base: str, key: str, model: str, system: str, user: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.load(response)
    return body["choices"][0]["message"]["content"].strip().replace("\n", " ")


def main() -> int:
    base = os.environ.get("TRANSLATE_API_BASE", "")
    key = os.environ.get("TRANSLATE_API_KEY", "")
    model = os.environ.get("TRANSLATE_MODEL", "")
    if not (base and key and model):
        print("api_translate: TRANSLATE_API_BASE/KEY/MODEL must all be set", file=sys.stderr)
        return 1
    limit = int(os.environ.get("TRANSLATE_MAX_SEGMENTS", "200"))

    glossary = yaml.safe_load((TRANSLATIONS / "glossary.yml").read_text(encoding="utf-8"))
    glossary_lines = "\n".join(
        f"- {term} -> {translation}"
        for term, translation in (glossary.get("terms") or {}).items()
    )
    system = SYSTEM_PROMPT.format(glossary=glossary_lines)

    translated = 0
    for path in sorted(TRANSLATIONS.rglob("*.yml")):
        if path.name == "glossary.yml":
            continue
        entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        dirty = False
        for entry in entries:
            if entry.get("status") != "pending" or translated >= limit:
                continue
            entry["zh"] = _request(base, key, model, system, entry["en"])
            entry["status"] = "machine"
            translated += 1
            dirty = True
        if dirty:
            path.write_text(
                yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=100000, default_flow_style=False),
                encoding="utf-8",
                newline="\n",
            )
    print(f"api_translate: translated {translated} segments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
