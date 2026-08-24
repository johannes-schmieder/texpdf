# Third-party notices

This file is a human-readable index. The public release package must include
complete license texts and a generated machine-readable inventory tied to the
exact plugin and resource-bundle checksums.

## Tectonic

`texpdf` embeds Tectonic 0.17.0. Tectonic is distributed under the MIT License.
Copyright and license information from the pinned Tectonic source distribution
must be retained with binary releases.

## Native libraries

The standalone plugin incorporates the following native libraries. Their
upstream copyright notices and complete license texts must be copied into the
release notice directory by the release build:

| Component | License family |
|---|---|
| Fontconfig | Fontconfig MIT-style license |
| FreeType | FreeType License or GPL-2.0-or-later |
| Graphite2 | MPL-2.0 |
| HarfBuzz | MIT |
| ICU | ICU License |
| libpng | libpng-2.0 |
| zlib | Zlib |

## Rust crates

The exact Rust dependency graph is defined by `Cargo.lock`. Run:

```sh
python3 tools/generate_dependency_inventory.py --require-declared
```

The resulting `licenses/generated/dependencies.json` and `.md` inventory every
package version and declared license. The release process must additionally
copy all required license texts; declared SPDX expressions alone are not the
full notices.

## Embedded TeX/LaTeX resources and fonts

The embedded ZIP contains a curated subset of a pinned Tectonic/TeX Live
resource bundle. Each package and font retains its upstream license. There is
no blanket `texpdf` license for those resources.

The release is not license-complete until
`licenses/generated/tex-resources.json`:

- identifies every embedded logical resource;
- maps each resource to an upstream package/font or an individually reviewed
  standalone license;
- reports no unresolved resources;
- records the exact embedded ZIP SHA-256;
- is marked `license_complete: true`;
- is accompanied by all required notices and source/modification information.

Until then, generated plugin artifacts are development qualification artifacts,
not public redistributable releases.
