# Release procedure

This procedure is intentionally fail-closed. Do not create a public binary
release by bypassing a failed check.

## 1. Freeze the source checkpoint

- Commit all source directly to `main`.
- Record the full source SHA.
- Require its immutable exact-SHA CI receipt.
- Require overall, Rust, and licensed Stata success.
- Do not use a receipt-publisher commit as the tested source SHA.

## 2. Generate dependency and resource inventories

```sh
python3 tools/generate_dependency_inventory.py --require-declared
python3 tools/generate_tex_resource_inventory.py \
  --tlpdb path/to/pinned-texlive-2022/texlive.tlpdb
```

Review every ambiguous or unresolved resource manually. Copy all required
license texts and notices into the release notice directory. Set
`license_complete: true` only through the generator after all mappings and
metadata are complete; never edit that value merely to pass the gate.

## 3. Build each target from the frozen source

Required targets:

```text
aarch64-apple-darwin
x86_64-apple-darwin
x86_64-pc-windows-msvc
x86_64-unknown-linux-gnu
```

For each target:

- prepare the same locked curated resource ZIP;
- build the release plugin with static native dependencies where permitted;
- record plugin bytes, SHA-256, linked-library inspection, and target triple;
- assemble the deterministic Stata installation package;
- run the release corpus offline;
- load and execute the plugin in an actual Stata process on that target;
- record the exact Stata version and source SHA in `release/targets.json`.

A hosted Rust build is useful evidence but is not Stata runtime qualification.

## 4. Run safety and regression gates

At minimum:

- Rust format, strict Clippy, unit and integration tests;
- malformed-input and failed-replacement preservation tests;
- Unicode, spaces, and relative-asset tests;
- BibTeX/natbib fixture;
- clean local `net install` test;
- high-iteration in-process stress run with periodic errors;
- memory-growth review;
- offline/no-system-TeX verification.

## 5. Assemble release assets

Each target package must include:

- `texpdf.ado`;
- `texpdf.sthlp`;
- the target `_texpdf_plugin.plugin`;
- `texpdf.pkg` and `stata.toc`;
- project MIT License;
- complete third-party notices and generated inventories;
- build/qualification metadata;
- SHA-256 manifest.

Build ZIP archives deterministically and verify a second build from the same
source produces the same resource ZIP and, where toolchains permit, the same
plugin/package digest.

## 6. Enforce the release gate

```sh
python3 tools/check_release_readiness.py
```

The command must exit successfully without `--allow-unqualified-targets`.

## 7. Create the GitHub Release

- Tag the exact qualified source as `v0.1.0`.
- Create a draft release first.
- Upload every target package and one combined checksum file.
- Verify installation from the draft asset URLs on clean target machines.
- Publish only after the release notes state the tested Stata versions,
  supported package tier, exclusions, and Tectonic/pdfLaTeX compatibility
  boundary.

## 8. Post-release verification

- Re-run `net install` from the public URL on every supported platform.
- Compile the release corpus offline.
- Preserve receipts and checksums under the release tag.
- Do not move or retag a released version; publish a new patch version for any
  binary change.
