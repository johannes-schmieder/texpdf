# Changelog

All notable changes to `texpdf` are recorded here. Semantic versioning begins
with the first public release.

## 0.1.0-rc.2 — unreleased (private release candidate)

### Added

- Linux x86-64 packaging and licensed Stata/MP 18 and 19 qualification on
  RHEL 8 with an enforced glibc 2.28 compatibility ceiling;
- source-bound SCC scheduler, build, package, and runtime evidence;
- exact artifact identities in licensed-Stata receipts.

### Fixed

- exact bundle reconstruction now preserves every metadata field required by
  the embedded Rust bundle reader;
- Linux pkgconf declaration probes use the same GNU feature environment as the
  compiled bootstrap and invalidate older cached configurations;
- temporary paths, Python selection, and the licensed-Stata lock are portable;
- release builds reject stale helpers whose embedded bundle identity differs
  from the regenerated bundle metadata.

## 0.1.0-rc.1 — 2026-08-24 (private release candidate)

### Added

- compiler-only Stata command `texpdf using ...`;
- `saving()`, overwrite-safe `replace`, and `texpdf, version`;
- one native plugin embedding an isolated target helper, Tectonic 0.17.0, and
  a curated academic TeX ZIP;
- offline operation with no system TeX or runtime bundle download;
- structured diagnostics, ABI panic containment, and shell escape disabled;
- atomic final-output installation and failed-replacement preservation;
- fixture-backed mathematics, tables, layout, PDF/PNG figures, fonts,
  hyperlinks, BibTeX, and `natbib` coverage;
- spaces, Unicode, relative-input, missing-package, and post-error recovery
  tests;
- deterministic Stata package assembly and local `net install` qualification;
- exact-source-SHA Rust/licensed-Stata receipts;
- 1,000-call licensed-Stata durability qualification with injected failures,
  helper-process lifecycle sampling, and bounded post-warm-up RSS growth;
- fail-closed dependency, resource, target, and release-readiness tooling;
- source-bound license and notice collection for both embedded Rust binaries,
  native libraries, and every embedded TeX/font resource;
- deterministic universal macOS candidate packaging with full archive notices,
  per-slice embedded-helper provenance, and package checksums;
- exact-byte qualification of the same universal candidate package under
  Apple Silicon and an x86_64 Stata process under Rosetta.

### Remaining before public release

- qualify Windows x86-64 and Linux x86-64 in actual Stata;
- authorize public distribution and pass the final public-release audit;
- publish final `v0.1.0` assets and public installation URLs.
