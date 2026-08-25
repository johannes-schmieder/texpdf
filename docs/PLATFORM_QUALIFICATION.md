# Target-platform Stata qualification

A successful Rust build is not sufficient to mark a platform supported. The
exact plugin binary must load and run the release corpus in Stata on that
platform.

## Inputs

For each target, preserve:

- exact Git source SHA;
- `_texpdf_plugin.plugin` bytes and SHA-256;
- embedded bundle SHA-256;
- target triple and binary-policy report;
- Stata executable path, version, and edition;
- package installation tree;
- expected profile and PASS markers.

Do not rebuild the plugin between checksum recording and Stata testing.

## macOS Apple Silicon

This is the connected qualification target. The self-hosted workflow builds the
real embedded engine before running the `quick` profile under Stata/MP 18. The
comprehensive checkpoint includes a real PDF compile, local `net install`,
Unicode/relative paths, recoverable errors, and 100 installed-plugin calls.

## macOS Intel

1. Build the x86-64 slice with deployment target 11.0.
2. Inspect exports, load commands, minimum OS, and dynamic dependencies.
3. Assemble the platform installation tree.
4. Transfer the exact artifact without modification to an Intel Mac with
   licensed 64-bit Stata.
5. Run the `quick` and high-iteration `stress` profiles.
6. Record the plugin digest and Stata result in `release/targets.json`.

A universal plugin tested only on Apple Silicon qualifies its ARM slice, not its
Intel slice.

## Linux x86-64

The private RC.2 artifact is built and qualified on BU SCC's RHEL 8/glibc 2.28
environment, with TeX/native libraries statically linked. Inspect the ELF for
RPATH/RUNPATH, accidental build paths, dynamic TeX libraries, exports, and
required GLIBC symbol versions; no required symbol may exceed 2.28.

On the licensed Linux Stata host or cluster node:

```sh
ci/scc/submit_linux_qualification.sh /projectnb/welfgr/texpdf/runs/RUN_ID
```

The required profiles are Stata/MP 18 quick, Stata/MP 18 stress1000, and
Stata/MP 19 quick. The runner stages the exact built package and binds its
plugin, helper, bundle, and ZIP hashes into every receipt. Require successful
SGE accounting, application markers, and outputs as documented in
`SCC_LINUX_QUALIFICATION.md`. Use only synthetic fixtures and collect only
sanitized evidence.

## Windows x86-64

Use the MSVC target with a static CRT and statically linked Tectonic native
libraries. Verify `pginit` and `stata_call` with `dumpbin /exports`, inspect DLL
dependencies, and ensure no vcpkg build path is embedded.

Run 64-bit licensed Stata in batch mode from PowerShell or `cmd.exe`, using an
isolated ado path and temporary directory. The Windows harness must distinguish
Stata-language errors from process exit status just like the macOS harness.
It must run the `quick` and `stress` profiles and preserve an exact binary
SHA-256 receipt.

## Promotion rule

A target record changes to `stata_runtime_qualified: true` only when:

- the recorded plugin SHA-256 matches the tested bytes;
- binary-policy inspection passes;
- Stata loads the plugin;
- the release corpus compiles offline;
- expected errors leave Stata usable;
- the target PASS markers and exact source SHA are present;
- the evidence is committed or attached to the immutable release record.

Manual statements such as “it worked on Windows” are not qualification records.
