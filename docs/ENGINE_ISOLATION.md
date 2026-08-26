# Embedded helper-process architecture

## Decision

`texpdf` will continue to distribute one native Stata plugin per platform, but
Tectonic compilation will execute in a same-architecture helper process embedded
inside that plugin.

At build time:

1. `texpdf-helper` is compiled as a standalone executable containing
   `texpdf-core`, Tectonic, the native engine libraries, and the curated TeX ZIP;
2. the helper bytes are incorporated into `texpdf.plugin`;
3. the release package ships only the plugin, ado/help files, and notices.

At runtime:

1. the plugin hashes the embedded helper bytes;
2. it verifies or atomically extracts them into a private, digest-addressed
   cache with executable-only owner permissions where supported;
3. it invokes the helper with a versioned file-based request/result protocol;
4. the helper exits after each compile, returning all Tectonic/native memory to
   the operating system;
5. the plugin remains loaded in Stata but contains no in-process Tectonic
   engine state.

This remains a one-plugin installation. The extracted helper is a verified
runtime cache derived exclusively from the installed plugin, not a second
installed dependency or a network download.

## Evidence requiring the change

The original in-process implementation was functionally correct but failed the
release memory gate.

Licensed Stata/MP 18, 1,000 repeated calls:

```text
warm median Stata RSS       389,566 KiB
late median Stata RSS     1,210,965 KiB
post-warm-up growth         821,399 KiB
ratio                           3.11
```

A Rust-only process using the same `texpdf-core`, bundle, Tectonic engine, and
native dependencies reproduced the result without Stata or the SPI bridge:

```text
warm median process RSS     363,520 KiB
late median process RSS   1,186,104 KiB
post-warm-up growth         822,584 KiB
ratio                           3.26
```

The Rust-only probe completed all 1,000 compilations successfully. macOS
`malloc_zone_pressure_relief(NULL, 0)` did not materially change the slope.
The evidence therefore implicates repeated in-process Tectonic/native engine
invocations rather than Stata, result transport, or the Rust SPI wrapper.

Source-bound evidence is recorded in:

- `release/memory-stress-macos-arm64.json`;
- `release/latest-memory-stress-macos-arm64.json` for the latest attempt;
- `release/memory-probe-rust-macos-arm64.json`.

## Safety properties

The helper design must enforce:

- SHA-256 verification of cached helper bytes before execution;
- atomic extraction and replacement;
- owner-only executable permissions on Unix;
- no shell command construction or shell interpolation;
- direct argument-array process invocation;
- a bounded execution timeout and forced termination on timeout;
- a versioned result schema with bounded diagnostics;
- no runtime network provider or system TeX dependency;
- helper architecture matching the containing plugin slice;
- cleanup/recovery from interrupted extraction or helper crashes.

The plugin must never accept an arbitrary helper path in normal operation.
A test-only cache-location override may change where verified embedded bytes are
written, but not which bytes execute.

## Platform implications

A macOS universal plugin contains a different embedded helper in each Mach-O
slice: the ARM64 plugin slice embeds the ARM64 helper and the x86-64 slice
embeds the Intel helper. Windows and Linux plugins likewise embed native helper
executables for their own target.

Actual licensed-Stata runtime qualification remains required for every target.

## Qualification gate

The helper architecture is accepted for v1 only after:

- all existing Rust and licensed-Stata functional tests pass;
- local `net install` still installs one plugin file;
- 1,000 repeated Stata calls pass with bounded Stata RSS growth;
- helper extraction, digest verification, timeout, crash, and malformed-result
  tests pass;
- offline/system-TeX-hidden qualification remains green;
- exact plugin/package sizes and hashes are republished.
