# texpdf implementation plan

Status: active implementation  
Updated: 2026-08-24  
Development branch: **main**

## 1. Mission

`texpdf` is a Stata package and command that compiles a complete LaTeX document to PDF:

```stata
texpdf using paper.tex
texpdf using paper.tex, saving(paper.pdf) replace
```

The user must not need TeX Live, MacTeX, MiKTeX, Tectonic, Rust, a compiler, an Internet connection, or any other typesetting installation. The released package will contain a native Stata plugin with the Tectonic engine and its supported TeX resources embedded in that plugin.

The repository, package, command, and native plugin are all named `texpdf`.

## 2. Owner decisions — resolved 2026-08-24

These decisions are authoritative unless Johannes explicitly changes them.

1. **One plugin file is the product goal.** Each supported platform receives one native `texpdf.plugin` artifact containing the engine and resource bundle. A helper executable is not part of the planned product architecture. If upstream process-fatal behavior makes this impossible, development stops at an explicit architecture review rather than silently changing the distribution model.
2. **Minimum Stata ABI: Stata 14.1+ / SPI 3.0.** Initial runtime certification is Stata/MP 18 because that is the licensed CI installation. Ado code must avoid unnecessarily raising the minimum version.
3. **Bundle breadth: academic/econometric core, roughly 20–50 MB per platform if practical.** Reliability and common package coverage take precedence over an arbitrary byte cap.
4. **Bibliographies: BibTeX plus natbib in v1.** Biber/biblatex are deferred.
5. **Project source license: MIT.** Tectonic, TeX support files, fonts, and Stata interface files retain their own upstream licenses/notices.
6. **Distribution: GitHub Releases and Stata `net install` first.** SSC is a later compatibility/policy decision.
7. **v1 is a compiler only.** No Stata report DSL, table authoring language, or document templating framework is in scope.
8. **Development happens directly on `main`.** Changes are committed as small coherent checkpoints and pushed frequently. History is not rewritten.

## 3. Non-negotiable product properties

### 3.1 Standalone and offline

After installation, normal compilation must:

- work without a system TeX distribution or Tectonic executable;
- perform no runtime package downloads and require no network;
- ignore the user's `TEXMF`, TeX cache, package manager, and shell `PATH`;
- include all advertised classes, packages, formats, fonts, BibTeX styles, and support data;
- use only the plugin, the user's source tree/assets, and temporary files;
- report the exact engine and bundle versions/digests.

CI must include an offline qualification that hides system TeX executables and rejects any attempted network access.

### 3.2 One native artifact per platform

The release artifact is a single `texpdf.plugin` for each target. The curated Tectonic bundle is transformed into a deterministic ZIP bundle and incorporated with `include_bytes!()`. `tectonic_bundles::zip::ZipBundle` reads the embedded bytes through an in-memory seekable cursor. No permanent TeX tree is extracted on installation or first use.

Generated format files and transient outputs may use a private temporary/cache directory. They are derived state, not a separately distributed resource tree.

### 3.3 Safe Stata behavior

Malformed TeX, missing assets, unsupported packages, I/O errors, and ordinary engine failures must return a Stata error without terminating or corrupting Stata. Shell escape is forcibly disabled. Rust panics must be caught at every Rust/C boundary and must never unwind through C or Stata.

Tectonic includes native/C/C++ engine code, so `catch_unwind` is not sufficient protection against every possible abort or signal. Repeated-call, malformed-input, and memory-growth stress tests are therefore release gates for the required in-process design.

### 3.4 Reproducibility and provenance

Releases pin and record:

- Rust toolchain;
- Tectonic 0.17.x source/crate version and complete `Cargo.lock`;
- bundle source URL/snapshot and raw archive SHA-256;
- deterministic transformed ZIP digest;
- bundle file manifest and upstream license inventory;
- release build flags and target triple;
- plugin SHA-256.

Runtime output must not depend on packages or fonts installed elsewhere on the machine.

## 4. Public Stata API

