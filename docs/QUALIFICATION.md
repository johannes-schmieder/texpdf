# Qualification record

This document separates demonstrated behavior from intended support. The
machine-readable records under `.ci/stata/results/` and `release/` are the
source of truth.

## Public 0.1.0 qualification

Version 0.1.0 is published from source
`be8f9aead479386d102a86ee8d2ad56780c66eb2`. Its required targets are macOS
Apple Silicon, Linux x86-64, and Windows x86-64. The generated readiness record
reports both `candidate_ready=true` and `public_release_ready=true`.

The distributed macOS plugin remains universal. Its x86-64 slice is built,
inspected, and hash-bound to the package, but the project has no Intel/Rosetta
runtime test capacity and makes no runtime-qualification claim for that slice.

## Evidence boundary

The final source differs from the fully licensed Windows RC2 runtime source
only in verified release metadata and packaging hygiene. The exact final
Windows package independently passed the hosted Rust/corpus, static-CRT, PE,
license, and package audits. The owner-approved carry-forward and the failed
final-source controller-deadline attempt are recorded without relabeling that
attempt as a pass in `../release/windows-runtime-equivalence.json`.

## macOS qualification

The universal package is built from the exact final source. Its ARM64 slice was
exercised in licensed Stata, including the quick
corpus and a 1,000-compile memory-stress run with injected failures and
post-error recovery. The x86-64 slice receives build and binary inspection only.
Historical Rosetta evidence does not qualify the public artifact or establish
ongoing Intel support.

Authoritative records:

- `.ci/stata/results/be8f9aead479386d102a86ee8d2ad56780c66eb2.json`
- `release/macos-universal.json`
- `release/memory-stress-macos-arm64.json`
- `release/targets.json`

## Linux qualification

The Linux x86-64 release package was built and tested on the Boston University
Shared Computing Cluster's RHEL 8 environment. The build uses a fresh Cargo
target directory, records the pinned toolchain, and rejects symbols newer than
GLIBC 2.28. The exact packaged plugin was exercised in:

- licensed Stata/MP 18 with the quick corpus;
- licensed Stata/MP 18 with the 1,000-compile stress corpus;
- licensed Stata/MP 19 with the quick corpus.

The committed canonical record, including scheduler, package, binary-policy,
and runtime receipts, is `../release/linux-x86_64.json`.

## Windows qualification

The exact final Windows package was built with the static MSVC CRT and passed
the hosted Rust workspace, realistic corpus, PE dependency, licensing, and
deterministic packaging checks. Licensed Stata/MP 19 quick and 1,000-call
stress behavior is carried from the behaviorally equivalent RC2 source under
the explicit record described above. The canonical package and runtime record
is `../release/windows-x86_64.json`.

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

## Qualification boundary

The universal macOS Intel slice is supplied for compatibility but is not
runtime-qualified. Any code, bundle, or interface change after 0.1.0 requires
new evidence and a new release; it cannot inherit the immutable 0.1.0 record.
