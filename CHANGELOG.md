# Changelog

All notable changes to `texpdf` are recorded here. Semantic versioning begins
with the first public release.

## 0.1.0 — unreleased

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
- 100-call installed-plugin stress qualification plus helper-aware
  higher-iteration and parent/process-tree memory tooling;
- fail-closed dependency, resource, target, and release-readiness tooling.
- source-bound license and notice collection for both embedded Rust binaries,
  native libraries, and every embedded TeX/font resource.

### Remaining before public release

- review the high-iteration memory/safety result;
- qualify macOS Intel, Windows x86-64, and Linux x86-64 in actual Stata;
- pass the clean-machine offline release audit and publish GitHub assets.
