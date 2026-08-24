# texpdf project plan

Status: design / bootstrap  
Updated: 2026-08-24  
Development branch: **main**

## 1. Mission

`texpdf` will be a Stata package whose primary command compiles LaTeX source to PDF without requiring the user to install TeX Live, MacTeX, MiKTeX, Tectonic, Rust, a C/C++ toolchain, or any other external typesetting software.

The target user experience is:

```stata
texpdf using paper.tex
```

with optional explicit output control:

```stata
texpdf using paper.tex, saving(paper.pdf) replace
```

The core engine will be **Tectonic**, embedded into the native `texpdf` backend. Tectonic is preferred over a direct pdfTeX/Web2C port because it is already designed as an embeddable TeX/LaTeX engine, has a Rust API, performs the full TeX/XDV/PDF workflow, and exposes bundle abstractions suitable for an offline embedded resource set.

The project name, repository name, Stata package name, and main command are all **`texpdf`**.

## 2. Non-negotiable product properties

### 2.1 Standalone operation

After installation, ordinary `texpdf` compilation must:

- work with **no system TeX installation**;
- work with **no Tectonic executable installed**;
- work with **no network connection**;
- not depend on the user's TeX environment, `TEXMF`, package manager, or shell PATH;
- include the LaTeX core, fonts, and supported packages needed by the advertised compatibility tier;
- behave consistently on supported Windows, macOS, and Linux systems.

The default build must not silently fall back to a system TeX installation or download missing TeX resources.

### 2.2 Native Stata integration

The public interface is an ado command backed by native compiled code. The Stata-facing layer should remain thin: syntax parsing, path normalization, option handling, user-facing error reporting, and returned results belong in ado; TeX compilation belongs in Rust/Tectonic.

### 2.3 Offline resources embedded with the engine

The preferred final design is to compile a curated Tectonic ZIP bundle directly into the native binary with `include_bytes!()` and open it in memory through `tectonic_bundles::zip::ZipBundle` over a `Cursor`. This avoids extraction of a permanent TeX tree and prevents compile-time network access by construction.

Temporary/generated files that Tectonic genuinely requires may use a Stata temporary directory. They must not amount to an installed TeX distribution and must be cleaned reliably.

### 2.4 Reproducible behavior

For the supported package set, output must not depend on what TeX packages or fonts happen to be installed on the user's machine. The project will pin:

- the Rust toolchain used for releases;
- Tectonic and its resolved dependency graph;
- the source TeX Live snapshot used to build the embedded bundle;
- the exact embedded bundle digest;
- bundled font versions;
- release build flags.

### 2.5 Safe failure behavior

Bad TeX input must produce a Stata error, not crash or corrupt Stata. Shell escape is disabled by default and is not planned for v1. The engine must never panic or unwind across the C ABI boundary.

Because a native plugin executes inside Stata's address space, direct in-process embedding will be subjected to an explicit containment/stress gate before release. If upstream engine behavior cannot be made acceptably crash-safe, the public API will remain unchanged but the engine may be isolated in a bundled helper process. **Standalone means no external installation; it does not automatically mean that process isolation is forbidden.** Whether a single physical plugin file is a hard requirement is an owner decision listed below.

## 3. Decisions already made

1. Repository/package/command name: `texpdf`.
2. Primary backend: Tectonic, not a fresh pdfTeX/Web2C port.
3. Standalone/offline compilation after installation is a core requirement.
4. Development happens directly on `main`, not a feature branch, unless the owner explicitly changes this policy.
5. Push small coherent checkpoints frequently so repository state is never far behind development state.
6. Use the licensed Stata/Rust CI runner described in `gptpro.md` and `STATA_CI_RUNNER.md` for exact-SHA Stata qualification.
7. Do not merge or resurrect the deliberate-failure tip of `codex/ci-bootstrap`; the CI infrastructure placed on `main` comes from the earlier exact-green bootstrap source commit `2ecbf988c3ee300829480da892509dbd1da4e383`.

