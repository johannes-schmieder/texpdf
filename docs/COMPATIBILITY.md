# LaTeX compatibility policy

## Engine

`texpdf` uses Tectonic 0.17.0, whose TeX engine is derived from XeTeX. It is
not a byte-for-byte or primitive-for-primitive replacement for `pdflatex`.
Documents written against ordinary LaTeX interfaces are the intended use case;
documents that depend on pdfTeX-specific primitives or external programs may
need changes.

## Supported 0.1.0 tier

The v1 compatibility target is common academic/econometric material:

- standard LaTeX article/report/book structures;
- AMS mathematics;
- conventional tables, including `booktabs`, `longtable`, and related tools;
- PDF, PNG, and JPEG figures supported by the engine;
- cross-references and hyperlinks;
- BibTeX with natbib;
- English-language hyphenation and standard English aliases;
- deterministic bundled fonts required by the supported fixtures.

A package is advertised as supported only after a redistributable fixture using
that package passes with the final curated bundle on every supported platform.
Presence of a file in the bundle is not by itself a support guarantee.

## Release real-world corpus

The release source carries a synthetic corpus modeled on current latexlog
reports, a legacy report, and a conventional multi-file economics manuscript.
It tests visibly colored PDF and PNG figures, generated-style tables,
landscape/tabularx layouts, relative inputs, equations, natbib, `cleveref`, and
`aer.bst`. The current latexlog and manuscript scenarios require actual
chromatic drawing content; the legacy blackwhite scenario remains deliberately
monochrome and includes real PDF graphs rather than layout placeholders.

The runnable Stata help examples additionally cover tables exported by
`table`/`collect`, `latexlog`, and the built-in `etable` command. The `etable`
example exports a `tableonly` LaTeX fragment and places it in a minimal wrapper
document. Stata's complete-document `etable` export adds packages outside the
current bundle and is therefore not the documented compatibility path.

`colortbl`, `cleveref`, and `aer.bst` are included in the 0.1.0 compatibility
corpus. Windows licensed-runtime behavior is supported through the documented
RC2-to-final equivalence record; the exact final Windows package independently
passed the hosted Rust/corpus and binary audits. The obsolete `subfigure`
package is retained only for legacy compatibility; its isolated fixture is
warning-free. Use `subcaption` for new work.

## Deliberate exclusions

The 0.1.0 tier excludes:

- shell escape and arbitrary external commands;
- minted/Pygments;
- Biber/biblatex;
- Beamer;
- TikZ/PGF and PSTricks;
- workflows requiring Ghostscript, Inkscape, Python, R, Stata, or another
  external program during compilation;
- arbitrary system fonts that are not embedded in the release bundle;
- remote package retrieval.
- broad language and hyphenation collections.

Some excluded documents may happen to compile with a development bundle. That
does not make the package part of the supported contract.

## Filesystem behavior

- The directory containing the primary `.tex` file is the compilation root.
- Relative `\input`, bibliography, and figure paths are resolved from that
  project tree.
- Spaces and Unicode paths are part of the qualified behavior.
- The final PDF is installed only after a successful compile.
- An existing output is preserved if a replacement compile fails.
- Input and output may not resolve to the same file.

## Reproducibility

The plugin carries a locked resource ZIP and reports both the Tectonic bundle
content digest and the ZIP SHA-256. The command does not silently consult the
user's TeX tree or download a missing package. A missing unsupported resource
therefore fails explicitly rather than making output machine-dependent.

## Adding packages

A proposed package is added only after:

1. its complete resource/font dependency closure is resolved;
2. its license and required notices are recorded;
3. a minimal fixture and a realistic corpus fixture pass;
4. its incremental bundle-size cost is measured;
5. the package does not require prohibited external execution;
6. the final artifact passes all supported-platform Stata runtime tests.
