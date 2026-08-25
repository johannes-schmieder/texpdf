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

### Changed

- Release readiness now distinguishes active development, immutable candidate
  source, target runtime evidence, and public-distribution authorization.
- Automatic evidence publishers preserve the frozen release-candidate source
  instead of replacing it with later green development commits.
- Release and distribution policy now defines SSC as the stable user channel,
  GitHub final tags as immutable snapshots, and `main` as development.

### Fixed

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
