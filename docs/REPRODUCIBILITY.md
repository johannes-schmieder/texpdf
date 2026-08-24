# Reproducibility policy

`texpdf` separates deterministic inputs from platform-toolchain binary
reproducibility.

## Locked deterministic inputs

A release pins:

- the exact Git source SHA;
- Rust 1.97.1 and `Cargo.lock`;
- Tectonic 0.17.0;
- the v33 source bundle and source index SHA-256 values;
- the curated logical-resource list;
- the transformed embedded ZIP SHA-256;
- vcpkg source revision and custom target triplets;
- release profile and deployment target;
- academic fixture corpus;
- generated third-party inventories.

The deterministic ZIP builder fixes entry ordering, timestamps, permissions,
compression settings, and digest metadata. The same source bundle and logical
resource list must reproduce the same embedded ZIP SHA-256.

## Runtime document reproducibility

The plugin does not consult a system TeX tree or download missing packages.
Therefore package and bundled-font selection is stable across machines for the
supported compatibility tier.

PDF byte equality can still be affected by document inputs such as dates,
absolute paths, generated identifiers, and explicitly selected system fonts.
Users who require byte-reproducible documents should set `SOURCE_DATE_EPOCH`,
avoid system-font lookup and volatile metadata, and preserve every input asset.

## Native binary reproducibility

The release process records, but does not yet promise, bit-for-bit identical
plugins across independent machines. Native linkers may emit build identifiers,
load-command UUIDs, and path-dependent data. Each target artifact is therefore
identified by its SHA-256 and exact build/qualification record.

Before claiming reproducible native binaries, the release process must perform
two clean builds from the same source and compare:

- embedded ZIP digest;
- exported symbols;
- dynamic dependency policy;
- minimum OS/GLIBC requirements;
- plugin bytes and SHA-256;
- deterministic installation ZIP bytes and SHA-256.

A binary mismatch is not hidden; it is either eliminated or documented as a
known toolchain source of nondeterminism.

## Qualification identity

A source SHA, plugin SHA-256, bundle ZIP SHA-256, and target runtime receipt form
one qualification identity. Rebuilding a plugin changes the binary identity and
requires a new target runtime qualification even when the Git source SHA is
unchanged.
