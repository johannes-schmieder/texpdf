# Changelog

All notable changes to `texpdf` will be recorded here. The project follows
semantic versioning after the first public release.

## 0.1.0 — unreleased

### Added

- compiler-only Stata command `texpdf using ...`;
- explicit `saving()` and overwrite-safe `replace` behavior;
- `texpdf, version` with engine and embedded-bundle provenance;
- Tectonic 0.17.0 embedded in one native Stata plugin;
- deterministic in-memory curated TeX ZIP bundle;
- offline operation with shell escape disabled;
- structured, bounded diagnostics and panic containment at the ABI boundary;
- academic fixture coverage including mathematics, tables, hyperlinks, natbib,
  and internal BibTeX;
- Unicode/spaces/relative-input tests;
- deterministic Stata package assembly and local `net install` qualification;
- exact-source-SHA licensed Stata/Rust receipts;
- 100-call in-process stress qualification and a reusable higher-iteration
  stress profile;
- fail-closed dependency, TeX-resource, target, and release-readiness
  inventories.

### Qualified

The comprehensive macOS Apple Silicon development checkpoint is
`5d85840783ad4406a1606e5b3af09a06cca2f657` under Stata/MP 18.

### Not yet public-release qualified

- complete embedded package/font license inventory;
- final cleaned artifact checksums;
- macOS Intel/universal runtime;
- Windows x86-64 runtime;
- Linux x86-64 runtime;
- high-iteration memory/safety gate.
