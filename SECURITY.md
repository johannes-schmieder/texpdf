# Security policy

## Supported use

`texpdf` compiles LaTeX controlled by the Stata user. It is not a sandbox for
hostile documents.

The release configuration provides these boundaries:

- shell escape is forcibly disabled;
- document-selected external helper programs are unsupported;
- no remote bundle or runtime package downloader is configured;
- Tectonic and its native libraries execute in a short-lived helper process;
- the embedded helper is architecture-checked and SHA-256-verified before use;
- the helper is launched directly without a shell and has a bounded timeout;
- helper identity and versioned results are validated on every operation;
- result values are normalized before Stata interpolation so compiler text
  cannot be reinterpreted as quote or macro syntax;
- Rust panics are caught at the ABI boundary and helper dispatch;
- diagnostics are bounded and output replacement is atomic.

## Filesystem trust boundary

TeX documents can request local inputs, images, bibliography databases, and
fonts. The primary project root is the source-file directory, but `texpdf` does
not claim an operating-system sandbox against every absolute path, symlink, or
traversal behavior in the underlying engine.

Do not compile an untrusted document in an account that can read sensitive
files. Use an OS sandbox, container, or low-privilege account for hostile input.
Release tests characterize traversal, absolute inputs, symlinks, malformed
fonts/images, recursion, oversized diagnostics, resource exhaustion, and
cancellation behavior.

## Native process boundary

The one-installed-plugin architecture runs the compiler in an embedded helper
process. A helper abort, signal, or panic must become a bounded Stata error
instead of terminating Stata. The bridge verifies cached bytes against the
build-time digest and rejects an identity-, operation-, protocol-, or
status-mismatched result.

This is process isolation, not an OS sandbox. A hostile document can still
consume resources or exercise files visible to the helper. Repeated-call,
malformed-input, timeout, memory-growth, orphan-process, and post-error-recovery
gates remain part of qualification.

## Reporting vulnerabilities

Use GitHub's private vulnerability reporting for this repository. Include
the exact source/tag and plugin SHA-256, OS/architecture/Stata version, a minimal
nonconfidential reproducer, and the outcome category. Do not include
credentials, Stata license material, confidential data, or unrelated files in
an issue or CI artifact.
