# Third-party components and redistribution status

`texpdf` project-owned source code is licensed under the MIT License in
`LICENSE`. The standalone plugin also incorporates third-party software and TeX
resources that retain their upstream copyrights and licenses.

## Tectonic

The embedded typesetting engine is Tectonic 0.17.0. Tectonic is distributed
under the MIT License. Its source version is pinned by `Cargo.toml` and the
release dependency graph.

## Native libraries

The macOS plugin statically incorporates the native libraries needed by
Tectonic, including Fontconfig, FreeType, Graphite2, HarfBuzz, ICU, libpng, and
zlib. The pinned vcpkg revision and build procedure are recorded in
`tools/prepare_native_deps.sh`. These projects retain their upstream licenses.
The qualification manifest confirms that the resulting plugin has no runtime
Homebrew or vcpkg-library dependency.

## TeX and LaTeX resources

The embedded resource ZIP is a curated subset of Tectonic's version-33 bundle,
which derives from TeX Live. Individual TeX/LaTeX packages, support files,
fonts, encodings, maps, and bibliography styles retain their own upstream
licenses. These include LPPL, permissive, free-font, public-domain, and other
free-software terms depending on the resource.

`bundle/curated-manifest.json` is the authoritative file-level inventory. It
records every embedded resource name, source byte range, and SHA-256 digest.
`bundle/QUALIFICATION.json` records the exact source archive, index, transformed
ZIP, plugin, and installation-package digests used in qualification.

## Public binary release gate

The software is implemented and privately qualified on macOS Apple Silicon,
but public binary publication remains gated on producing a complete
package/font-to-license mapping and shipping all required upstream notices with
the GitHub Release. This file is a provenance summary; it is not yet the final
release license inventory.
