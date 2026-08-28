# Changelog

All notable user-facing changes to `texpdf` are recorded here. `Unreleased`
describes development on `main`; dated sections are created only for final
releases. Release candidates are testing checkpoints, not stable
releases or SSC versions.

## Unreleased

No user-facing changes yet.

## 0.1.0 - 2026-08-28

### Added

- A compiler-only Stata command, `texpdf using ...`, with `saving()`,
  overwrite-safe `replace`, and `texpdf, version`.
- A native Stata plugin containing an isolated target helper, Tectonic 0.17.0,
  and a curated academic TeX resource bundle for offline compilation.
- Structured diagnostics, ABI panic containment, shell-escape denial, atomic
  output installation, and recovery after failed compilations.
- Fixture-backed support for mathematics, tables, layout, PDF/PNG figures,
  fonts, hyperlinks, BibTeX, and `natbib`, including spaces, Unicode, and
  relative inputs.
- Deterministic Stata package assembly, clean local `net install` tests, and
  exact-source Rust/licensed-Stata receipts.
- Universal macOS packaging with licensed runtime qualification on Apple
  Silicon and a built, inspected, explicitly untested Intel compatibility slice.
- A 1,000-call licensed-Stata durability gate with injected failures, helper
  lifecycle sampling, and bounded post-warm-up RSS growth.
- Linux x86-64 packaging and licensed Stata/MP 18 and 19 qualification on RHEL
  8 with an enforced GLIBC 2.28 compatibility ceiling.
- Source-bound license inventories, notice collection, SCC accounting, and
  exact artifact identities in release and runtime receipts.
- A source-only synthetic real-world corpus for current latexlog reports,
  legacy `subfigure` output, and conventional multi-file economics manuscripts,
  including an optional hash-pinned latexlog regeneration contract.
- Development-tested offline resources for `colortbl`, `cleveref`, the
  `economic` package's `aer.bst`, and legacy `subfigure` compatibility.
- An opt-in `view` option that opens a successfully compiled PDF in the
  operating system's default viewer without changing batch-mode defaults.
- Three self-contained, one-click help examples for manual `file write` report
  construction, the suggested but optional `latexlog` workflow, and a polished
  three-model regression table created with Stata's built-in `etable`.
- Cross-platform distribution support with canonical macOS, Linux, and Windows
  plugin filenames, one plugin per GitHub package, and all three in the single
  SSC package.
- Fail-closed Windows Stata/MP 19 qualification tooling, including full corpus,
  help-example, recovery, offline/no-system-TeX, and 1,000-call stress gates.
- Deterministic SSC combination with a compressed complete license archive,
  combined build manifest, checksums, and a maintainer-approved `.pkg` index
  that selects and load-checks exactly one native plugin for the host platform.
- A static public-workflow security audit for immutable action pins, minimal
  permissions, and prohibition of pull-request execution on licensed or
  self-hosted runners.

### Changed

- Installed help now includes the author's website, GitHub profile, email, an
  invitation for suggestions, a prominent Tectonic acknowledgement, and an
  exact manifest-checked inventory of every bundled LaTeX interface.
- The README now has a shorter project-state summary and a prominent, linked
  acknowledgement of the Tectonic project and its contributors.
- Help wording now describes only included capabilities, identifies the
  current version directly, and keeps the `latexlog` and `etable`
  cross-references together.
- Release readiness now distinguishes active development, immutable candidate
  source, target runtime evidence, and public-distribution authorization.
- Automatic evidence publishers preserve the frozen release-candidate source
  instead of replacing it with later green development commits.
- Release and distribution policy now defines SSC as the stable user channel,
  GitHub final tags as immutable snapshots, and `main` as development.
- Bundle selection name/version now live in the pinned bundle lock, and current
  development identity is recorded separately from frozen candidate evidence.
- Release scope and readiness are data-driven for RC/final version, exact
  source, required targets, public GitHub authorization, and SSC authorization.
- Public license manifests use portable provenance labels instead of local
  machine paths.
