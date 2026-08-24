# Licensing and redistribution policy

## Project-owned source

Source written specifically for `texpdf` is distributed under the MIT License
in the repository root.

## Tectonic and Rust dependencies

Tectonic is MIT licensed. Its dependency graph contains packages under several
permissive and weak-copyleft licenses. The release process must generate a
locked dependency inventory with:

```sh
python3 tools/generate_dependency_inventory.py --require-declared
```

The generated inventory records each package version and its declared SPDX
license expression or license file. A release must also include the license
texts required by those dependencies; the inventory by itself is not a
substitute for notices.

## Native libraries

The standalone plugin statically incorporates native libraries used by
Tectonic, including Fontconfig, FreeType, Graphite2, HarfBuzz, ICU, libpng, and
zlib. Their licenses and notices must accompany every binary release. The build
must not assume that static linking makes those obligations disappear.

## Embedded TeX resources and fonts

The curated ZIP is assembled from a pinned Tectonic/TeX Live resource bundle.
Those files retain their individual upstream licenses. Common license families
include the LaTeX Project Public License, SIL Open Font License, GPL-compatible
licenses, permissive font licenses, and public-domain material, but no release
may infer one blanket license for the bundle.

The final release inventory must map every embedded logical path to either:

1. a TeX Live package and its catalogue license metadata; or
2. an explicitly reviewed standalone resource/font license.

For every included package/font, the release must retain required notices and
make source or modification information available where its license requires
that. The generated resource manifest and the upstream source-bundle digests
must be shipped alongside the binary checksums.

## Release gate

Public GitHub Release publication is blocked until all of the following exist:

- a complete Rust dependency inventory and required license texts;
- native-library license texts and notices;
- a complete embedded-resource/package/font inventory;
- all notices required by the resource licenses;
- checksums tying the inventory to the exact embedded ZIP and plugin.

Development artifacts may be retained privately for qualification, but they
must be marked non-release and must not be represented as license-complete
public binaries.
