# Error and diagnostic contract

The ado layer converts the native result record into ordinary Stata return
codes. The plugin itself normally returns zero after writing a valid failure
record so the ado program can display bounded TeX diagnostics before exiting
with the recorded code.

| Return code | Meaning |
|---:|---|
| `198` | invalid command syntax, invalid flag, unsupported result schema, or input/output path conflict |
| `459` | LaTeX/Tectonic compilation failure |
| `601` | input is missing or not a regular file |
| `602` | output exists and `replace` was not specified |
| `603` | filesystem or output-installation failure |
| `710` | internal bundle, synchronization, result-record, or panic-containment failure |

## Diagnostic behavior

- Normal engine chatter is suppressed.
- Errors and warnings are captured by a structured Tectonic status backend.
- The native layer bounds the number and length of records.
- Newlines and NULs are sanitized before the line-oriented result is parsed by
  Stata.
- Large logs are not stored in Stata macros.
- A Rust panic is converted into `r(710)` if unwinding reaches the Rust ABI
  guard. Native aborts or signals cannot be converted and remain part of the
  helper-backed installed-plugin safety gate.

## Output guarantees

- Compilation occurs in a staging directory on the output filesystem.
- The final PDF is installed only after Tectonic reports success and a valid PDF
  exists.
- Without `replace`, an existing destination is never modified.
- With `replace`, an ordinary TeX failure preserves the existing destination.
- The hardened installer uses atomic replacement on POSIX systems and a
  backup/restore transaction on Windows.
- Input and output may not identify the same file.

## Missing or unsupported packages

The standalone bundle never downloads a missing package and never falls back
to the user's TeX installation. A document outside the supported compatibility
tier therefore fails explicitly with `r(459)`. This is intentional: silent
machine-dependent fallback would violate the standalone and reproducibility
contract.
