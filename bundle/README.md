# Embedded TeX resource bundle

`texpdf` embeds a deterministic ZIP-format Tectonic bundle in each native plugin. Runtime compilation never downloads packages and never consults a system TeX tree.

## Source and transformation

The initial implementation uses Tectonic's version-33 indexed-tar resource as a bootstrap source. `tools/prepare_bundle.py` downloads the raw archive and gzip-compressed index into a cache, verifies locked checksums, reconstructs each logical file from the indexed byte range, and writes a deterministic ZIP archive at:

```text
bundle/generated/texpdf-bundle.zip
```

The generated archive is not committed to Git. It is a reproducible build input and is incorporated into the Rust binary with `include_bytes!()`.

The transformed ZIP must contain a valid 64-character `SHA256SUM` entry because Tectonic's `ZipBundle` uses that value as the bundle identity.

## Bundle policy

The first proof may embed the complete source bundle. Before v1, the bundle will be reduced to the package/font dependency closure advertised in `packages.toml`, with one compiling fixture per claimed top-level package. The final bundle manifest, source checksum, transformed checksum, file count, size, and licenses are release artifacts.

No generated bundle or license inventory is considered final until the offline corpus and redistribution audit are complete.
