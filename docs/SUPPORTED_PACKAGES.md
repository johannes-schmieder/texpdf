# Supported package matrix

Support is evidence-based. A package is not supported merely because a file
with that name happens to be present in the development bundle.

## Qualified in the comprehensive checkpoint

Source `5d85840783ad4406a1606e5b3af09a06cca2f657` compiled a real
document in licensed Stata using:

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

These are the minimum compatibility guarantees of the current macOS Apple
Silicon development checkpoint.

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
