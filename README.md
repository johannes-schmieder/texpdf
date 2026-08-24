# texpdf

`texpdf` is a standalone LaTeX-to-PDF compiler for Stata.

The intended public interface is:

```stata
texpdf using paper.tex
texpdf using paper.tex, saving(paper.pdf) replace
```

A released platform artifact will be one native `texpdf.plugin` containing the Tectonic engine and an embedded academic TeX resource bundle. Users will not need TeX Live, MacTeX, MiKTeX, Tectonic, Rust, a compiler, or an Internet connection.

## Project status

Implementation is in progress. The licensed Stata/Rust CI infrastructure and architecture are established; public installation instructions will be added when the first end-to-end plugin artifact is qualified.

See [`PLAN.md`](PLAN.md) for the authoritative design and milestones, [`STATUS.md`](STATUS.md) for the current checkpoint, and [`gptpro.md`](gptpro.md) for the exact-SHA Stata CI workflow.

## Initial scope

Version 1 is a compiler for complete `.tex` documents. It targets Stata 14.1+ at the plugin ABI level and initially certifies Stata/MP 18. The bundled compatibility tier is aimed at common academic/econometric documents, including math, tables, figures, hyperlinks, and BibTeX/natbib. Beamer, TikZ/PGF, Biber/biblatex, shell escape, and external helper programs are not planned for v1.

## Development

Development occurs directly on `main` in small checkpoints. Normal source pushes run Rust checks and licensed Stata tests on a repository-scoped Apple Silicon runner. A checkpoint is considered qualified only by the immutable exact-source-SHA receipt under `.ci/stata/results/`.

## License

Project-owned source code is MIT licensed. Tectonic, TeX/LaTeX support files, fonts, and Stata interface files retain their upstream licenses and notices.