### 4.1 Initial syntax

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
texpdf, version
```

Rules:

- without `saving()`, replace `.tex` with `.pdf`;
- refuse to overwrite an existing PDF unless `replace` is specified;
- resolve relative includes and figures relative to the primary source directory;
- accept paths containing spaces and Unicode;
- compile a complete document only;
- suppress normal TeX chatter and print concise diagnostics on failure.

A later `log()` option may retain the full engine log, but it is not required for the first end-to-end milestone.

### 4.2 Returned results

`texpdf` is `rclass`. Planned stable results are:

```text
r(pdf)             output PDF path
r(engine)          tectonic
r(engine_version)  pinned Tectonic version
r(bundle_version)  texpdf bundle identifier
r(bundle_digest)   transformed bundle digest
r(warnings)        warning count
```

The native result record is versioned and line-oriented so Stata 14.1 does not need a JSON parser. Large logs are never transported through Stata macros.

## 5. Architecture

```text
texpdf.ado
    |
    v
private plugin command / SPI 3.0 C shim
    |
    v
texpdf-stata Rust cdylib
    |
    v
texpdf-core
    |
    +-- Tectonic 0.17 driver API
    +-- embedded deterministic ZIP bundle
    +-- structured status backend
    +-- filesystem/output policy
    |
    v
PDF + versioned result record
```

### 5.1 Repository layout

```text
Cargo.toml
Cargo.lock
rust-toolchain.toml
PLAN.md
STATUS.md
README.md
LICENSE

crates/
  texpdf-core/
  texpdf-stata/

vendor/stata-plugin/
  stplugin.c
  stplugin.h
  ORIGIN.md

bundle/
  README.md
  bundle.lock.toml
  packages.toml
  generated/              # build output, not committed
  licenses/

tools/
  prepare_bundle.py

stata/
  texpdf.ado
  _texpdf_plugin.ado
  texpdf.sthlp
  texpdf.pkg
  stata.toc
  tests/

tests/fixtures/
ci/
.github/workflows/
```

### 5.2 Rust core

`texpdf-core` is independent of Stata and exposes only project-owned types. Tectonic types do not leak into its public API.

```rust
pub struct CompileRequest {
    pub input: PathBuf,
    pub output: PathBuf,
    pub replace: bool,
    pub keep_log: bool,
}

pub struct CompileResult {
    pub output: PathBuf,
    pub warning_count: usize,
    pub engine_version: String,
    pub bundle_version: String,
    pub bundle_digest: String,
}

