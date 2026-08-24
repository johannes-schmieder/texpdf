# texpdf status

Updated: 2026-08-24

## Summary

The compiler-only macOS Apple Silicon product is implemented and end-to-end
qualified. `texpdf` runs as one native Stata plugin containing Tectonic and a
curated offline TeX bundle.

```stata
texpdf using document.tex
texpdf using document.tex, saving(document.pdf) replace
texpdf, version
```

## Last exact green product checkpoint

Source `a42f29fbeefd41811475d47e066e1ffea5290bfd` passed the `quick`
profile with:

```text
overall       success
Rust          success
Rust mode     repository-engine
licensed Stata success
platform      macOS Apple Silicon
Stata         Stata/MP 18, bundle 18.0.130
```

The immutable receipt required all of:

- `TEXPDF IN PROCESS STRESS PASS`;
- `TEXPDF NET INSTALL PASS`;
- `TEXPDF FULL ENGINE STATA PASS`;
- `TEXPDF STATA MATA SMOKE PASS`.

The qualified artifact measurements are:

| Component | Bytes | Binary size |
|---|---:|---:|
| Curated embedded bundle | 6,690,289 | 6.38 MiB |
| Standalone ARM64 plugin | 49,997,392 | 47.68 MiB |
| Deterministic Stata ZIP | 23,475,982 | 22.39 MiB |

The bundle contains 557 logical files. Exact hashes are recorded in
`docs/generated/CURRENT_ARTIFACT.md` and `release/targets.json`.

## Current branch condition

The latest source checkpoint before this documentation cleanup is
`8a7466dddb8bcda7ac8b748b549aa5bf96666279`. Its CI receipt is red because
`cargo fmt --check` found formatting differences in three newly added Rust test
files. The Rust step therefore stopped before staging the plugin, and the
subsequent Stata lane reported `r(601)` because `_texpdf_plugin.plugin` was not
present.

This is a CI/source-formatting regression, not evidence that the last qualified
compiler or embedded bundle stopped working. The immediate engineering task is
to format those tests and obtain a new exact-SHA green receipt for current
`main`.

## Qualified behavior

The green macOS ARM64 checkpoint covers:

- native plugin loading and `texpdf, version`;
- real PDF compilation with no system TeX or runtime network bundle;
- the declared academic/econometric package corpus;
- mathematics, tables, hyperlinks, PDF/PNG figures, Latin Modern/TeX Gyre,
  `natbib`, and internal BibTeX;
- relative inputs, spaces, and Unicode paths;
- default output naming, `saving()`, overwrite protection, and `replace`;
- malformed TeX, missing inputs/packages, and post-error recovery;
- atomic preservation of an existing PDF after failed replacement;
- deterministic package assembly and local `net install`;
- 100 successful in-process compile calls with periodic injected failures;
- shell escape disabled and selected dependency/network-policy checks.

## v1 release gates still open

1. Restore current `main` to an exact-SHA green Rust/Stata receipt.
2. Complete the file-to-package/font license mapping and ship all required
   Rust, native-library, TeX, and font notices.
3. Complete and review the high-iteration memory/safety qualification.
4. Build and load-test macOS Intel/universal, Windows x86-64, and Linux x86-64
   plugins in actual licensed Stata runtimes.
5. Run the clean-machine, offline, fail-closed release audit and publish signed
   GitHub Release / `net install` assets.

Only macOS Apple Silicon is currently marked runtime-qualified in
`release/targets.json`. Hosted or cross-compiled binaries must not be described
as supported until the matching Stata runtime receipt exists.