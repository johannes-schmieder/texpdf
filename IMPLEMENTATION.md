# texpdf implementation record

## Product

`texpdf` is a compiler-only Stata command:

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
texpdf, version
```

The installed native artifact contains the Stata bridge and a target-matching
compiler helper. The helper contains Tectonic 0.17.0, its native dependencies,
and a deterministic curated resource ZIP. Compilation does not consult a
system TeX installation or download packages.

## Architecture

```text
Stata ado syntax and result handling
  -> SPI 3.0 Rust cdylib (`pginit`, `stata_call`)
  -> SHA-256-verified embedded helper extraction
  -> direct child process with bounded timeout
  -> versioned result-file protocol
  -> texpdf-core request/result/error API
  -> Tectonic + embedded in-memory ZIP bundle
  -> staged PDF + atomic final-output installation
```

The bridge owns ABI safety, helper materialization, child lifecycle, protocol
validation, and Stata `r()` results. The helper owns compilation, diagnostics,
bundle provenance, temporary output, and atomic installation. Tectonic types do
not cross the process protocol or public project API.

## Implemented guarantees

- one installed plugin file per GitHub platform package and all three in the
  combined SSC package, with no separately distributed helper;
- target architecture and helper digest checked before execution;
- content-addressed private helper cache with invalid-cache replacement;
- direct no-shell execution and a configurable bounded timeout;
- helper identity, operation, protocol version, status, and digest validation;
- no system TeX executable, resource download, or remote bundle provider;
- shell escape disabled and diagnostics bounded;
- panic containment in both ABI bridge and helper dispatch;
- compiler/native crashes isolated from the Stata process;
- overwrite protection and atomic final installation;
- relative inputs, spaces and Unicode paths, figures, and BibTeX/`natbib`;
- deterministic package layout, local `net install`, and exact-source receipts.

## Evidence boundaries

The project distinguishes exact green source, exact artifact source, build
qualification, actual licensed-Stata runtime qualification, and failed stress
attempts. The current values live only in generated `STATUS.md`,
`release/READINESS.*`, `release/targets.json`, immutable `.ci` receipts, and
`docs/generated/CURRENT_ARTIFACT.md`.

## Compatibility evidence

The qualified fixture set covers LaTeX core, AMS mathematics, common academic
tables/layout, PDF and PNG figures, hyperlinks, Latin Modern and TeX Gyre,
BibTeX/`natbib`, paths, overwrite behavior, missing packages, malformed input,
and recovery. Embedded resources are not automatically advertised: support is
fixture- and runtime-evidence-backed.

## Security boundary

The compiler runs in a short-lived child process, not in Stata. The boundary
limits compiler crash persistence but is not an OS sandbox; TeX can still read
locally available inputs and consume resources. Timeout, malformed-input,
filesystem-boundary, memory-growth, and post-error recovery remain release
gates. See `SECURITY.md`.

## Platform and release boundary

Version 0.1.0 qualifies macOS ARM64, Linux x86-64, and Windows x86-64 under its
recorded evidence policy. Linux support enforces a
GLIBC 2.28 compatibility ceiling and licensed Stata/MP 18 and 19 tests. Windows
requires static CRT linkage and licensed Stata/MP 19. The universal macOS
artifact still carries a built and inspected x86-64 slice, but it is explicitly
untested and is not marketed as qualified runtime support.
