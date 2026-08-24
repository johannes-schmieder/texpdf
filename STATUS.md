# texpdf development status

Updated: 2026-08-24

## Current phase

M0 is complete and implementation has started.

Completed:

- repository/package/command name fixed as `texpdf`;
- Tectonic selected as the embedded engine;
- standalone, offline, one-plugin-per-platform goal fixed;
- minimum Stata ABI fixed at SPI 3.0 / Stata 14.1+;
- academic bundle, BibTeX/natbib, MIT, GitHub Releases, and compiler-only v1 scope approved;
- direct-to-`main` exact-SHA licensed Stata/Rust CI established and qualified;
- detailed implementation plan recorded.

In progress:

- pinned Rust workspace;
- deterministic Tectonic indexed-tar to embedded ZIP transformation;
- Rust core compilation API and diagnostics;
- native Stata SPI bridge;
- end-to-end `texpdf.ado` command.

## Qualification boundary

The current green receipts qualify the CI and documentation bootstrap only. They do not yet qualify a Tectonic engine, embedded resource bundle, native plugin, or public Stata command. Each milestone will update this file with its exact qualified source SHA.
