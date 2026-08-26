# Changelog

All notable user-facing changes to `texpdf` are recorded here. `Unreleased`
describes development on `main`; dated sections are created only for final
releases. Private release candidates are testing checkpoints, not stable
releases or SSC versions.

## Unreleased

### Added

- A compiler-only Stata command, `texpdf using ...`, with `saving()`,
  overwrite-safe `replace`, and `texpdf, version`.
- A native Stata plugin containing an isolated target helper, Tectonic 0.17.0,
  and a curated academic TeX resource bundle for offline compilation.
- Structured diagnostics, ABI panic containment, shell-escape denial, atomic
  output installation, and recovery after failed compilations.
- Fixture-backed support for mathematics, tables, layout, PDF/PNG figures,
  fonts, hyperlinks, BibTeX, and `natbib`, including spaces, Unicode, and
  relative inputs.
- Deterministic Stata package assembly, clean local `net install` tests, and
  exact-source Rust/licensed-Stata receipts.
- Universal macOS packaging and licensed runtime qualification on Apple
  Silicon and in an x86-64 Stata process under Rosetta.
- A 1,000-call licensed-Stata durability gate with injected failures, helper
  lifecycle sampling, and bounded post-warm-up RSS growth.
- Linux x86-64 packaging and licensed Stata/MP 18 and 19 qualification on RHEL
  8 with an enforced GLIBC 2.28 compatibility ceiling.
- Source-bound license inventories, notice collection, SCC accounting, and
  exact artifact identities in release and runtime receipts.
- A source-only synthetic real-world corpus for current latexlog reports,
  legacy `subfigure` output, and conventional multi-file economics manuscripts,
  including an optional hash-pinned latexlog regeneration contract.
- Development-tested offline resources for `colortbl`, `cleveref`, the
  `economic` package's `aer.bst`, and legacy `subfigure` compatibility.
- An opt-in `view` option that opens a successfully compiled PDF in the
  operating system's default viewer without changing batch-mode defaults.
- Two self-contained, one-click help examples for manual `file write` report
  construction and the suggested but optional `latexlog` workflow.

### Changed

- Release readiness now distinguishes active development, immutable candidate
  source, target runtime evidence, and public-distribution authorization.
- Automatic evidence publishers preserve the frozen release-candidate source
  instead of replacing it with later green development commits.
- Release and distribution policy now defines SSC as the stable user channel,
  GitHub final tags as immutable snapshots, and `main` as development.
- Bundle selection name/version now live in the pinned bundle lock, and current
  development identity is recorded separately from frozen candidate evidence.

### Fixed

- Real-world modern corpus figures now contain obvious navy/orange color, and
  manifest validation rejects declared color PDF/PNG assets whose drawing
  content is actually monochrome. Snapshot normalization also preserves the
  intended orientation of Stata PDF graphs instead of auto-rotating a panel.
- The legacy blackwhite corpus now embeds two real monochrome PDF graphs instead
  of empty framed placeholders, with manifest checks for inclusion and color.
- Exact bundle reconstruction preserves every metadata field required by the
  embedded Rust bundle reader.
- Linux pkgconf probes use the same GNU feature environment as the compiled
  bootstrap and invalidate older incompatible cache entries.
- Temporary paths, Python selection, and the licensed-Stata lock work across
  macOS and Linux.
- Release builds reject stale helpers whose embedded bundle identity differs
  from regenerated bundle metadata.

No final version has been released yet. The existing private RC checkpoints
remain prerelease evidence and are never eligible for SSC submission.
