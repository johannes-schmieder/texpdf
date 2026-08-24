# Third-party notices

This file is a human-readable index. The public release package must include
complete license texts and a generated machine-readable inventory tied to the
exact plugin and resource-bundle checksums.

The deterministic ZIP carries that complete tree under `LICENSES/`. It is not
enumerated in `texpdf.pkg`, because Stata imposes a package-file size limit;
`net install` installs this index and the runtime files, while the adjacent ZIP
is the authoritative complete notice archive.

## Tectonic

`texpdf` embeds Tectonic 0.17.0. Tectonic is distributed under the MIT License.
Copyright and license information from the pinned Tectonic source distribution
must be retained with binary releases.

## Native libraries

The embedded compiler helper incorporates the following native libraries. The
release audit copies their upstream copyright and license texts into the exact
package notice directory:

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

The exact Rust dependency graphs are defined by `Cargo.lock`. The audit takes
the deduplicated union rooted at both `texpdf-stata` and `texpdf-helper`; the
helper is embedded at build time and is not a Cargo dependency of the bridge.
Run:

```sh
python3 tools/generate_dependency_inventory.py --require-declared
```

The resulting inventories record every package version and declared license.
Upstream notice files are copied when shipped. If a crate declares only MIT or
Apache-2.0 (or their OR combination) and ships no notice, the explicit
canonical-SPDX policy copies the standard text and retains complete per-crate
attribution. Other missing or custom expressions fail closed.

## Embedded TeX/LaTeX resources and fonts

The embedded ZIP contains a curated subset of a pinned Tectonic/TeX Live
resource bundle. Each package and font retains its upstream license. There is
no blanket `texpdf` license for those resources.

The release is license-complete only when the exact-source audit confirms that:

- identifies every embedded logical resource;
- maps each resource to an upstream package/font or an individually reviewed
  standalone license;
- reports no unresolved resources;
- records the exact embedded ZIP SHA-256;
- `tex-notices.json` binds every resource SHA to a committed full license or
  resource-specific notice;
- `license-texts.json` covers the union of both Rust binary graphs and every
  linked native library;
- `STATUS.json` reports `release_license_complete: true` with every stage zero.

Private-development artifacts remain non-public regardless of audit status;
public publication is a separate fail-closed release gate.
