# texpdf

`texpdf` is a standalone LaTeX-to-PDF compiler for Stata.

```stata
texpdf using paper.tex
texpdf using paper.tex, saving(paper.pdf) replace
texpdf, version
```

The package uses one native Stata plugin containing the Rust bridge, Tectonic
0.17.0, its native libraries, and a curated academic TeX resource bundle.
Runtime compilation requires no TeX installation, Tectonic executable, Rust
toolchain, package download, or network connection.

## Project state

The macOS Apple Silicon implementation is a qualified pre-release candidate
under licensed Stata/MP 18.

The current exact green source checkpoint is
`90101fa26ef06cea0ffa7e241b4230a1d0fe62a9`. The current generated artifact
record was produced from source `a42f29fbeefd41811475d47e066e1ffea5290bfd`.
Keeping these identifiers separate prevents a newer green source receipt from
being mistaken for a byte-for-byte artifact measurement.

Measured artifacts:

| Artifact | Exact size |
|---|---:|
| Embedded TeX ZIP | 6,690,289 bytes (6.38 MiB; 557 files) |
| Standalone ARM64 plugin | 49,997,392 bytes (47.68 MiB) |
| Stata installation ZIP | 23,475,982 bytes (22.39 MiB) |

The exact green source passed Rust formatting, strict Clippy, workspace tests,
native plugin construction, licensed Stata compilation, local `net install`,
the academic package corpus, and 100 in-process compile calls with injected TeX
failures.

This is not yet a public v1 release. Remaining gates are the complete
third-party license/notices inventory, high-iteration memory/safety review,
macOS universal/Intel qualification, and actual Stata runtime qualification on
Windows and Linux.

See:

- [`STATUS.md`](STATUS.md) — current source, artifact, and release state;
- [`PLAN.md`](PLAN.md) — remaining v1 work in execution order;
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — durable architecture and evidence;
- [`docs/README.md`](docs/README.md) — documentation index;
- [`docs/generated/CURRENT_ARTIFACT.md`](docs/generated/CURRENT_ARTIFACT.md) — exact artifact measurements;
- [`release/targets.json`](release/targets.json) — platform qualification registry.

## Command behavior

Without `saving()`, a final `.tex` suffix is replaced by `.pdf`; otherwise
`.pdf` is appended. Existing output is protected unless `replace` is supplied.
Relative `\input`, `\includegraphics`, and bibliography paths are resolved from
the primary source directory.

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

Compilation failures are transported through a versioned native result record.
Shell escape is disabled, Rust panics are contained at the ABI boundary, and an
ordinary TeX error does not terminate Stata or replace a previously valid PDF.

## Compatibility tier

The qualified academic tier covers LaTeX core, AMS mathematics, common table
and layout packages, PDF/PNG figures, hyperlinks, Latin Modern and TeX Gyre
fonts, and BibTeX with `natbib`. The exact contract and fixture-backed package
list are documented in [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) and
[`docs/SUPPORTED_PACKAGES.md`](docs/SUPPORTED_PACKAGES.md).

Beamer, TikZ/PGF, PSTricks, Biber/`biblatex`, `minted`, shell-dependent tools,
and arbitrary external helpers are outside the v1 tier.

## Architecture

```text
texpdf.ado
  -> Stata SPI 3.0 Rust bridge
  -> texpdf-core
  -> Tectonic 0.17.0
  -> embedded deterministic ZIP bundle
  -> PDF
```

Project-owned source is MIT licensed. Embedded TeX resources, fonts, Tectonic,
and native libraries retain their upstream licenses. Public binary publication
is fail-closed until the generated inventories and required notices are
complete.
