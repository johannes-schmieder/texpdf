# texpdf v1 compatibility contract

This document defines the intended v1 behavior of the compiler-only `texpdf`
command. Platform qualification remains separate: a target is supported only
after the final plugin has loaded and compiled the offline corpus in actual
licensed Stata on that operating system.

## Public syntax

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
texpdf, version
```

The command is `rclass` and requires Stata 14.1 or newer at the ado/SPI level.
The currently qualified runtime is Stata/MP 18 on macOS Apple Silicon.

Without `saving()`, a final case-insensitive `.tex` suffix is replaced by
`.pdf`; otherwise `.pdf` is appended. Existing output is protected unless
`replace` is specified. The output may not resolve to the input source.

## Stored results

Successful compilation returns:

```text
r(pdf)                 final output path
r(engine)              tectonic
r(engine_version)      embedded Tectonic version
r(bundle_version)      embedded texpdf bundle version
r(bundle_digest)       Tectonic content digest
r(bundle_zip_sha256)   SHA-256 of the embedded resource ZIP
r(warnings)            captured warning count
```

`texpdf, version` returns all entries except `r(pdf)`.

The names and meanings above are the v1 compatibility contract. New returned
results may be added, but these entries should not be removed or repurposed in
a v1 maintenance release.

## Error classes

The ado layer reports the native error class using conventional Stata return
codes:

| Return code | Meaning |
|---:|---|
| 198 | invalid syntax, option combination, flag, or invalid source/output identity |
| 601 | input is missing or is not a regular file |
| 602 | output exists and `replace` was not specified |
| 603 | filesystem or output-installation failure |
| 459 | TeX/Tectonic compilation failure |
| 710 | malformed result record, embedded-bundle failure, engine lock failure, or other internal bridge error |

Ordinary TeX errors are returned through a versioned result record; they do not
cross the ABI as an unwind. The Stata process must remain usable after a
recoverable compilation error.

## Input filesystem behavior

The primary source directory is the TeX filesystem root used for normal
relative lookup. The qualified corpus covers relative `\input`,
`\includegraphics`, bibliography files, spaces, and Unicode paths.

Shell escape is disabled. The package does not run arbitrary external helper
programs. Documents that require Pygments, Ghostscript conversion, gnuplot,
Biber, or another subprocess are outside v1.

## Tectonic versus pdfLaTeX

`texpdf` uses Tectonic 0.17.0, whose TeX engine is XeTeX-derived. It is a LaTeX
compiler, but it is not a wrapper around the `pdflatex` executable.

Expected implications:

- ordinary LaTeX source, mathematical notation, tables, figures, references,
  and BibTeX/natbib workflows in the advertised corpus are supported;
- Unicode and modern font handling follow the XeTeX/Tectonic model;
- PDF bytes, line breaking, font embedding, and metadata need not match a
  pdfTeX build byte-for-byte;
- documents that directly depend on pdfTeX-only primitives or packages are not
  guaranteed to work;
- DVI/PS workflows and packages requiring external conversion are not part of
  v1;
- Tectonic performs the required internal reruns automatically rather than
  exposing a `latexmk`-style command loop to Stata.

The supported contract is the committed offline corpus, not every package in a
full TeX Live installation.

## Advertised package tier

The current curated corpus covers the package groups recorded in
`bundle/packages.toml` and `README.md`, including AMS math, common economics
and scientific tables, standard graphics/layout packages, hyperlinks,
`microtype`, BibTeX, and natbib.

Explicit initial exclusions include:

- Beamer;
- TikZ/PGF and PSTricks;
- Biber/biblatex;
- minted/Pygments;
- arbitrary system fonts not embedded in the bundle;
- broad language/font collections not represented in the corpus;
- runtime package downloads.

A package is supported only after an offline fixture compiles with the released
plugin. Presence of a file in the resource ZIP by itself is not a support
promise.

## Reproducibility boundary

The Rust dependency graph, native dependency revision, source archives,
resource selection, bundle ZIP, plugin, and installation ZIP are checksum
pinned. This makes release artifacts traceable and rebuildable.

The project does not currently promise byte-identical PDFs across compilation
times or operating systems. PDF metadata, engine behavior, and platform font
rendering details may differ even when the document is semantically identical.

## Platform support labels

The repository uses three distinct labels:

1. **Build-qualified:** the plugin compiles, exports the required symbols, has
   an audited runtime dependency set, and passes Rust/core tests on that OS.
2. **Runtime-qualified:** the exact plugin loads and compiles the offline corpus
   in licensed Stata on that OS/architecture.
3. **Supported:** the runtime-qualified artifact is included in a
   license-complete public release and passes the clean installation profile.

A hosted compiler build alone never establishes Stata support.
