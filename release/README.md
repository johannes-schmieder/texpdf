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
tests and native linking succeed. The active private `0.1.0-rc.2` qualification
checkpoint requires
both macOS targets and Linux x86-64 in `scope.json`. Linux also requires the
source-bound record in `linux-x86_64.json`, a glibc 2.28 binary-policy pass,
and licensed Stata/MP 18 and 19 receipts. Windows is explicitly deferred;
public distribution and final `v0.1.0` have a separate blocker set.

Hosted workflows may build Windows, Linux, and macOS development artifacts,
but build-only outputs remain unsupported. Linux release qualification is
performed on BU SCC with `ci/scc/`; `READINESS.json` and `READINESS.md` are
generated from canonical records by `tools/sync_project_state.py`.
