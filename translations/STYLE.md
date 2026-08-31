# Translation style contract

Every `zh:` field in this directory must follow these rules. `translate.py
check` enforces the structural ones; reviewers enforce the rest.

1. **One line.** A `zh:` value never contains a newline; the renderer splices
   it into a single Markdown block.
2. **Inline Markdown passes through untouched.** Preserve exactly, in place:
   inline code backticks and their contents, bold/italic markers, icon tokens
   such as `:material-tune-variant:{ .lg .middle }`, attribute lists `{ ... }`,
   inline math `$...$`, and raw HTML. In `[text](destination)` translate only
   the text — never the destination. In `[`Name`][fatqat.Name]` translate
   nothing; it is a code cross-reference.
3. **Code identifiers stay English.** Class, function, parameter, gate, and
   file names (`Program`, `run()`, `shots`, `CZ`) remain verbatim, including
   inside prose. Product names (FatQat, Qiskit, OpenQASM, QuTiP, PyPI,
   GitHub, NumPy, Matplotlib) are not translated.
4. **Terminology follows `glossary.yml`.** One English term, one Chinese
   rendering, everywhere. Note the deliberate pair: simulator/simulation →
   模拟器/模拟, emulator/emulation → 仿真器/仿真.
5. **Punctuation.** Chinese prose uses full-width punctuation（，。：；？！）；
   half-width stays inside code spans, paths, and numbers. No space between
   CJK text and full-width punctuation; keep a normal half-width space
   around inline code, Latin words, and numbers.
6. **Table rows are one entry.** An entry whose English starts with `|` is a
   complete table row: translate the cell contents in place and keep every
   `|` exactly where the structure puts it — never add, drop, or move pipes
   (`check` compares the pipe count).
7. **Status discipline.** Machine output sets `status: machine`. Only a human
   reviewer flips an entry to `reviewed`. Never edit `id:` or `en:` by hand —
   they belong to the extractor.
