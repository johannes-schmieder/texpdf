# texpdf development status

Updated: 2026-08-24

## Current phase

The compiler-only macOS Apple Silicon implementation is functional and
end-to-end qualified. `texpdf` loads as one native Stata plugin containing
Tectonic and a curated offline TeX resource bundle.

The qualified public interface is:

```stata
texpdf using document.tex
texpdf using document.tex, saving(document.pdf) replace
texpdf, version
```

## Exact qualified checkpoint

Source `63b997d290ec3adde0af33dbb49a96972d1e30c9` passed the `quick`
profile with overall, Rust, and licensed-Stata status all `success`.

Qualification environment:

- macOS Apple Silicon;
- Stata/MP 18, bundle 18.0.130;
- Rust 1.97.1;
- Tectonic 0.17.0;
- CI run 32724852879.

The immutable receipt required all of:

- `TEXPDF FULL ENGINE STATA PASS`;
- `TEXPDF NET INSTALL PASS`;
- `TEXPDF STRESS PASS`;
- `TEXPDF STATA MATA SMOKE PASS`.

## Qualified artifact sizes

- Curated embedded resource bundle: **6,692,142 bytes** (6.38 MiB), 477 files.
- Standalone macOS ARM64 plugin: **49,996,816 bytes** (47.68 MiB).
- Deterministic Stata installation ZIP: **23,480,504 bytes** (22.39 MiB).
- Installed package tree: **50,007,160 bytes** (47.69 MiB).

Exact hashes and provenance are recorded in `bundle/QUALIFICATION.json` and
`bundle/curated-manifest.json`.

## Qualified behavior

The licensed Stata/Rust tests cover:

- plugin loading and version reporting;
- real PDF compilation with no system TeX executable or runtime network bundle;
- mathematics, tables, figures/layout packages, hyperlinks, natbib, and
  internal BibTeX processing;
- the complete declared academic package corpus;
- relative inputs and graphics;
- paths containing spaces and Unicode;
- default output naming, `saving()`, and `replace`;
- missing inputs, existing outputs, malformed TeX, and post-error recovery;
- deterministic package assembly and local `net install`;
- 100 successful compile calls in one Stata process with periodic injected TeX
  failures.

## Remaining release gates

The implementation is not yet advertised as a public cross-platform v1 release.
The remaining gates are:

1. complete the package/font-level license inventory and required notices;
2. build and test macOS Intel/universal, Windows x86-64, and Linux x86-64
   plugins;
3. run licensed Stata runtime qualification on each supported platform;
4. run the final clean-machine/offline release profile and publish GitHub
   Release assets.

The current macOS ARM64 artifact is a qualified development/release candidate,
not an unqualified prototype.
