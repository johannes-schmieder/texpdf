# Release qualification records

This directory records target-specific evidence for the plugin binaries
published as `v0.1.0` and for later release work.

The immutable [`v0.1.0`](https://github.com/johannes-schmieder/texpdf/releases/tag/v0.1.0)
tag and GitHub Release define the stable version. The identical combined
archive has been submitted to SSC and is awaiting publication. `main` remains
development; RC evidence is never eligible for SSC.

`targets.json` is deliberately fail-closed. A target entry is complete only
when it contains:

- the exact source SHA;
- target triple;
- plugin SHA-256 and byte size;
- embedded bundle SHA-256;
- Stata version/edition;
- a successful actual Stata runtime result on that platform.

Build-only artifacts keep `stata_runtime_qualified: false`, even when Rust
tests and native linking succeed. Version 0.1.0 qualifies macOS Apple Silicon,
Linux x86-64, and Windows x86-64 under the recorded release policy. The
universal macOS binary retains an inspected but runtime-untested Intel
compatibility slice. Linux includes the GLIBC 2.28 audit and licensed Stata/MP
18 and 19 receipts. Windows combines the exact final hosted build/binary audit
with the owner-approved, diff-validated RC2 runtime carry-forward recorded in
`windows-runtime-equivalence.json`.

Hosted workflows may build Windows, Linux, and macOS development artifacts,
but build-only outputs remain unsupported. Linux release qualification is
performed on BU SCC with `ci/scc/`; `READINESS.json` and `READINESS.md` are
generated from canonical records by `tools/sync_project_state.py`.

`publication.json` records the public-repository audit, verified final GitHub
release, archive hashes, preserved RC.1 state, and current SSC-submission
status. `READINESS.json` and `READINESS.md` are generated from the canonical
records and currently contain no release blockers.
