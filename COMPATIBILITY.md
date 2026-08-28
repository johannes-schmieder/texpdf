# Compatibility

The canonical compatibility contract is maintained in:

- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for engine and document-level behavior;
- [`docs/SUPPORTED_PACKAGES.md`](docs/SUPPORTED_PACKAGES.md) for the fixture-backed academic package tier;
- [`release/targets.json`](release/targets.json) for operating-system and architecture qualification.

The intended `0.1.0` qualified runtime matrix is macOS Apple Silicon, Linux
x86-64 with GLIBC 2.28 compatibility, and Windows x86-64, across Stata 18 and
19 overall; Windows is specifically tested on Stata/MP 19. The macOS package
remains universal and includes an inspected Intel slice, but that slice is not
runtime-tested or qualified. Current qualification state is read from
`release/targets.json`. A successful build alone is never a support claim.
