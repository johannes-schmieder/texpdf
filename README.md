# texpdf

`texpdf` is a standalone LaTeX-to-PDF compiler for Stata.

```stata
texpdf using paper.tex
texpdf using paper.tex, saving(paper.pdf) replace
texpdf using paper.tex, replace view
texpdf, version
```

The package installs one native Stata plugin. The plugin contains a thin Rust
SPI bridge plus a target-matching compiler helper that embeds Tectonic 0.17.0,
its native libraries, and a curated academic TeX resource bundle. The bridge
verifies and extracts the helper into a private cache and launches it directly.
Runtime compilation requires no TeX installation, separately installed helper,
Rust toolchain, package download, or network connection.

## Project state

`main` is the active development branch; it is not a stable distribution
channel. The private `0.1.0-rc.2` qualification checkpoint covers macOS
universal and Linux x86-64, including a GLIBC 2.28 floor and licensed Stata/MP
18 and 19 qualification on BU SCC. It is not a final release and is not eligible
for SSC. Windows, public distribution, and final `v0.1.0` remain deferred.

Exact SHAs, artifact sizes, target support, failed attempts, and live blockers
are generated from repository evidence in [`STATUS.md`](STATUS.md) and
[`release/READINESS.md`](release/READINESS.md); they are deliberately not copied
into this durable overview.

See:

- [`STATUS.md`](STATUS.md) — generated current evidence and blockers;
- [`PLAN.md`](PLAN.md) — remaining work in execution order;
- [`RELEASING.md`](RELEASING.md) — authoritative versioning, GitHub Release, and SSC policy;
- [`CHANGELOG.md`](CHANGELOG.md) — user-facing changes on `main` and in final releases;
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — durable architecture and guarantees;
- [`docs/README.md`](docs/README.md) — documentation index;
- [`docs/generated/CURRENT_ARTIFACT.md`](docs/generated/CURRENT_ARTIFACT.md) — exact artifact measurements;
- [`release/targets.json`](release/targets.json) — platform qualification registry.

## Installation channels

### Stable version from SSC

No final version is on SSC yet. Once SSC publishes `texpdf`, this will be the
normal recommended installation for ordinary users:

```stata
ssc install texpdf
```

The SSC package will always correspond to a final immutable GitHub release,
not to the current tip of `main` or to a release candidate.

### Development version from `main`

Installation from `main` is a **development version** and may differ from SSC.
When a public flat development installation tree is enabled, its form is:

```stata
net install texpdf, replace ///
    from("https://raw.githubusercontent.com/johannes-schmieder/texpdf/main/stata/")
```

The repository is currently private, and `texpdf` requires a compiled
platform plugin, so use a qualified CI development artifact until that public
tree exists. Do not treat the command above as a stable-release install.

### Exact historical release

An immutable tag identifies exact historical source. If that tag contains the
applicable installation tree, install it explicitly, for example:

```stata
net install texpdf, replace ///
    from("https://raw.githubusercontent.com/johannes-schmieder/texpdf/v0.2.0/stata/")
```

For compiled releases whose plugin is delivered as a platform-specific GitHub
Release asset, use the immutable installation URL documented in that release.
See [`RELEASING.md`](RELEASING.md) and
[`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## Command behavior

Without `saving()`, a final `.tex` suffix is replaced by `.pdf`; otherwise
`.pdf` is appended. Existing output is protected unless `replace` is supplied.
Relative `\input`, `\includegraphics`, and bibliography paths are resolved from
the primary source directory. The opt-in `view` option opens a successful PDF
with the operating system's default application. `help texpdf` includes three
one-click examples whose inspectable outputs remain under
`./texpdf_examples/`: manual `file write`, the suggested but optional
`latexlog` package, and Stata's built-in `etable` producing a polished
three-model regression table.

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