## 4. Current repository / CI state

The licensed self-hosted runner is an Apple Silicon Mac Studio with Stata/MP 18 and Rust installed. Pushes to `main` trigger the repository's quick Stata/Rust workflow once the CI bootstrap is present on `main`.

The development discipline for every meaningful source checkpoint is:

1. make one focused change;
2. commit/push it directly to `main`;
3. record the **full source commit SHA**;
4. inspect `.ci/stata/results/<full-source-sha>.json` when published;
5. require exact `tested_sha`, `status=success`, `stata_status=success`, `rust_status=success`, and the intended profile;
6. inspect workflow job logs/artifacts on failure;
7. fix with another small source commit rather than amending history;
8. never confuse the receipt-publisher `[skip ci]` commit with the source commit it qualified.

The plan file itself should be updated as milestones are completed, architectural decisions change, or material risks are discovered.

## 5. Proposed repository architecture

Target layout:

```text
texpdf/
├── Cargo.toml
├── Cargo.lock
├── rust-toolchain.toml
├── PLAN.md
├── README.md
├── LICENSE
│
├── crates/
│   ├── texpdf-core/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── compile.rs
│   │       ├── bundle.rs
│   │       ├── diagnostics.rs
│   │       └── error.rs
│   │
│   └── texpdf-stata/
│       ├── Cargo.toml
│       ├── build.rs
│       ├── src/lib.rs
│       └── c/
│           └── stata_shim.c
│
├── vendor/
│   └── stata-plugin/
│       ├── stplugin.c
│       ├── stplugin.h
│       └── ORIGIN.md
│
├── bundle/
│   ├── README.md
│   ├── packages.toml
│   ├── licenses/
│   └── generated/          # generated bundle normally excluded unless release policy requires it
│
├── tools/
│   └── bundle-builder/
│
├── stata/
│   ├── texpdf.ado
│   ├── texpdf.sthlp
│   ├── texpdf.pkg
│   └── tests/
│       ├── smoke.do
│       ├── errors.do
│       ├── paths.do
│       └── corpus.do
│
├── tests/
│   ├── fixtures/
│   │   ├── minimal/
│   │   ├── math/
│   │   ├── tables/
│   │   ├── figures/
│   │   ├── bibliography/
│   │   └── failures/
│   └── corpus-manifest.toml
│
├── ci/
└── .github/workflows/
```

The exact layout can evolve, but the separation between pure Rust engine logic, Stata ABI glue, embedded resources, Stata ado code, and tests should remain.

## 6. Engine architecture

### 6.1 `texpdf-core`

`texpdf-core` is independent of Stata. It should be fully testable with ordinary Rust tests and expose a small API such as:

```rust
pub struct CompileRequest {
    pub input: PathBuf,
    pub output: PathBuf,
    pub root: PathBuf,
    pub keep_log: bool,
}

pub struct CompileResult {
    pub output: PathBuf,
    pub warnings: Vec<Diagnostic>,
    pub engine_version: String,
    pub bundle_digest: String,
}

pub fn compile(request: &CompileRequest) -> Result<CompileResult, TexPdfError>;
```

The public Rust API should not expose Tectonic types so that the backend can later be changed or supplemented without rewriting the Stata layer.

### 6.2 Tectonic baseline

Initial development baseline: **Tectonic 0.17.0**, with the exact dependency graph committed in `Cargo.lock`.

Prefer a build with network-related default features disabled if Tectonic's current crate graph permits it cleanly. The intended compile path is through the driver API (`ProcessingSessionBuilder`) with an explicitly supplied local/embedded bundle, not through a convenience API that may consult a default remote bundle.

Use restrictive Tectonic security settings and keep shell escape disabled.

### 6.3 Embedded bundle

Preferred implementation:

