# Embedded TeX resource bundle

`texpdf` embeds a deterministic ZIP-format Tectonic bundle in each native
plugin. Runtime compilation never downloads packages and never consults a
system TeX tree.

## Frozen qualified bundle and current development selection

`QUALIFICATION.json` preserves the exact `texpdf-academic-v1` bytes qualified
for the frozen private release candidate. It remains historical evidence and
is not rewritten merely because `main` moves.

`DEVELOPMENT.json` records the newer bundle embedded by `main`. That selection
adds the real-world compatibility corpus and is explicitly not an all-target
qualification or a replacement release candidate. Its current evidence fields
show which bounded development lanes have run and which licensed target lanes
have not been repeated.

Exact file counts, sizes, content digests, and ZIP hashes are recorded in the
corresponding identity record; they are not duplicated in this durable
description. Platform support is authoritative in
`../release/targets.json`, and the human-readable current artifact summary is
`../docs/generated/CURRENT_ARTIFACT.md`.

`curated-manifest.json` records selected resource names, byte ranges, source
hashes, the English-only resource policy, explicit exclusions, and the
project-generated `language.dat`. Generated archives themselves are not
committed.

## Reproducible construction

`tools/rebuild_curated_bundle.py` and `tools/prepare_curated_bundle.py`
reconstruct the selected resources from pinned source archives and write:

```text
bundle/generated/texpdf-bundle.zip
bundle/generated/bundle-info.json
bundle/generated/curated-manifest.json
```

The Rust core incorporates the selected ZIP with `include_bytes!()` and opens
it through Tectonic's in-memory `ZipBundle` implementation. The bundle's
`SHA256SUM` entry is recomputed from the selected content. Source archive,
index, local archive, and local index checksums are pinned by the bundle lock
and manifest records.

The exact rebuilder defaults to `DEVELOPMENT.json`. A release reconstruction
of the frozen candidate must use its recorded source checkout; the manifest on
current `main` describes the newer development selection. The build and CI
tooling verifies the exact ZIP hash before embedding it.

## Compatibility policy

The public v1 compatibility tier is fixture-backed. The integrated academic
corpus exercises the supported math, table, layout, figure, font, hyperlink,
and bibliography packages. The development real-world corpus adds current
latexlog, legacy subfigure, and conventional economics-manuscript structures.
A package is not considered supported merely because a similarly named file
is present in the ZIP.

The exact user-facing contract is documented in
`../docs/SUPPORTED_PACKAGES.md` and `../docs/COMPATIBILITY.md`.

Large or external-helper-dependent ecosystems—Beamer, TikZ/PGF, PSTricks,
Biber/`biblatex`, and `minted`/Pygments—are excluded from v1.
The private RC also supports English-language hyphenation only; broad language
collections are excluded by `resource-policy.json`.

## Licensing

Every embedded resource retains its upstream license. The file-level manifest
is not by itself a complete redistribution notice. The source-bound license
audit under `../licenses/generated/` must map every resource to reviewed
package/font evidence and collect all required license texts before public
binary publication.

Development qualification artifacts remain non-public until
`../licenses/generated/STATUS.json` reports `release_license_complete: true`
and the fail-closed release audit passes.
