# texpdf implementation record

Updated: 2026-08-24

## Product

`texpdf` is implemented as a compiler-only Stata command:

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
texpdf, version
```

The native artifact contains the Stata bridge, Tectonic 0.17.0, its native
engine dependencies, and a deterministic curated resource ZIP. Runtime
compilation neither invokes nor consults a system TeX installation and does not
download packages.

## Architecture

```text
Stata ado syntax and result handling
  -> SPI 3.0 Rust cdylib (`pginit`, `stata_call`)
  -> texpdf-core request/result/error API
  -> Tectonic processing session
  -> embedded in-memory ZIP bundle
  -> staged PDF
  -> atomic final-output installation
```

The Stata-facing layer handles syntax, paths, errors, and `r()` results. The
Rust core owns compilation, diagnostics, bundle provenance, temporary output,
and atomic installation. Tectonic types do not cross the public project API.

## Implemented guarantees

- one plugin file per platform;
- no runtime TeX executable, resource download, or remote bundle provider;
- shell escape disabled;
- structured and bounded diagnostics;
- Rust panic containment at the ABI boundary;
- overwrite protection and atomic final installation;
- an existing PDF remains intact after an ordinary failed replacement compile;
- relative project inputs and figures;
- spaces and Unicode paths;
- internal BibTeX/`natbib` processing;
- engine/bundle provenance returned to Stata;
- deterministic package layout and local `net install` test;
- exact-source-SHA CI receipts.

## Exact qualified macOS ARM64 baseline

The current target registry points to source:

```text
a42f29fbeefd41811475d47e066e1ffea5290bfd
```

Its immutable `quick` receipt reports overall, Rust, and licensed-Stata success
in `repository-engine` mode on Stata/MP 18 for Apple Silicon. Required markers
cover full-engine compilation, package installation, generic smoke tests, and
100 in-process compile calls with periodic injected TeX failures.

Exact artifacts:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Curated bundle ZIP | 6,690,289 | `05688ffcca2e82a12143c836708e3dc3b811a30dbe2b74caf951eb7b409792ab` |
| ARM64 plugin | 49,997,392 | `185e4094c0d9835af199a3602fa8cd6ffa62a0da09c43c7267018b8ecb622298` |
| Stata package ZIP | 23,475,982 | `efe6db8333ef15a0c2b6f39c31cb6c958c1b19bace7555e686c8e2c935231f3c` |

The embedded bundle contains 557 files and has Tectonic content digest
`273502edfafe0a6adcdd19c0659965bcf0ebea26cacc1ad372439b80fd7a2a81`.

## Compatibility evidence

The qualified fixture set covers:

- LaTeX core, AMS math, and `mathtools`;
- common academic table and layout packages;
- PDF and PNG figures;
- hyperlinks and references;
- Latin Modern and TeX Gyre fixtures;
- BibTeX and `natbib`;
- missing-package, malformed-input, overwrite, path, and recovery behavior.

The project deliberately distinguishes “embedded”, “fixture-qualified”, and
“runtime-supported”. A resource present in the ZIP is not automatically part of
the public compatibility contract.

## Security and failure boundary

The engine executes in Stata's process. Rust unwinds are contained, but
`catch_unwind` cannot intercept every process-level abort or native-library
signal. The release gate therefore includes repeated-call, malformed-input,
memory-growth, shell-escape, and dependency-policy tests. See `SECURITY.md` for
the trust boundary.

## Platform boundary

Only `aarch64-apple-darwin` is currently runtime-qualified. macOS Intel,
Windows x86-64, and Linux x86-64 remain unsupported until native artifacts have
been loaded and tested in licensed Stata on those targets. Build-only results
must not be marketed as runtime support.

## Release boundary

The product implementation is substantially complete on macOS ARM64. Public
binary release remains fail-closed on:

- a complete Rust/native/TeX/font license and notice inventory;
- the reviewed high-iteration memory/safety gate;
- actual Stata runtime qualification for every advertised target;
- clean-machine offline release testing and checksum-bound public assets.

`STATUS.md` records the live branch state; `PLAN.md` is the remaining execution
roadmap.