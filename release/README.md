# Release qualification records

This directory records target-specific evidence for the exact plugin binaries
that may eventually be published.

These records do not make `main` a stable distribution. Under
[`../RELEASING.md`](../RELEASING.md), `main` is development, a final `vX.Y.Z`
tag and GitHub Release freeze one stable version, and SSC distributes the
current supported final release. RC evidence is never eligible for SSC.

`targets.json` is deliberately fail-closed. A target entry is complete only
when it contains:

- the exact source SHA;
- target triple;
- plugin SHA-256 and byte size;
- embedded bundle SHA-256;
- Stata version/edition;
- a successful actual Stata runtime result on that platform.

Build-only artifacts must keep `stata_runtime_qualified: false`, even when Rust
tests and native linking succeed. The active public `0.1.0-rc2` scope requires
both macOS targets, Linux x86-64, and Windows x86-64. Linux also requires the
source-bound record in `linux-x86_64.json`, a glibc 2.28 binary-policy pass,
and licensed Stata/MP 18 and 19 receipts. Windows requires
`windows-x86_64.json`, static CRT evidence, and exact Stata/MP 19 quick and
stress receipts. No target is deferred.

Hosted workflows may build Windows, Linux, and macOS development artifacts,
but build-only outputs remain unsupported. Linux release qualification is
performed on BU SCC with `ci/scc/`; `READINESS.json` and `READINESS.md` are
generated from canonical records by `tools/sync_project_state.py`.

`publication.json` is written only after a full-history secret scan and
read-back verification of the live public GitHub settings. It binds the audit
tip to the active candidate source and records the preserved/superseded RC.1
state without modifying that historical tag or its assets.
