# Implementation record

Updated: 2026-08-24

## Product

`texpdf` is implemented as a compiler-only Stata command:

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
texpdf, version
```

The command calls one native plugin containing the Rust bridge, Tectonic
0.17.0, statically linked native engine dependencies, and a deterministic
curated TeX resource ZIP. Runtime compilation does not require or consult a
system TeX installation and does not download packages.

## Implemented behavior

- SPI 3.0 plugin ABI and Stata 14.1-compatible ado syntax;
- direct in-process Tectonic compilation;
- shell escape disabled;
- explicit embedded in-memory bundle;
- structured and bounded diagnostics;
- panic containment at the Rust ABI boundary;
- overwrite protection;
- final output installation only after successful typesetting;
- preservation of an existing PDF after an ordinary failed replacement
  compile;
- spaces and Unicode paths;
- relative project inputs;
- internal BibTeX/natbib processing;
- returned engine and bundle provenance;
- deterministic Stata package layout and local `net install` test;
- exact-SHA CI receipts;
- reusable artifact, license-inventory, stress, cross-platform build-only, and
  macOS universal workflows.

## Comprehensive qualified source

```text
5d85840783ad4406a1606e5b3af09a06cca2f657
```

Its immutable `quick` receipt reports:

```text
overall       success
Stata         success
Rust          success
Rust mode     repository-engine
platform      macOS Apple Silicon
Stata         Stata/MP 18
```

It required full-engine, package installation, generic smoke, and 100-call
in-process stress PASS markers.

A later path experiment regressed the suite. Commit
`63b997d290ec3adde0af33dbb49a96972d1e30c9` restored the exact
stress-qualified core implementation. The immutable receipt for any later
source checkpoint remains authoritative; branch ancestry alone is not a pass.

## Artifact scale

The qualified development build measured approximately:

```text
curated TeX ZIP       6.62 MB
standalone plugin    49.93 MB
```

The exact-SHA artifact publisher records precise bytes and SHA-256 values under
`.ci/artifacts/` for subsequent successful engine runs.

## Release boundary

The macOS Apple Silicon compiler is implemented and demonstrated. Public v1 is
not declared complete until:

- the embedded resource inventory is license-complete;
- the final cleaned plugin/package checksums are recorded;
- the high-iteration safety gate is reviewed;
- macOS Intel, Windows x86-64, and Linux x86-64 plugins pass actual Stata
  runtime tests;
- the fail-closed release-readiness command succeeds.

Build-only artifacts are never labeled as supported runtime targets.
