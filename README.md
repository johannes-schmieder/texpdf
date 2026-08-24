# texpdf

`texpdf` is a standalone LaTeX-to-PDF compiler for Stata.

```stata
texpdf using paper.tex
texpdf using paper.tex, saving(paper.pdf) replace
texpdf, version
```

The package uses one native Stata plugin containing the Tectonic engine and an
embedded, curated academic TeX resource bundle. Runtime use does not require
TeX Live, MacTeX, MiKTeX, a Tectonic executable, Rust, a compiler, package
downloads, or a network connection.

## Status

The macOS Apple Silicon implementation is end-to-end qualified under licensed
Stata/MP 18. The exact qualified source is
`63b997d290ec3adde0af33dbb49a96972d1e30c9`.

Current qualified sizes:

- embedded bundle: 6,692,142 bytes (477 resources);
- standalone plugin: 49,996,816 bytes;
- deterministic Stata installation ZIP: 23,480,504 bytes.

The CI qualification compiles real documents, exercises BibTeX/natbib and the
declared academic package corpus, performs a local `net install`, tests spaces
and Unicode in paths, verifies recovery after TeX errors, and runs 100 compile
calls in one Stata process.

See [`STATUS.md`](STATUS.md) for the qualification boundary,
[`bundle/QUALIFICATION.json`](bundle/QUALIFICATION.json) for exact hashes and
sizes, and [`PLAN.md`](PLAN.md) for the remaining cross-platform and public
release gates.

## Command behavior

Without `saving()`, a final `.tex` suffix is replaced by `.pdf`; otherwise
`.pdf` is appended. Existing output is protected unless `replace` is specified.
Relative `\input`, `\includegraphics`, and bibliography paths are resolved from
the directory containing the primary source document.

After successful compilation, `texpdf` returns:

```text
r(pdf)
r(engine)
r(engine_version)
r(bundle_version)
r(bundle_digest)
r(bundle_zip_sha256)
r(warnings)
```

Compilation errors are reported through a versioned native result record. Rust
panics are caught at the ABI boundary, shell escape is disabled, and ordinary
TeX errors do not terminate Stata.

## Embedded compatibility tier

The qualified bundle covers the project’s academic/econometric corpus,
including:

- LaTeX core, AMS math, and `mathtools`;
- `booktabs`, `longtable`, `tabularx`, `multirow`, `threeparttable`, `dcolumn`,
  `siunitx`, and `adjustbox`;
- `graphicx`, `xcolor`, `geometry`, `float`, `placeins`, `rotating`,
  `pdflscape`, `caption`, and `subcaption`;
- `hyperref`, `url`, `setspace`, `enumitem`, `fancyhdr`, `titlesec`,
  `microtype`, and `natbib`;
- BibTeX and the fonts/metrics/maps required by the corpus.

Beamer, TikZ/PGF, PSTricks, Biber/biblatex, minted/Pygments, and arbitrary
external helper programs are outside the initial v1 tier.

## Architecture

```text
texpdf.ado
    -> Stata SPI 3.0 Rust bridge
    -> texpdf-core
    -> Tectonic 0.17.0
    -> embedded deterministic ZIP bundle
    -> PDF
```

Native dependencies are built statically with a pinned vcpkg revision. The
macOS qualification checks exported plugin symbols and rejects unexpected
Homebrew or vcpkg runtime-library dependencies.

## Development and CI

Development occurs directly on `main` in small checkpoints. Normal pushes run
Rust formatting, strict Clippy, tests, the release plugin build, licensed Stata
compilation tests, package assembly, `net install`, and the configured stress
profile. Each source checkpoint receives an immutable receipt under
`.ci/stata/results/<source-sha>.json`.

The generated bundle and plugin are build artifacts and are not committed to
Git. GitHub Release publication will be enabled after the embedded
package/font license inventory and the non-ARM platform qualifications are
complete.

## License

Project-owned source is MIT licensed. Tectonic, native libraries, TeX/LaTeX
resources, fonts, and bibliography styles retain their upstream licenses and
notices. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