pub fn compile(request: &CompileRequest) -> Result<CompileResult, TexPdfError>;
```

The implementation uses `ProcessingSessionBuilder` with:

- restrictive default security;
- explicit primary input and filesystem root;
- explicit output directory;
- format `latex`;
- PDF output;
- explicit embedded bundle;
- shell escape forcibly disabled;
- stdout suppressed;
- structured status capture;
- automatic TeX/BibTeX reruns.

### 5.3 Bundle transformation and embedding

The initial source bundle is Tectonic's pinned v33 indexed-tar resource. `tools/prepare_bundle.py`:

1. downloads the raw bundle and its gzip-compressed index into a persistent CI cache;
2. verifies the locked raw SHA-256 before use once the first trusted digest is recorded;
3. parses logical file names and byte ranges from the index;
4. copies those logical resources into a deterministic ZIP archive;
5. preserves/provides `SHA256SUM` for Tectonic's bundle interface;
6. emits a file manifest, transformed ZIP SHA-256, file count, compressed size, and license/provenance metadata;
7. writes `bundle/generated/texpdf-bundle.zip` for compile-time embedding.

The first working prototype may embed the full v33 bundle. M5 then reduces it to the selected academic dependency closure while preserving fixture coverage. The final release must not fetch this bundle at runtime.

### 5.4 Stata ABI boundary

Use Stata SPI 3.0 through a small C shim compiled together with the Rust `cdylib`:

- C owns `pginit`/`stata_call` and Stata calling-convention details;
- Rust receives UTF-8 command arguments through a narrow C ABI;
- Rust catches panics and writes a versioned result record atomically;
- the C shim returns bounded Stata return codes and emits only catastrophic bridge errors;
- no Rust object or allocation crosses the ABI boundary.

The build copies/renames the resulting platform library to `texpdf.plugin`. The official Stata plugin interface source is vendored with an origin/version record and redistribution notice.

## 6. v1 supported bundle

The advertised target is an academic/econometric core, subject to measured dependency closure and license audit.

### Core and math

- LaTeX base and standard tools/graphics
- `amsmath`, `amssymb`, `amsfonts`, `amscls`
- `mathtools`

### Tables

- `booktabs`, `array`, `longtable`, `tabularx`
- `multirow`, `threeparttable`, `threeparttablex` when economical
- `dcolumn`, `siunitx`, `adjustbox`

### Figures and layout

- `graphicx`, `xcolor`, `geometry`
- `float`, `placeins`, `rotating`, `pdflscape`
- `caption`, `subcaption`

### Formatting and references

- `hyperref`, `url`, `setspace`, `enumitem`, `fancyhdr`
- `titlesec` when compatible/economical
- `microtype`
- `natbib`, BibTeX engine, and common BibTeX/natbib styles

### Fonts

- everything required for deterministic default LaTeX output;
- Latin Modern;
- a small justified TeX Gyre set if size and licensing allow.

### Explicit v1 exclusions

- Beamer;
- TikZ/PGF and PSTricks;
- Biber/biblatex;
- minted/Pygments and shell-dependent packages;
- arbitrary external programs;
- broad language and font collections;
- remote package retrieval.

Every advertised top-level package requires a compiling fixture. Presence in the ZIP alone is not evidence of support.

## 7. CI and development discipline

### 7.1 Direct-to-main workflow

For every coherent source checkpoint:

1. commit and push directly to `main`;
2. record the full source SHA;
3. wait for/read `.ci/stata/results/<source-sha>.json`;
4. require exact `tested_sha`, `profile`, `status=success`, `stata_status=success`, and `rust_status=success`;
5. inspect workflow jobs/artifacts on failure;
6. fix in another small commit without rewriting history.

Receipt-publisher `[skip ci]` commits are not source checkpoints. Missing receipts are not passes.

### 7.2 Fast checks

Every normal source push runs:

- bundle preparation/check when required;
- `cargo fmt --all --check`;
- strict workspace Clippy;
- workspace tests;
- native macOS arm64 plugin build;
- licensed Stata quick tests after the plugin build.

The workflow must build Rust before Stata once native tests are enabled.

### 7.3 Deeper profiles

- `version`: runner/tool inventory;
- `smoke`: plugin load and one tiny compile;
- `quick`: core success/error/path tests plus Stata API tests;
- `corpus`: academic fixture corpus;
- `stress`: repeated calls and malformed input;
- `release`: clean/offline package qualification and artifact inventory.

Long corpus/stress/release profiles are manual or release-triggered, not run on every small commit.

## 8. Test strategy

### Rust tests

- embedded ZIP opens and locked digest matches;
- minimal article, math, table, figure, and natbib/BibTeX fixtures compile;
- syntax errors, missing package/assets, permissions, and overwrite policy fail cleanly;
- no network provider is compiled into or consulted by runtime code;
- diagnostics are bounded and valid UTF-8;
- output naming and result records are correct;
- repeated compiles clean temporary files;
- panic injection is contained at the exported ABI.

### Licensed Stata tests

- `which texpdf` and plugin load;
- default output and `saving()`;
- `replace` semantics;
- spaces and Unicode paths;
- relative includes and figures;
- bad TeX and missing inputs return expected Stata codes;
- `r()` results;
- repeated calls in one Stata process;
- invocation from a directory unrelated to the installed package.

### Safety/stress gate

Before release, run thousands of compilations in one Stata process, malformed/corrupt fixtures, TeX capacity failures, invalid images/fonts, panic injection, cancellation tests, and memory-growth measurements. Stata must remain usable after recoverable failures. Known upstream abort/signal paths must be documented and either eliminated, avoided by policy, or treated as blockers for the one-plugin release goal.

## 9. Platform targets

Required release targets:

- macOS Apple Silicon;
- macOS Intel, preferably combined with Apple Silicon as a universal plugin;
- Windows x86-64 MSVC;
- Linux x86-64 GNU.

A platform is supported only after the final plugin loads in actual Stata and compiles the offline smoke corpus. Hosted Rust builds alone do not certify Stata integration.

## 10. Licensing and release packaging

`texpdf` project code is MIT licensed. Before a public release:

- retain Tectonic's MIT notices;
- record and audit native dependencies;
- retain Stata interface provenance/copyright notices;
- generate a bundle-level package/font license inventory;
- include all required notices in source and GitHub release assets;
- publish plugin and manifest SHA-256 values;
- verify `net install` from a clean GitHub release layout.

## 11. Size and performance targets

Measure on each target:

- plugin size and embedded bundle size;
- installed size;
- cold first compile and warm repeated compile time;
- peak resident memory and repeated-call growth;
- format-cache size and lifecycle.

The planning target is 20–50 MB per plugin, but common-package reliability may justify a larger measured artifact. Optimize resource selection before introducing fragile compression/loading tricks.

## 12. Milestones

### M0 — Decisions and CI bootstrap

- [x] Repository/package/command named `texpdf`.
- [x] Licensed Stata/Rust exact-SHA CI on `main`.
- [x] Main-only development policy recorded.
- [x] Owner decisions D1–D7 resolved.
- [x] Detailed implementation plan updated.
- [x] MIT license selected.

### M1 — Rust/Tectonic core

- [ ] Create pinned Rust workspace and lockfile.
- [ ] Implement project-owned request/result/error types.
- [ ] Implement structured Tectonic status capture.
- [ ] Compile a minimal document through the Tectonic driver with an explicit bundle.
- [ ] Add success and bad-input unit tests.

Exit: Rust tests produce a valid PDF without invoking an external TeX executable.

### M2 — Embedded offline bundle

- [ ] Implement deterministic indexed-tar-to-ZIP transformer.
- [ ] Lock source and transformed digests.
- [ ] Embed ZIP bytes into `texpdf-core`.
- [ ] Compile with Tectonic network features disabled.
- [ ] Prove operation with system TeX hidden and network unavailable.

Exit: the Rust binary plus user input is sufficient to compile PDF.

### M3 — Native Stata bridge

- [ ] Vendor and document SPI 3.0 interface files.
- [ ] Implement C shim and panic-safe Rust ABI.
- [ ] Build/rename macOS arm64 `texpdf.plugin`.
- [ ] Pass licensed Stata plugin-load/version test.
- [ ] Implement versioned result transport.

### M4 — End-to-end command

- [ ] Implement `texpdf.ado`, `saving()`, and `replace`.
- [ ] Compile a minimal document from Stata.
- [ ] Return engine/bundle metadata.
- [ ] Handle spaces/Unicode and concise failures.
- [ ] Add `.sthlp`, `.pkg`, and `stata.toc`.

Exit: `texpdf using example.tex` passes licensed Stata CI without runtime TeX/network dependencies.

### M5 — Curated academic bundle

- [ ] Freeze package list and dependency closure.
- [ ] Add fonts and BibTeX/natbib.
- [ ] Add package-by-package fixtures.
- [ ] Generate license inventory.
- [ ] Measure and reduce artifact size safely.

### M6 — Robustness gate

- [ ] Malformed-input corpus.
- [ ] Repeated in-process compile stress.
- [ ] Memory/leak and panic/FFI tests.
- [ ] Confirm that the required one-plugin design is release-safe.

### M7 — Cross-platform artifacts

- [ ] macOS arm64 and x86-64/universal.
- [ ] Windows x86-64 MSVC.
- [ ] Linux x86-64 GNU.
- [ ] Actual Stata runtime qualification on every platform.

### M8 — Corpus and API freeze

- [ ] Expand realistic economics/academic corpus.
- [ ] Resolve common missing packages.
- [ ] Freeze syntax, return values, and error codes.
- [ ] Document Tectonic/pdfLaTeX differences and exclusions.

### M9 — GitHub release qualification

- [ ] Deterministic release builds and checksum manifest.
- [ ] Complete licenses/notices.
- [ ] Clean-machine offline tests on all supported systems.
- [ ] GitHub Release + `net install` layout.
- [ ] Full release profile green.

## 13. Definition of v1 success

On a clean supported machine containing Stata but no TeX installation, the user can install `texpdf` from a GitHub release and run:

```stata
texpdf using paper.tex, saving(paper.pdf)
```

The one shipped plugin compiles the documented academic source set completely offline, handles ordinary failures without destabilizing Stata, exposes engine/bundle provenance, and passes actual Stata tests on Windows, macOS, and Linux.
