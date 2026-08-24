# Embedded TeX resource bundle

`texpdf` embeds a deterministic ZIP-format Tectonic bundle in each native
plugin. Runtime compilation never downloads packages and never consults a
system TeX tree.

## Current qualified bundle

The qualified bundle is `texpdf-academic-v1`, derived from the pinned
Tectonic/TeX Live 2022 resources and the `tlextras-2022.0` local-resource
archive.

Current exact artifact values:

- 557 logical resources;
- 19,035,195 uncompressed resource bytes;
- 6,690,289-byte deterministic ZIP (6.38 MiB);
- ZIP SHA-256
  `05688ffcca2e82a12143c836708e3dc3b811a30dbe2b74caf951eb7b409792ab`;
- Tectonic content digest
  `273502edfafe0a6adcdd19c0659965bcf0ebea26cacc1ad372439b80fd7a2a81`.

The exact bundle/plugin/package qualification is recorded in
`QUALIFICATION.json`. Platform support is authoritative in
`../release/targets.json`, and the human-readable current artifact summary is
`../docs/generated/CURRENT_ARTIFACT.md`.

`curated-manifest.json` records the selected resource names, byte ranges,
source hashes, and selection reasons. Generated archives themselves are not
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

The build and CI tooling verifies the exact ZIP hash before embedding it. The
same curated ZIP is used for all platform targets.

## Compatibility policy

The public v1 compatibility tier is fixture-backed. The integrated academic
corpus exercises the supported math, table, layout, figure, font, hyperlink,
and bibliography packages. A package is not considered supported merely
because a similarly named file is present in the ZIP.

The exact user-facing contract is documented in
`../docs/SUPPORTED_PACKAGES.md` and `../docs/COMPATIBILITY.md`.

Large or external-helper-dependent ecosystems—Beamer, TikZ/PGF, PSTricks,
Biber/`biblatex`, and `minted`/Pygments—are excluded from v1.

## Licensing

Every embedded resource retains its upstream license. The file-level manifest
is not by itself a complete redistribution notice. The source-bound license
audit under `../licenses/generated/` must map every resource to reviewed
package/font evidence and collect all required license texts before public
binary publication.

Development qualification artifacts remain non-public until
`../licenses/generated/STATUS.json` reports `release_license_complete: true`
and the fail-closed release audit passes.
