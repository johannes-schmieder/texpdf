# texpdf plan to v1

Updated: 2026-08-24  
Development branch: **main**  
Release target: **0.1.0**

## 1. Product definition

`texpdf` is a compiler-only Stata package:

```stata
texpdf using filename.tex [, saving(filename.pdf) replace]
texpdf, version
```

Version 1 ships one native plugin per supported platform. Each plugin embeds
Tectonic and the curated academic TeX resource ZIP. Runtime use is offline and
does not depend on a system TeX installation or external helper executable.

Fixed decisions:

- repository, package, and command name: `texpdf`;
- engine: Tectonic 0.17.0;
- one physical plugin file per platform;
- Stata ABI floor: SPI 3.0 / Stata 14.1-compatible ado syntax;
- academic/econometric compatibility tier;
- BibTeX + `natbib` in v1; no Biber;
- project-owned source license: MIT;
- GitHub Releases and `net install` distribution;
- development directly on `main`, using small non-amended checkpoints.

## 2. Authoritative evidence

Project state is determined in this order:

1. `.ci/stata/results/<source-sha>.json` for exact Rust/Stata qualification;
2. `release/targets.json` for platform support status;
3. `docs/generated/CURRENT_ARTIFACT.md` for exact artifact measurements;
4. `STATUS.md` for the live human-readable summary;
5. this plan for remaining work.

A branch head, successful ancestor, build-only artifact, or receipt-publisher
commit is not a substitute for an exact green source receipt.

Current exact green source:
`90101fa26ef06cea0ffa7e241b4230a1d0fe62a9`.

Current exact macOS ARM64 artifact baseline:
`a42f29fbeefd41811475d47e066e1ffea5290bfd`.

## 3. Completed foundations

### M0 — Product and CI bootstrap — complete

- [x] Product scope and owner decisions fixed.
- [x] Main-only development and exact-SHA receipt discipline established.
- [x] Licensed Stata/MP 18 self-hosted runner qualified.
- [x] Rust formatting, strict Clippy, tests, plugin build, Stata tests, artifact
      publication, and receipt publication wired together.

### M1 — Rust/Tectonic core — complete on macOS ARM64

- [x] Pinned Rust workspace and `Cargo.lock`.
- [x] Project-owned request/result/error API.
- [x] Structured bounded diagnostics.
- [x] Tectonic driver integration with shell escape disabled.
- [x] Success, malformed-input, missing-package, PDF/PNG figure, and recovery
      tests.

### M2 — Embedded offline bundle — complete

- [x] Deterministic curated bundle construction.
- [x] Bundle embedded with `include_bytes!` and opened in memory.
- [x] No runtime remote-bundle provider.
- [x] Curated academic bundle reduced to about 6.38 MiB.
- [x] Exact bundle hash, content digest, and file count published.

### M3 — Stata bridge and command — complete on macOS ARM64

- [x] SPI 3.0 native bridge with `pginit` and `stata_call` exports.
- [x] Panic containment at the Rust ABI boundary.
- [x] Versioned result-file transport.
- [x] `texpdf.ado`, `saving()`, `replace`, `texpdf, version`, help, package,
      and `stata.toc` files.
- [x] Spaces, Unicode paths, relative inputs, and concise recoverable errors.

### M4 — Academic compatibility tier — complete for the declared corpus

- [x] Mathematics, table, layout, hyperlink, font, figure, and bibliography
      fixtures.
- [x] BibTeX/`natbib` processing inside Tectonic.
- [x] Package corpus manifest and explicit unsupported-package behavior.
- [x] Bundle size within the desired product range.

### M5 — macOS ARM64 qualification — complete

- [x] Actual licensed Stata/MP 18 runtime qualification.
- [x] Deterministic package assembly and local `net install`.
- [x] 100-call in-process stress with injected TeX errors.
- [x] Standalone binary dependency-policy inspection.
- [x] Exact plugin/package sizes and SHA-256 values recorded.

### P0 — Restore current source to green — complete

