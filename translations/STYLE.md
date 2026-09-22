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
   GitHub, NumPy, Matplotlib) are not translated. Named algorithms and their
   abbreviations (Grover, QAOA, VQE) also stay English. Preserve source spelling
   and case; a code name such as `Estimator` takes precedence over the generic
   glossary term estimator → 估计器. Keep ordinary descriptions in Chinese.
4. **Terminology follows `glossary.yml`.** Use established Chinese terms for
   concepts such as 量子态、密度矩阵、哈密顿量、可观测量 and 期望值. For an
   ambiguous term, give Chinese and English together at its first substantive
   mention on a page, then use the Chinese term consistently. In particular,
   quantum channel → 量子信道 and control channel → 控制通道 are different
   concepts; do not translate every occurrence of channel the same way.
   Generic simulator/simulation → 模拟器/模拟 and emulator/emulation →
   仿真器/仿真, while the `Simulator` class keeps its name. API titles and
   navigation labels naming a class keep the identifier; a short Chinese
   description may follow, for example Estimator：计算期望值.
   Use Registers and Operations for their API page titles; keep Register and
   Operation when referring to API objects or types. In user-guide prose, use
   the specific meaning when clear: 量子门, 旋转, 测量, or 脉冲块. Do not turn
   every Operation into a gate: reset, atom placement, and pulses also belong
   to this API. Generic quantum/classical registers may remain 量子/经典寄存器;
   explain their role as grouped program resources when first introduced.
   Do not change unrelated words such as 操作数, 操作系统, or 注册.
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