```rust
static BUNDLE_BYTES: &[u8] = include_bytes!(env!("TEXPDF_BUNDLE_PATH"));
```

then construct a seekable cursor and a Tectonic `ZipBundle` directly over those bytes.

This design has several advantages:

- one native binary can carry its own TeX support resources;
- no resource download at runtime;
- no global TeX tree to install or mutate;
- easy bundle digest/version reporting;
- easy testing that every supported package is actually in the shipped artifact.

If compiler/linker limitations make embedding a large ZIP impractical on a target, the fallback is a package-local read-only bundle file shipped next to the native plugin. It is still standalone from TeX, but a one-binary release remains the preferred target until proven impractical.

### 6.4 Input filesystem policy

Default compilation root should be the directory containing the primary `.tex` file. Relative `\input`, `\includegraphics`, bibliography files, and other project assets should work within that tree.

The first release should not provide arbitrary shell execution. We will test traversal, absolute paths, symlinks, and Unicode paths explicitly before fixing the exact filesystem policy.

### 6.5 Diagnostics

Implement a custom Tectonic status backend that captures structured errors/warnings rather than relying on uncontrolled stdout/stderr output.

The Rust core should return:

- a concise primary error;
- a bounded list of relevant TeX diagnostics;
- optional complete log text when requested;
- engine and bundle metadata.

Normal compilation chatter should be suppressed.

## 7. Stata plugin architecture

### 7.1 ABI boundary

Use Stata's current SPI 3.0 interface. Keep the ABI surface extremely small.

Preferred pattern:

```text
Stata ado
   ↓
Stata plugin C shim (`stata_call`)
   ↓ C ABI
Rust `texpdf-stata`
   ↓
`texpdf-core`
   ↓
Tectonic + embedded bundle
   ↓
PDF
```

A small C shim avoids reimplementing Stata-specific export/calling-convention details directly in Rust, particularly on Windows. Rust must catch all recoverable errors and must never unwind through `stata_call`.

### 7.2 Result transport

Avoid passing large TeX logs through Stata macros. The ado layer can create a temporary machine-readable result path and pass it to the native backend. The backend writes a small JSON or line-oriented result record containing status, diagnostics metadata, versions, and output path. The ado layer translates that into Stata output and `r()` results.

The result schema will be versioned from the start.

### 7.3 Initial command syntax

