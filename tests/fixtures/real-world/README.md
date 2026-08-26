# Real-world compatibility corpus

This corpus exercises realistic document structures without copying research
prose, estimates, data, authorship, or generated outputs from external
projects. The three families are synthetic derivatives:

- `latexlog-current` is generated from deterministic synthetic Stata data
  through the current `latexlog` interface.
- `latexlog-legacy` preserves a legacy report shape, including obsolete
  `subfigure` syntax and relative table inputs.
- `manuscript` is a conventional multi-file economics article with
  cross-references, figures, a regression table, natbib, and `aer.bst`.

`manifest.json` is the versioned contract. It lists every entrypoint and
non-entrypoint source asset, the capabilities each fixture exercises, its
provenance, and the only diagnostics that may be accepted. The top-level list
permits only Tectonic lifecycle notes; empty fixture diagnostic lists therefore
mean warning-free compilation is required.

The two modern scenarios also declare `color_assets`. Validation inspects their
actual PDF drawing operators and PNG pixel data, so a nominally RGB asset that
contains only black, white, and gray cannot silently replace a color figure.
The legacy blackwhite scenario is intentionally monochrome.

The legacy fixture includes two actual monochrome PDF graphs through obsolete
`subfigure` syntax and currently compiles without warnings. Manifest validation
rejects missing, unused, or accidentally colored legacy graph assets. If the
obsolete package begins emitting a platform-specific warning, only an exact
obsolete-package diagnostic may be added; new documents should use `subcaption`.

Validate the corpus structure with:

```sh
python3 ci/check_real_world_corpus.py
```

Compile every entrypoint directly with the embedded offline bundle with:

```sh
cargo test --locked --package texpdf-core --test corpus
```

Set `TEXPDF_CORPUS_OUTPUT` to retain compiled PDFs for inspection. Otherwise
the Rust test uses a temporary directory.

## Optional latexlog regeneration contract

The committed current-latexlog snapshot is checked against one exact
`latexlog.ado` content hash. The separate latexlog checkout is always treated
as read-only. Run:

```sh
LATEXLOG_DIR=/path/to/latexlog \
python3 tools/check_latexlog_fixture.py \
  --stata-bin /path/to/stata-mp
```

Use Stata's command-line executable (`stata-mp` on macOS), not the GUI
executable. The default ten-minute timeout can be adjusted explicitly.

The checker runs Stata in an isolated temporary directory, normalizes only
latexlog's leading date/time comment, and compares the resulting TeX with the
committed snapshot. It verifies that all generated graph assets exist and
have the expected file signatures. Passing `--update` is required to replace
the committed snapshot and graph assets.

Compiled corpus PDFs are review artifacts and are never committed.
