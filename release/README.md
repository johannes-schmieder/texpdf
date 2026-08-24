# Release qualification records

This directory records target-specific evidence for the exact plugin binaries
that may eventually be published.

`targets.json` is deliberately fail-closed. A target entry is complete only
when it contains:

- the exact source SHA;
- target triple;
- plugin SHA-256 and byte size;
- embedded bundle SHA-256;
- Stata version/edition;
- a successful actual Stata runtime result on that platform.

Build-only artifacts must keep `stata_runtime_qualified: false`, even when Rust
tests and native linking succeed. The active private `v0.1.0-rc.1` gate requires
the two macOS targets in `scope.json`. Windows and Linux are explicitly
deferred; public distribution and final `v0.1.0` have a separate blocker set.

The current comprehensive runtime evidence is for macOS Apple Silicon. Manual
workflows can build Windows, Linux, and macOS universal development artifacts,
but those outputs remain unsupported until they pass the release corpus inside
licensed Stata. `READINESS.json` and `READINESS.md` are generated from these
records by `tools/sync_project_state.py`.