Minimum viable public syntax:

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
```

Likely early additions:

```stata
texpdf using filename.tex, saving(filename.pdf) replace log(filename.log)
texpdf, version
```

Potential v1 options should be added only when backed by a concrete use case. Do not replicate Tectonic's entire CLI as Stata options.

### 7.4 Returned results

Make `texpdf` an `rclass` command. Candidate results:

```text
r(pdf)             final output path
r(engine)          "tectonic"
r(engine_version)  pinned Tectonic version
r(bundle_version)  texpdf bundle version
r(bundle_digest)   bundle content digest
r(warnings)        warning count
```

Exact names will be fixed before the public API freeze.

## 8. Supported LaTeX bundle

The bundle should target academic/econometric documents rather than all of TeX Live.

### 8.1 Core target set

Initial inclusion target, subject to dependency closure and license audit:

**Core LaTeX / math**

- LaTeX base
- `amsmath`, `amssymb`, `amsfonts`, `amscls`
- `mathtools`
- standard LaTeX tools/graphics dependencies

**Tables**

- `booktabs`
- `array`
- `longtable`
- `tabularx`
- `multirow`
- `threeparttable`
- `threeparttablex` if dependency cost is modest
- `dcolumn`
- `siunitx`
- `adjustbox`

**Figures / layout**

- `graphicx`
- `xcolor`
- `geometry`
- `float`
- `placeins`
- `rotating`
- `pdflscape`
- `caption`
- `subcaption`

**Document formatting / references**

- `hyperref`
- `url`
- `setspace`
- `enumitem`
- `fancyhdr`
- `titlesec` if compatible and inexpensive
- `microtype`
- `natbib`
- standard BibTeX styles and common natbib styles

**Fonts**

At minimum, bundle all fonts required for deterministic default LaTeX output. Candidate extended academic fonts include Latin Modern and a small TeX Gyre selection. Additional font packages should be justified by actual corpus coverage rather than added indiscriminately.

### 8.2 Explicit initial exclusions

Unless the owner chooses a broader first release, defer:

- Beamer;
- TikZ/PGF;
- PSTricks;
- `biblatex` + Biber workflows;
- large language collections;
- broad font collections;
- minted/Pygments and other shell-dependent packages;
- arbitrary external helper programs.

These can be added later if real usage justifies the binary-size and maintenance cost.

### 8.3 Bundle construction

Create the resource bundle reproducibly from a pinned TeX Live source snapshot. Maintain a human-readable manifest describing:

- requested top-level packages;
- automatically included dependency closure;
- fonts;
- format/hyphenation resources;
- license metadata;
- source snapshot and checksums.

The builder must be deterministic enough that CI can verify the bundle digest from the same inputs.

### 8.4 Bundle tests

For every advertised top-level package, keep at least one minimal compiling fixture. A release cannot claim support for a package based only on its presence in the archive.

## 9. Licensing and provenance

Before public distribution:

1. choose the `texpdf` source license;
2. record the pinned Tectonic license/version;
3. audit direct and relevant native dependencies;
4. verify redistribution terms for the Stata plugin interface source files if vendored;
5. generate a license/provenance inventory for every TeX package and font in the embedded bundle;
6. ship required license notices in the repository and release package.

The implementation should avoid assuming that Tectonic's MIT license alone covers TeX Live support files; bundle contents retain their own licenses.

## 10. Platform targets

Primary release targets:

- macOS Apple Silicon (`aarch64-apple-darwin`);
- macOS Intel (`x86_64-apple-darwin`), ideally combined with Apple Silicon as one universal Mach-O Stata plugin;
- Windows 64-bit (`x86_64-pc-windows-msvc`);
- Linux 64-bit (`x86_64-unknown-linux-gnu`).

Possible later target:

- Linux ARM64 if Stata and demand justify it.

A platform is not considered supported until the final native artifact has been loaded by Stata on that platform and has compiled the release smoke corpus offline.

## 11. Development and CI strategy

### 11.1 Main-branch workflow

Development is intentionally direct-to-`main`. Therefore commits must remain small and reversible.

Rules:

- never accumulate a large unpublished working set;
- push after each coherent step;
- no history rewriting or force pushing;
- never intentionally commit a failing checkpoint to `main` merely to test CI;
- use unit tests before pushing when possible;
- verify the exact-SHA CI receipt after meaningful source changes;
- if CI is unavailable, state that explicitly rather than treating missing evidence as a pass.

### 11.2 Fast checks on every source push

Once the Rust workspace exists, the existing Rust quick lane should automatically become repository checks. Required baseline:

- `cargo fmt --check`;
- `cargo clippy --workspace --all-targets -- -D warnings` (or the closest equivalent supported by the existing runner script);
- `cargo test --workspace`;
- basic Stata ado/plugin smoke tests once the plugin exists.

### 11.3 Deeper CI profiles

Extend the current Stata profiles as the project matures. Proposed eventual profiles:

- `version`: runner/tool inventory only;
- `smoke`: minimal ado/plugin load + one tiny document;
- `quick`: Rust tests + several Stata compile/error/path tests;
- `corpus`: larger academic compatibility corpus;
- `stress`: malformed inputs and repeated compile loop;
- `release`: full offline package qualification.

Do not make long release tests part of every tiny push.

### 11.4 Cross-platform Rust/native CI

The Mac self-hosted runner is authoritative for licensed Stata-on-Mac testing, but it cannot by itself certify Windows and Linux Stata integration.

During development, pure Rust core tests should be run on all build targets that are economically practical. Before release, obtain actual Stata runtime qualification on Windows and Linux as well as macOS. The exact infrastructure can be decided later (Windows VM/VPS/self-hosted runner and Linux machine/cluster).

## 12. Test strategy

### 12.1 Rust unit tests

Test independently of Stata:

- embedded bundle opens and digest matches;
- minimal article compiles;
- equations compile;
- tables compile;
- figures/images compile;
- bibliography flow compiles if included;
- missing package fails cleanly;
- syntax error fails cleanly;
- missing input/output permissions fail cleanly;
- no network provider is required;
- deterministic fixture output where byte-level determinism is realistic;
- diagnostics are bounded and valid UTF-8;
- repeated compilation does not leak temp files.

### 12.2 Stata tests

Use real licensed Stata through the existing CI workflow for:

- `which texpdf` / plugin load;
- basic `texpdf using ...` success;
- default output naming;
- `saving()`;
- `replace` behavior;
- paths containing spaces;
- non-ASCII/Unicode paths;
- missing source file;
- invalid TeX;
- existing output without `replace`;
- relative included files and images;
- return values in `r()`;
- repeated calls in one Stata process;
- running from a directory unrelated to the package install location.

### 12.3 Compatibility corpus

Build a curated corpus of realistic academic source files rather than relying only on toy examples. Keep sources small and redistributable. Cover:

- equations and theorem-like structures;
- regression tables using common packages;
- EPS/PDF/PNG/JPEG figure cases that Tectonic supports;
- footnotes, references, hyperlinks;
- cross-references requiring multiple passes;
- BibTeX/natbib if included;
- common economics article preambles.

Record both expected-success and expected-unsupported cases.

### 12.4 Differential tests

Where useful, compile the same fixtures with Tectonic CLI and/or the Mac's TeX Live installation as a diagnostic reference. These are not the production dependency and exact PDF byte equality is not required; compare successful compilation, extracted text/page count, and expected visible structure when practical.

### 12.5 Stress / safety tests

Before accepting in-process embedding as release-safe:

- thousands of repeated compile calls in one Stata process;
- malformed TeX corpus;
- deliberately missing/corrupt assets;
- extreme recursion / TeX capacity errors;
- invalid fonts and images where feasible;
- cancellation/interruption behavior;
- memory growth monitoring;
- Rust panic injection around every FFI boundary;
- verify no unwind crosses C;
- verify Stata remains usable after ordinary compilation failures.

If this gate reveals credible process-fatal failure modes that cannot be contained, move Tectonic execution into a bundled helper process while preserving the ado API.

## 13. Performance and size targets

This is not primarily a numerical-performance project. Optimize for startup latency, predictable memory use, and package size without sacrificing reliability.

Measure continuously:

- native binary size by target;
- embedded bundle size;
- total installed size;
- cold first compile time;
- warm repeated compile time;
- peak resident memory;
- repeated-call memory growth.

Initial planning target for a curated academic bundle: approximately **20–50 MB per platform artifact**, but measurement rather than a hard arbitrary cap governs decisions. If a modest increase eliminates common missing-package failures, prefer usability.

Avoid loading/decompressing the entire TeX resource bundle into RAM eagerly if the Tectonic ZIP bundle can serve files on demand.

## 14. Milestones

### M0 — CI and design bootstrap

- [x] Repository named `texpdf`.
- [x] `gptpro.md` present.
- [x] Licensed Stata/Rust CI bootstrap exists and has an exact-green source checkpoint.
- [x] Put the green CI bootstrap on `main` without the deliberate-failure tip.
- [x] Create detailed `PLAN.md`.
- [ ] Resolve owner decisions in Section 17.
- [ ] Update `gptpro.md` so future sessions follow the main-only development policy.

Exit: architecture and policy decisions are explicit; `main` has working CI.

### M1 — Minimal Rust/Tectonic proof of concept

- [ ] Create Rust workspace and pin toolchain/dependencies.
- [ ] Add `texpdf-core`.
- [ ] Compile a trivial article from Rust using Tectonic 0.17.0.
- [ ] Use an explicit local test bundle; do not rely on system TeX.
- [ ] Capture diagnostics in a structured backend.
- [ ] Add unit tests for success and bad TeX.

Exit: `cargo test` compiles a PDF with no external TeX executable.

### M2 — True embedded/offline bundle proof

- [ ] Build a tiny ZIP-format Tectonic test bundle.
- [ ] Embed it with `include_bytes!`.
- [ ] Open it in-memory via `ZipBundle`/`Cursor`.
- [ ] Compile with network functionality disabled/unavailable.
- [ ] Prove compilation works after hiding/removing reliance on the Mac's installed TeX tree.
- [ ] Record bundle digest in test output.

Exit: a Rust test produces PDF using only the executable/test artifact plus user input.

### M3 — Stata native bridge

- [ ] Vendor or reproducibly obtain Stata SPI 3.0 files after license/provenance review.
- [ ] Implement tiny C shim.
- [ ] Build Rust `cdylib`/plugin on Mac arm64.
- [ ] Implement a private Stata plugin command.
- [ ] Run a licensed Stata smoke test calling Rust.
- [ ] Add exact error/result transport.

Exit: Stata invokes the native Rust backend successfully through CI.

### M4 — First end-to-end `texpdf` command

- [ ] Implement `texpdf.ado` syntax.
- [ ] Compile `using` file to default `.pdf`.
- [ ] Add `saving()` and `replace`.
- [ ] Return engine/bundle metadata.
- [ ] Handle spaces and Unicode paths.
- [ ] Add concise user-facing TeX errors.
- [ ] Add `.sthlp` documentation.

Exit: `texpdf using example.tex` works in Stata/MP 18 on the self-hosted Mac with no system TeX dependency.

### M5 — Curated academic bundle

- [ ] Build dependency-aware bundle generator.
- [ ] Freeze top-level v1 package list.
- [ ] Add fonts.
- [ ] Add package-by-package fixtures.
- [ ] Generate license/provenance inventory.
- [ ] Measure artifact size.
- [ ] Ensure no runtime network path.

Exit: common academic/econometric documents compile offline from the shipped resource set.

### M6 — Robustness / containment gate

- [ ] Run malformed-input corpus.
- [ ] Repeated compile stress test in one Stata process.
- [ ] Memory/leak checks.
- [ ] Panic/FFI tests.
- [ ] Decide definitively between direct in-process engine and helper-process isolation.

Exit: architecture is considered safe enough for broad Stata use.

### M7 — Cross-platform builds

- [ ] macOS arm64 release artifact.
- [ ] macOS x86_64 release artifact.
- [ ] Universal macOS plugin if feasible.
- [ ] Windows x86_64 build.
- [ ] Linux x86_64 build.
- [ ] Verify each artifact links only to acceptable system/runtime libraries.
- [ ] Test actual Stata loading on each supported OS.

Exit: same ado-level API passes smoke corpus on Windows/macOS/Linux.

### M8 — Compatibility corpus and API freeze

- [ ] Expand real-world corpus.
- [ ] Resolve common missing packages.
- [ ] Freeze syntax and `r()` results.
- [ ] Document intentional Tectonic-vs-pdfLaTeX differences.
- [ ] Document unsupported packages/workflows.

Exit: v1 public interface and compatibility promise are stable.

### M9 — Packaging and release qualification

- [ ] Choose final install/distribution mechanism.
- [ ] Build deterministic release artifacts.
- [ ] Include licenses/notices.
- [ ] Verify install on clean Windows/macOS/Linux machines with no TeX distribution.
- [ ] Full `release` CI/profile.
- [ ] Create checksum manifest and release notes.

Exit: release candidate can be installed on a clean Stata machine and compile the advertised corpus completely offline.

## 15. Definition of v1 success

Version 1.0 is ready when a clean supported machine with Stata but no TeX distribution can:

```stata
texpdf using paper.tex, saving(paper.pdf)
```

and successfully compile a documented set of ordinary academic LaTeX sources using only files shipped with `texpdf` plus the user's source/assets.

Additionally:

- Windows, macOS, and Linux are genuinely tested in Stata;
- no network is needed at compile time;
- common errors return control to Stata cleanly;
- bundle and engine versions are inspectable;
- licensing/provenance is complete;
- the repository's release test corpus is green;
- package size and runtime are measured and documented.

## 16. Explicit non-goals for the first release

Unless later promoted by an owner decision:

- perfectly reproducing `pdflatex` byte-for-byte;
- supporting every TeX Live package;
- replacing TeX Live as a general-purpose distribution;
- shell escape;
- arbitrary external tools;
- Biber;
- a high-level Stata report/table authoring DSL;
- Beamer/TikZ as required v1 features;
- remote package fetching during normal compilation.

The first release should be an excellent **compiler command**, not an entire document-generation framework.

## 17. Owner decisions needed before they become blocking

The following decisions materially affect architecture or release scope. Recommended defaults are included so development can proceed to early proof-of-concept work without waiting.

### D1. Is one physical native binary per platform a hard requirement?

**Recommended:** standalone/offline package is mandatory, but permit a bundled helper executable later if the in-process containment gate shows meaningful crash risk. Prefer an embedded single plugin in the first prototype.

If the answer is "single plugin file no matter what," the containment architecture and distribution work become more constrained.

### D2. Minimum Stata version

**Recommended:** target SPI 3.0 / Stata **14.1+** at the ABI level, while initially certifying actual behavior on Stata 18 because that is the licensed CI installation. Avoid ado features that unnecessarily raise the minimum version.

Alternative: declare Stata 16+ or 18+ to reduce compatibility obligations.

### D3. First-release bundle breadth

**Recommended:** "academic core" around roughly 20–50 MB per platform: math, tables, figures, layout, hyperlinks, natbib/BibTeX, and a small deterministic font set; no Beamer/TikZ/Biber initially.

Alternative: accept a larger 50–100+ MB artifact to cover a substantially broader TeX Live subset from day one.

### D4. Bibliographies in v1

**Recommended:** support Tectonic's built-in **BibTeX + natbib** workflow in v1; do not promise Biber/biblatex.

### D5. Public source license

**Recommended:** MIT for the `texpdf` source code, subject to a short dependency/Stata-SPI redistribution audit. TeX bundle files retain their upstream licenses and notices.

### D6. Distribution priority

**Recommended:** design release artifacts first around GitHub Releases / Stata `net install` compatibility, then assess SSC size/policy constraints once real artifact sizes are known. Do not let SSC constraints distort the engine architecture before measurement.

### D7. Scope of the Stata command

**Recommended:** v1 only compiles complete `.tex` documents. Higher-level table/report/document-generation commands are a later layer and should not delay a robust compiler.

## 18. Research / verification notes behind the design

As of 2026-08-24:

- Tectonic 0.17.0 is the current release baseline chosen for the prototype.
- Tectonic's Rust crate is explicitly designed to be embedded and exposes a high-level driver API.
- Its `ProcessingSessionBuilder` accepts an explicit bundle and defaults to restrictive security settings.
- `tectonic_bundles` provides a `ZipBundle` over a generic `Read + Seek`, which makes an in-memory embedded ZIP bundle technically natural.
- Stata's current plugin interface is SPI 3.0 for Stata 14.1 and later; native plugins are platform-specific, and a universal macOS plugin can combine Intel and Apple Silicon slices.

These facts should be rechecked when release engineering begins; they are implementation baselines, not promises that upstream APIs will remain unchanged.
