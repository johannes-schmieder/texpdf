# Security policy

## Supported use

`texpdf` is intended to compile LaTeX source controlled by the Stata user. It
is not a sandbox for hostile documents.

The release configuration reduces the most important TeX execution risks:

- shell escape is forcibly disabled;
- arbitrary external helper programs are unsupported;
- the engine is given an explicit embedded resource bundle;
- no remote bundle or runtime package downloader is configured;
- Rust panics are caught at the native ABI boundary;
- diagnostics and result records are bounded;
- output replacement occurs only after successful compilation.

## Filesystem trust boundary

TeX documents can request local inputs, images, bibliography databases, and
fonts. The primary project root is the directory containing the source file,
but `texpdf` does not currently claim to provide an operating-system security
sandbox against every absolute path, symlink, or traversal behavior in the
underlying engine.

Do not compile an untrusted document in a Stata process that can read sensitive
files. Use an operating-system sandbox, container, or low-privilege account for
hostile inputs.

Before public v1, tests must characterize and document:

- `..` traversal and absolute input paths;
- symlinks crossing the source tree;
- absolute and relative output attempts from TeX primitives;
- recursive inclusion and capacity exhaustion;
- malformed fonts and images;
- oversized diagnostics and logs;
- cancellation/interrupt behavior.

## Native process boundary

The one-plugin architecture runs Tectonic and its C/C++ engine components
inside Stata. `catch_unwind` prevents Rust unwinding through the C ABI, but it
cannot intercept every native abort, signal, memory-corruption defect, or
resource-exhaustion failure. The in-process stress and malformed-input gates
are therefore part of release qualification.

An ordinary LaTeX error must return a Stata error and leave Stata usable. A
credible process-fatal engine path that cannot be removed or bounded is a
release blocker for the required one-plugin design.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository owner. Include:

- the exact `texpdf` source/tag and plugin SHA-256;
- operating system, architecture, and Stata version;
- a minimal nonconfidential reproducer;
- whether the outcome is data disclosure, unexpected file write, process crash,
  code execution, or resource exhaustion.

Do not include credentials, Stata license material, confidential data, or
unrelated files in an issue or CI artifact.