- GitHub packages retain explicit platform plugin names, while SSC uses Stata's
  `g`/`h` package directives plus a versioned installation marker; mixed,
  incomplete, and stale installation layouts now fail closed.
- Intel/Rosetta is no longer a required runtime qualification target. The
  universal macOS distribution still carries the x86-64 compatibility slice,
  with readiness enforcing that no runtime-support claim is made for it.

### Fixed

- The macOS durability gate now downloads, verifies, and tests the exact
  source-bound universal candidate package instead of rebuilding a separate
  native helper. Memory evidence is bound to the universal workflow run,
  artifact digest, package ZIP, universal plugin, and embedded ARM helper.
- Cross-platform package assembly now canonicalizes shared Stata metadata to
  LF and sanitizes host paths and target-local vcpkg labels from public license
  evidence, keeping the macOS, Linux, Windows, and combined SSC archives
  byte-coherent without altering the underlying notice texts.
- Development memory-stress publication now preserves the frozen candidate's
  canonical record and stores newer `main` attempts separately.
- Real-world modern corpus figures now contain obvious navy/orange color, and
  manifest validation rejects declared color PDF/PNG assets whose drawing
  content is actually monochrome. Snapshot normalization also preserves the
  intended orientation of Stata PDF graphs instead of auto-rotating a panel.
- The legacy blackwhite corpus now embeds two real monochrome PDF graphs instead
  of empty framed placeholders, with manifest checks for inclusion and color.
- Exact bundle reconstruction preserves every metadata field required by the
  embedded Rust bundle reader.
- Linux pkgconf probes use the same GNU feature environment as the compiled
  bootstrap and invalidate older incompatible cache entries.
- Temporary paths, Python selection, and the licensed-Stata lock work across
  macOS and Linux.
- Release builds reject stale helpers whose embedded bundle identity differs
  from regenerated bundle metadata.
- Windows builds link the MSVC CRT statically and reject dynamic CRT imports.
- Windows checkouts preserve the byte-exact LF form of the generated
  `language.dat` resource so deterministic bundle reconstruction has the same
  identity on every supported operating system.
- The Stata dispatcher reuses only its verified platform binding and fails
  closed on an unknown/stale resident plugin instead of trying to reload a
  native library within the same session.
- Licensed qualification now stages the same marker-free GitHub installation
  layout that users receive, including build-produced plugins used by the
  1,000-call stress lane, so the SSC source marker cannot be misidentified as a
  second installed distribution channel.
- Hosted Linux and Windows builders fetch only the selected TeX resource ranges
  and require the result to match every frozen bundle identity field, avoiding
  multi-gigabyte archive downloads and the rate limits they triggered.
- Windows checkouts preserve LF bytes for every repository input whose raw
  content is validated during bundle reconstruction, including the resource
  policy and committed resource trace.
- Hosted builders pin Cargo, rustc, and the rustup proxy environment to the
  same release toolchain, preventing runner-default upgrades and concurrent
  component-install races during compilation.
- Hosted Ubuntu Linux artifacts are explicitly development-only and report
  their actual GLIBC requirements; the strict GLIBC 2.28 release ceiling
  remains exclusively enforced on the canonical SCC RHEL 8 build.
- Windows binary audits locate the installed Visual C++ tools with Microsoft's
  version-independent `vswhere` interface instead of assuming a Visual Studio
  2022 directory on newer hosted runner images.
- License-audit publication derives the active candidate from the authoritative
  `main` release scope, so an exact implementation checkout cannot route current
  candidate evidence into the historical development namespace.
- macOS ARM qualification records the actual Stata edition and version from
  its runtime receipt instead of emitting a hard-coded version claim.
- The canonical Windows builder now requires an explicit successful
  exact-source license-audit artifact, verifies the complete ignored license
  text tree and audit status, emits a public-release package with that unpacked
  tree, and writes portable LF-only package checksums.
- Licensed Windows runtime receipts use a stable release-runner label instead
  of recording the private test machine's computer name.
