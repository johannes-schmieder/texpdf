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

These are the minimum compatibility guarantees of the current qualified
macOS development checkpoint. The private RC's language policy is English-only.

## Candidate academic v1 packages

The following remain candidate packages until each has a redistributable
fixture, a resolved resource/font closure, complete license metadata, and a
successful final-platform corpus result:

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

Candidates should be promoted in small fixture-backed groups so the incremental
bundle cost and license closure are measurable.

## Development-tested real-world additions

The bundle on `main` contains a separate development selection that has not
replaced the frozen private candidate. Its synthetic real-world corpus tests:

- `colortbl` in current latexlog-generated tables;
- `cleveref` in a multi-file economics manuscript;
- the `aer.bst` BibTeX style from TeX Live's `economic` package with natbib;
- the obsolete `subfigure` package in a sanitized legacy report.

These are development-tested capabilities pending full all-target runtime
requalification. `subfigure` is supported only to open and compile legacy
documents; new documents should use `subcaption`.

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

A development artifact may compile some excluded material accidentally. That
is not a support promise.
