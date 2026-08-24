# Qualification record

This document separates demonstrated behavior from intended support. The
immutable JSON receipts under `.ci/stata/results/` are the machine-readable
source of truth.

## Comprehensive macOS Apple Silicon checkpoint

Qualified source:

```text
5d85840783ad4406a1606e5b3af09a06cca2f657
```

Required receipt fields:

```text
profile       quick
status        success
stata_status  success
rust_status   success
rust_mode     repository-engine
```

The licensed Stata log required these markers:

```text
TEXPDF FULL ENGINE STATA PASS
TEXPDF NET INSTALL PASS
TEXPDF IN PROCESS STRESS PASS
TEXPDF STATA MATA SMOKE PASS
```

The checkpoint demonstrated:

- loading the generated plugin in Stata/MP 18 on Apple Silicon;
- compilation with the embedded curated bundle and no runtime TeX executable;
- mathematics, `booktabs`, `hyperref`, natbib, and internal BibTeX;
- default and explicit output naming;
- replacement protection;
- spaces and Unicode in paths;
- relative `\input` resolution;
- clean errors for missing input, existing output, and malformed TeX;
- continued plugin usability after an ordinary TeX failure;
- deterministic package assembly and a local `net install` test;
- 100 successful compile calls in one Stata process with periodic injected
  failures.

## Current artifact scale

The qualified development build measured approximately 6.62 MB for the
embedded resource ZIP and 49.93 MB for the complete standalone plugin. Exact
byte counts, digests, and package ZIP measurements belong in the generated
artifact manifests and must be committed in the final release qualification
record.

## What this does not certify

This checkpoint does not certify:

- macOS Intel or a universal Mach-O artifact;
- Windows x86-64;
- Linux x86-64;
- Stata releases other than the connected Stata/MP 18 installation;
- completeness of the third-party package/font license inventory;
- arbitrary TeX Live documents outside the documented compatibility tier;
- process safety under unbounded or adversarial input.

A target becomes supported only after its final plugin loads and compiles the
release corpus in an actual Stata process on that target.
