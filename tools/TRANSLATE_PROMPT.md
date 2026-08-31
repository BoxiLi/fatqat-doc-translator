Translate the pending documentation segments in this repository.

You are working in the fatqat-doc-translator repository. The translation
database lives under `translations/`: one YAML file per English page, one
entry per prose segment with keys `id`, `en`, `zh`, `status`.

Do exactly this:

1. Read `translations/STYLE.md` (binding style contract) and
   `translations/glossary.yml` (fixed terminology) first.
2. Find every entry with `status: pending` across `translations/**/*.yml`.
3. For each: write a high-quality Simplified Chinese translation of `en` into
   `zh` (one line, no newlines), then set `status: machine`. If a retired
   entry elsewhere in the same file carries similar English text, use its `zh`
   as the starting point so earlier hand-tuning survives.
4. Never modify `id`, `en`, entry order, or entries that are not pending.
5. Table-row entries (English starts with `|`) keep every `|` in place; in
   `[text](destination)` translate only the text; `[`Name`][fatqat.Name]`
   cross-references, inline code, icon tokens, attribute lists, and math pass
   through verbatim. Code identifiers and product names stay English.
6. When done, run `python tools/translate.py check` and fix anything it
   reports as an error before finishing. Warnings are advisory.
