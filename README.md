# texpdf

`texpdf` is a standalone LaTeX-to-PDF compiler for Stata.

```stata
texpdf using paper.tex
texpdf using paper.tex, saving(paper.pdf) replace
texpdf, version
```

The package installs one native Stata plugin. The plugin contains a thin Rust
SPI bridge plus a target-matching compiler helper that embeds Tectonic 0.17.0,
its native libraries, and a curated academic TeX resource bundle. The bridge
verifies and extracts the helper into a private cache and launches it directly.
Runtime compilation requires no TeX installation, separately installed helper,
Rust toolchain, package download, or network connection.

## Project state

The private macOS universal [`v0.1.0-rc.1`](https://github.com/johannes-schmieder/texpdf/releases/tag/v0.1.0-rc.1)
candidate is published. The active `v0.1.0-rc.2` checkpoint adds Linux x86-64
as a required runtime with a glibc 2.28 floor and licensed Stata/MP 18 and 19
qualification on BU SCC. Windows, public distribution, and final `v0.1.0`
publication remain deferred until their separate gates are authorized and met.

Exact SHAs, artifact sizes, target support, failed attempts, and live blockers
are generated from repository evidence in [`STATUS.md`](STATUS.md) and
[`release/READINESS.md`](release/READINESS.md); they are deliberately not copied
into this durable overview.

See:

- [`STATUS.md`](STATUS.md) — generated current evidence and blockers;
- [`PLAN.md`](PLAN.md) — remaining work in execution order;
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — durable architecture and guarantees;
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

Compilation failures cross a versioned native result protocol. Shell escape is
disabled, bridge and helper panics are contained, the compiler has a bounded
timeout, and an ordinary TeX error does not terminate Stata or replace a
previously valid PDF.

## Compatibility tier

The qualified academic tier covers LaTeX core, AMS mathematics, common table
and layout packages, PDF/PNG figures, hyperlinks, Latin Modern and TeX Gyre
fonts, English-language hyphenation, and BibTeX with `natbib`. Broad language
and hyphenation collections are deliberately outside this RC. The exact
fixture-backed contract is documented
in [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) and
[`docs/SUPPORTED_PACKAGES.md`](docs/SUPPORTED_PACKAGES.md).

Beamer, TikZ/PGF, PSTricks, Biber/`biblatex`, `minted`, shell-dependent tools,
and arbitrary document-selected external helpers are outside the RC tier.

## Architecture

```text
texpdf.ado
  -> Stata SPI 3.0 Rust bridge
  -> SHA-256-verified target helper embedded in the plugin
  -> direct child process + versioned result protocol
  -> texpdf-core + Tectonic 0.17.0
  -> embedded deterministic ZIP bundle
  -> staged PDF + atomic final installation
```

Project-owned source is MIT licensed. Embedded TeX resources, fonts, Tectonic,
and native libraries retain their upstream licenses. Candidate packaging is
fail-closed unless the exact plugin/helper graphs, bundle resources, and full
notice tree pass the source-bound audit.
