# Qualification record

This document separates demonstrated behavior from intended support. The
machine-readable records under `.ci/stata/results/` and `release/` are the
source of truth.

## Active public 0.1.0 qualification

The active scope requires macOS Apple Silicon, Linux x86-64, and Windows
x86-64 at one exact source SHA. The public `v0.1.0-rc2` and final
`v0.1.0` each require their own complete evidence matrix; the final metadata
commit is requalified rather than inheriting RC evidence. Until those records
are complete, `release/READINESS.json` must report the public release as not
ready.

The distributed macOS plugin remains universal. Its x86-64 slice is built,
inspected, and hash-bound to the package, but the project has no Intel/Rosetta
runtime test capacity and makes no runtime-qualification claim for that slice.

## Historical private RC.2 evidence

The private `0.1.0-rc.2` candidate is bound to source:

```text
7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8
```

The candidate includes complete source-bound license evidence. Its required
runtime targets are macOS Apple Silicon, macOS Intel, and Linux x86-64.

## macOS qualification

For the active release, the universal package is built from the exact candidate
source. Its ARM64 slice is exercised in licensed Stata, including the quick
corpus and a 1,000-compile memory-stress run with injected failures and
post-error recovery. The x86-64 slice receives build and binary inspection only.
Older private candidate history included a Rosetta runtime run; that historical
evidence does not qualify the new public artifacts or establish ongoing Intel
support.

Authoritative records:

- `.ci/stata/results/7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8.json`
- `release/macos-universal.json`
- `release/memory-stress-macos-arm64.json`
- `release/targets.json`

## Linux qualification

The Linux x86-64 candidate was built and tested on the Boston University
Shared Computing Cluster's RHEL 8 environment. The build uses a fresh Cargo
target directory, records the pinned toolchain, and rejects symbols newer than
GLIBC 2.28. The exact packaged plugin was exercised in:

- licensed Stata/MP 18 with the quick corpus;
- licensed Stata/MP 18 with the 1,000-compile stress corpus;
- licensed Stata/MP 19 with the quick corpus.

The immutable SCC run is:

```text
/projectnb/welfgr/texpdf/runs/20260825T1700Z-7aa7b16-linux-rc2
```

Its SGE jobs are build `7308886`, Stata 18 quick `7308887`, Stata 18
stress-1000 `7308888`, and Stata 19 quick `7308889`. All have `failed=0` and
`exit_status=0`. The committed canonical record is
`release/linux-x86_64.json`.

## Demonstrated behavior

The qualification corpus covers:

- loading the generated plugin and compiling without a runtime TeX executable;
- mathematics, `booktabs`, `hyperref`, natbib, and internal BibTeX;
- default and explicit output naming and replacement protection;
- spaces and Unicode in paths and relative `\input` resolution;
- clean errors for missing input, existing output, and malformed TeX;
- continued plugin usability after ordinary TeX failures;
- exact artifact identity across packaging and runtime receipts;
- complete bundled license notices and source-bound audit evidence.

## Deliberately deferred

The historical candidate does not certify Windows x86-64, the newer realistic
corpus bundle, or the current cross-platform distribution layout. It remains
valid only for its recorded bytes and must not be reused for public promotion.
