# Embedded TeX resource bundle

`texpdf` embeds a deterministic ZIP-format Tectonic bundle in each native
plugin. Runtime compilation never downloads packages and never consults a
system TeX tree.

## Qualified bundle

The current qualified bundle is `texpdf-academic-v1`, derived from Tectonic's
version-33 indexed-tar resource and the pinned `tlextras-2022.0` local-resource
archive.

Exact qualified values:

- 477 logical resources;
- 14,393,356 uncompressed resource bytes;
- 6,692,142-byte deterministic ZIP;
- ZIP SHA-256
  `164a849049ae627d0b15ae28a9b5ad5930121c95b17827b528e1666fd62ca6e6`;
- Tectonic content digest
  `675375703bc247518c61902cbefccb2066d9e41c4d613c274f4a97fdf9fcce31`.

The full qualification record is `QUALIFICATION.json`. The file-by-file
selection, source byte ranges, and hashes are in `curated-manifest.json`.

## Reproducible construction

`tools/prepare_bundle.py` reconstructs the complete pinned source ZIP from the
indexed tar. `tools/trace_resources.py` and the corpus identify requested
resources. `tools/prepare_curated_bundle.py` then computes a deterministic
closure over the source/local resource indices and writes:

```text
bundle/generated/texpdf-bundle.zip
bundle/generated/bundle-info.json
bundle/generated/curated-manifest.json
```

Generated archives are not committed. The Rust core incorporates the selected
ZIP with `include_bytes!()` and opens it through Tectonic's in-memory
`ZipBundle` implementation.

The bundle's `SHA256SUM` entry is recomputed from the selected resources. Source
archive, index, local archive, and local index checksums are pinned in
`bundle.lock.toml`.

## Compatibility policy

`packages.toml` defines the advertised academic package groups. The integrated
corpus exercises every current top-level package claim along with BibTeX and
natbib. A package is not considered supported merely because a similarly named
file is present; it must compile in the offline corpus.

Large or external-helper-dependent ecosystems—Beamer, TikZ/PGF, PSTricks,
Biber/biblatex, and minted/Pygments—are excluded from the initial tier.

## Licensing

Every resource retains its upstream license. `curated-manifest.json` is the
file-level provenance inventory. A complete package/font-to-license mapping and
all required notices remain the final gate before public binary publication;
see `../THIRD_PARTY_NOTICES.md`.
