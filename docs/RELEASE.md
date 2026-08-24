# Release procedure

This procedure is intentionally fail-closed. Do not create a public binary
release by bypassing a failed check or by treating a build-only target as a
supported Stata runtime.

## 1. Freeze the source checkpoint

- Commit all source directly to `main`.
- Require a committed `Cargo.lock` and record its SHA-256.
- Record the full source SHA.
- Require `.ci/stata/results/<source-sha>.json` with exact `tested_sha`, intended
  profile, overall success, Rust success, and licensed-Stata success.
- Do not use a receipt-publisher or generated-summary commit as the tested
  source SHA.
- Ensure `release/targets.json` identifies that exact source for every runtime-
  qualified target.

## 2. Complete the third-party license audit

The durable workflow `.github/workflows/license-audit.yml` produces a
source-bound audit under `licenses/generated/`. Equivalent local inputs are:

```sh
python3 tools/generate_license_inventory.py \
  --manifest bundle/curated-manifest.json \
  --tlpdb path/to/pinned-texlive-2022/texlive.tlpdb \
  --overrides bundle/license-overrides.toml \
  --output licenses/generated/tex-resources.json \
  --markdown licenses/generated/tex-resources.md \
  --strict

python3 tools/generate_cargo_license_inventory.py \
  --output licenses/generated/cargo.json \
  --markdown licenses/generated/cargo.md \
  --strict

python3 tools/generate_dependency_inventory.py \
  --json licenses/generated/dependencies.json \
  --markdown licenses/generated/dependencies.md \
  --require-declared
```

Then collect all required Rust and native-library texts with
`tools/collect_dependency_license_texts.py`.

Public packaging requires `licenses/generated/STATUS.json` to report:

- `release_license_complete: true`;
- zero ambiguous or unmapped embedded resources;
- zero resources lacking license metadata;
- zero undeclared Rust dependency licenses;
- zero missing Rust or native notice files;
- successful return codes for every audit phase.

Review ambiguous or standalone resources manually. Reviewed overrides must cite
real evidence. Never edit completion fields merely to pass the gate.

## 3. Build and qualify each target

Required v1 targets:

```text
aarch64-apple-darwin
x86_64-apple-darwin
x86_64-pc-windows-msvc
x86_64-unknown-linux-gnu
```

For each target:

- prepare the exact locked curated resource ZIP;
- build the release plugin with the documented native-linking policy;
- verify `pginit` and `stata_call` exports;
- inspect dynamic dependencies;
- record plugin bytes, SHA-256, target triple, and build source;
- assemble the deterministic Stata package;
- run a local `net install` from that package tree;
- compile the release corpus offline;
- load and execute the plugin in an actual licensed Stata process;
- record the exact Stata version, source SHA, receipt, and qualification method
  in `release/targets.json`.

A hosted Rust build, cross-compile, or universal-binary slice is useful evidence
but is not by itself Stata runtime qualification.

## 4. Run safety and regression gates

At minimum:

- Rust formatting, strict Clippy, unit and integration tests;
- malformed-input and failed-replacement preservation tests;
- Unicode, spaces, relative-input, PDF, and PNG tests;
- BibTeX/`natbib` and the academic package corpus;
- clean local `net install` test;
- 1,000 or more in-process compile calls with periodic injected errors;
- RSS/peak-memory sampling and review;
- shell-escape denial;
- offline/no-system-TeX verification;
- exact embedded-ZIP integrity verification.

The durable macOS memory result is
`release/memory-stress-macos-arm64.json`. A passing growth gate is required but
cannot prove that no native process-fatal path exists; the remaining boundary
must be documented in `SECURITY.md`.

## 5. Assemble public package assets

Development packages may be produced without complete third-party evidence,
but they are explicitly non-release artifacts. Public packages must be built
with:

```sh
python3 tools/package_release.py \
  --plugin path/to/_texpdf_plugin.plugin \
  --bundle-info path/to/bundle-info.json \
  --output-dir dist/texpdf-TARGET \
  --zip dist/texpdf-TARGET.zip \
  --manifest dist/texpdf-TARGET.manifest.json \
  --target TARGET \
  --public-release
```

`--public-release` refuses to build unless the license audit is complete. It
adds the generated inventories and collected texts under `LICENSES/` and lists
them in the release-specific `texpdf.pkg`.

Each target package must contain:

- `texpdf.ado` and `texpdf.sthlp`;
- the target `_texpdf_plugin.plugin`;
- `texpdf.pkg` and `stata.toc`;
- the project MIT License;
- the third-party notice index;
- complete generated inventories and collected license texts;
- `BUILD_INFO.json` and a SHA-256 manifest.

Build ZIP archives deterministically and verify that a second build from the
same source reproduces the resource ZIP and, where the platform toolchain
permits, the plugin/package digest.

## 6. Enforce the release gate

Generate a human-readable and machine-readable report:

```sh
python3 tools/check_release_readiness.py
```

For an actual release, require the strict exit code:

```sh
python3 tools/check_release_readiness.py --require-public-release-ready
```

The durable report is published as `release/READINESS.json` and
`release/READINESS.md`. Every release-blocking check must pass.

## 7. Create and verify the GitHub Release

- Tag the exact qualified source as `v0.1.0`.
- Create a draft release first.
- Upload every target package, manifests, third-party notice bundle, and one
  combined checksum file.
- Verify the documented `net install` command from draft asset URLs on clean
  target machines.
- Compile the release corpus with system TeX hidden and outbound bundle/network
  access unavailable.
- Publish only after release notes state the tested Stata versions, supported
  package tier, exclusions, and Tectonic/pdfLaTeX compatibility boundary.

## 8. Post-release verification

- Re-run public `net install` on every supported platform.
- Compile the release corpus offline.
- Preserve receipts, target manifests, and checksums under the immutable tag.
- Do not move or retag a released version; publish a new patch version for any
  binary or resource-bundle change.