- [x] Apply `cargo fmt` output to the three newly added Rust test files.
- [x] Run exact-SHA Rust engine checks and licensed Stata `quick` profile.
- [x] Require `status=success`, `rust_status=success`, and
      `stata_status=success` for source
      `90101fa26ef06cea0ffa7e241b4230a1d0fe62a9`.
- [x] Update the live status to distinguish current source evidence from the
      earlier exact artifact record.

## 4. Remaining work in execution order

### P1 — License-complete redistribution inventory — highest release blocker

- [ ] Generate the locked Rust dependency inventory and collect required texts.
- [ ] Generate the native vcpkg dependency inventory and collect notices.
- [ ] Map every embedded TeX/font resource to a TeX Live package or an
      explicitly reviewed standalone license.
- [ ] Resolve every ambiguous/unmapped resource and package lacking license
      metadata; reviewed overrides must record evidence.
- [ ] Assemble the final release notice tree and bind it to the exact bundle and
      plugin hashes.
- [ ] Make `check_release_readiness.py` fail closed on any missing mapping,
      notice, checksum, or unsupported target claim.

Exit: the release audit reports `license_complete=true` and all required texts
are included in the installation/release archive.

### P2 — In-process safety and durability gate

- [ ] Re-run and preserve the 1,000-call licensed-Stata stress result.
- [ ] Record process RSS/peak-memory behavior and check for monotone growth.
- [ ] Exercise malformed/corrupt inputs, TeX capacity failures, invalid images,
      repeated errors, and post-error recovery.
- [ ] Verify atomic output replacement and per-process format-cache isolation.
- [ ] Review any upstream abort/signal paths that Rust panic containment cannot
      catch.

Exit: no material leak or Stata-process instability is observed, and known
in-process limitations are documented in `SECURITY.md`.

### P3 — Cross-platform native builds and runtime qualification

For each target, use the same curated bundle and public API:

- [x] `aarch64-apple-darwin`: build and Stata runtime qualified.
- [ ] `x86_64-apple-darwin`: Intel slice builds; fix universal packaging and
      obtain Intel Stata runtime qualification.
- [ ] `x86_64-pc-windows-msvc`: native MSVC build and Windows Stata runtime.
- [ ] `x86_64-unknown-linux-gnu`: native GNU build and Linux Stata runtime.

Every target must have:

- plugin exports and binary-policy checks;
- an offline compile corpus;
- local `net install` from the target package tree;
- actual licensed Stata version/load/compile/error/recovery tests;
- exact target SHA, plugin SHA-256, size, and runtime receipt recorded in
  `release/targets.json`.

Build-only success is not runtime support.

### P4 — Public 0.1.0 release

- [ ] Freeze command syntax, returned results, and error codes.
- [ ] Complete user installation, compatibility, security, licensing, and
      troubleshooting documentation.
- [ ] Run clean-machine tests with system TeX hidden and outbound network
      unavailable.
- [ ] Rebuild deterministic package trees and checksum manifests for every
      supported target.
- [ ] Run the fail-closed release audit against the exact tag.
- [ ] Tag `v0.1.0`, publish GitHub Release assets, and verify documented
      `net install` commands from the public release location.
- [ ] Update `CHANGELOG.md` from “unreleased” to the release date.

Exit: users can install and compile on every advertised platform without any
external TeX installation or network access.

## 5. CI discipline

For every source checkpoint:

1. push the smallest coherent change to `main`;
2. record the full source SHA;
3. read `.ci/stata/results/<source-sha>.json`;
4. require the intended profile, exact SHA, overall success, Rust success, and
   Stata success;
5. inspect logs/artifacts on failure and fix with another commit;
6. never rewrite history or describe a missing receipt as a pass.

Documentation-only and generated-summary changes may be excluded from expensive
engine CI, but source, build, package, bundle, license-policy, and test changes
must receive the appropriate exact-SHA gate.

## 6. v1 definition of done

A clean supported machine containing only Stata can install `texpdf` from the
public GitHub Release and run:

```stata
texpdf using paper.tex, saving(paper.pdf)
```

The one installed plugin compiles the documented academic tier completely
offline, preserves existing output on failure, exposes engine/bundle provenance,
and has a green actual-Stata runtime receipt for that operating system and
architecture.
