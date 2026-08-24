# Licensing and redistribution policy

## Project-owned source

Source written specifically for `texpdf` is distributed under the MIT License
in the repository root.

## Tectonic and Rust dependencies

Tectonic is MIT licensed. The installed plugin embeds a separately built helper,
so the release graph is the deduplicated union rooted at `texpdf-stata` and
`texpdf-helper`, not the bridge graph alone. The release process generates the
locked inventory with:

```sh
python3 tools/generate_dependency_inventory.py --require-declared
```

The generated inventory records each package version and its declared SPDX
license expression or license file. Upstream notice files are copied when
present. Crates that publish only standard MIT/Apache SPDX metadata use the
committed canonical-text policy; other missing/custom expressions fail closed.

## Native libraries

The helper embedded in the standalone plugin statically incorporates native
libraries used by Tectonic, including Fontconfig, FreeType, Graphite2,
HarfBuzz, ICU, libpng, and zlib. Their licenses and notices must accompany every
binary release. The build must not assume that static linking makes those
obligations disappear.

## Embedded TeX resources and fonts

The curated ZIP is assembled from a pinned Tectonic/TeX Live resource bundle.
Those files retain their individual upstream licenses. Common license families
include the LaTeX Project Public License, SIL Open Font License, GPL-compatible
licenses, permissive font licenses, and public-domain material, but no release
may infer one blanket license for the bundle.

The final release inventory must map every embedded logical path to either:

1. a TeX Live package and its catalogue license metadata; or
2. an explicitly reviewed standalone resource/font license.

Every reviewed override is tied to exact resource bytes and pinned evidence.
The generated TeX notice tree binds all resource hashes to a committed full
license or resource-specific notice and preserves AMSFonts Reserved Font Names.
The resource attribution manifest and upstream source-bundle digests ship with
the binary checksums.

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
