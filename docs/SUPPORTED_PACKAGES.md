# Supported package matrix

Support is evidence-based. A package is not supported merely because a file
with that name happens to be present in the development bundle.

## Qualified corpus

The exact source currently qualified by licensed Stata is recorded in
`../STATUS.md` and `../release/targets.json`. The corpus exercises:

| Capability | Qualified material |
|---|---|
| Document class | `article` |
| Mathematics | `amsmath` |
| Tables | `booktabs` |
| Links/references | `hyperref` |
| Bibliography | `natbib` with internal BibTeX and `plainnat` |
| Project structure | relative `\input` |
| Paths | spaces and Unicode |
| Fonts | deterministic defaults required by the fixture |

These are minimum guarantees of the cross-platform 0.1.0 release. Its language
policy is English-only.

## Bundled academic interfaces

Version 0.1.0 bundles the following user-facing groups. The exact `.sty`,
`.cls`, and `.bst` inventory is listed by `help texpdf` and checked against the
curated manifest. Support claims remain fixture-based rather than inferred
from the mere presence of a file.

### Mathematics

- `amssymb`, `amsfonts`, `amscls`, `mathtools`.

### Tables

- `array`, `longtable`, `tabularx`, `multirow`, `threeparttable`,
  `threeparttablex`, `dcolumn`, `siunitx`, `adjustbox`.

### Figures and layout

- `graphicx`, `xcolor`, `geometry`, `float`, `placeins`, `rotating`,
  `pdflscape`, `caption`, `subcaption`.

### Formatting and references

- `url`, `setspace`, `enumitem`, `fancyhdr`, `titlesec`, `microtype`.

### Fonts

- Latin Modern and a small justified TeX Gyre subset.

Future additions should be promoted in small fixture-backed groups so their
incremental bundle cost and license closure remain measurable.

## Real-world corpus additions

The 0.1.0 synthetic real-world corpus tests:

- `colortbl` in current latexlog-generated tables;
- `cleveref` in a multi-file economics manuscript;
- the `aer.bst` BibTeX style from TeX Live's `economic` package with natbib;
- the obsolete `subfigure` package in a sanitized legacy report.

These capabilities are included in the 0.1.0 qualification record. Windows
licensed-runtime behavior follows the documented RC2-to-final equivalence
boundary. `subfigure` is supported only to open and compile legacy documents;
new documents should use `subcaption`.

## Deliberate exclusions for v1

- shell escape and arbitrary helper programs;
- Biber/biblatex;
- minted/Pygments;
- Beamer;
- TikZ/PGF;
- PSTricks;
- broad language/font collections;
- runtime package downloads;
- reliance on arbitrary system fonts.

A release or development artifact may compile some excluded material accidentally. That
is not a support promise.
