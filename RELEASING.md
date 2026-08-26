# Releasing texpdf

This is the authoritative policy for developing, versioning, releasing, and
distributing `texpdf`. Technical qualification details live in
[`docs/RELEASE.md`](docs/RELEASE.md); release history lives in
[`CHANGELOG.md`](CHANGELOG.md).

## Distribution channels

The project has three distinct channels:

| Channel | Meaning | Mutable? |
|---|---|---|
| `main` | Active development toward the next release | Yes, by new commits |
| Git tag and GitHub Release `vX.Y.Z` | Exact source and artifacts for stable version `X.Y.Z` | No |
| SSC package | Stable version recommended to ordinary Stata users | Replaced only by a newer final release |

`main` is not the latest stable release. It may contain fixes, new features,
metadata, or qualification work that SSC users do not yet receive. After a
release, development normally continues immediately on `main`.

Release candidates use tags such as `v0.2.0-rc1` and `v0.2.0-rc2`. They are
GitHub prereleases for testing only and must never be submitted to SSC. A
release candidate does not become final automatically: creating `v0.2.0` is a
separate, explicit release decision.

The existing private `v0.1.0-rc.1` prerelease is historical, macOS-only, and
superseded. Preserve its tag and assets; all new RC tags use `-rcN`.

## Version numbers and immutable tags

Use semantic-style versions:

- increment the patch number for compatible fixes (`0.2.0` to `0.2.1`);
- increment the minor number for compatible features (`0.2.1` to `0.3.0`);
- increment the major number for intentionally incompatible stable changes;
- append `-rcN` only to prerelease tags.

Every published final tag is immutable. Never force-move, rewrite, delete and
recreate, or otherwise change a final tag or its released assets to incorporate
a later source fix. If `v0.2.0` is defective, fix the defect on `main`, repeat
qualification, and publish `v0.2.1`.

## Version metadata

For a final release, these must name the same version and date:

- tag and GitHub Release (`vX.Y.Z`);
- the `*! version X.Y.Z DDmonYYYY` header in `stata/texpdf.ado`;
- the matching header in `stata/texpdf.sthlp`;
- `d Distribution-Date: YYYYMMDD` in `stata/texpdf.pkg`;
- the dated `CHANGELOG.md` heading;
- generated package manifests and release assets;
- the package submitted to SSC.

Do not add a standalone `VERSION` file. Run:

```sh
python3 ci/check_release_metadata.py
```

Before a final tag, also run:

```sh
python3 ci/check_release_metadata.py --tag vX.Y.Z
```

For an RC, use `--tag vX.Y.Z-rcN`. Tag CI repeats this check.

## Development and release workflow

```text
Development on main
        ↓
Update CHANGELOG / docs / version metadata
        ↓
Run complete tests and target qualification
        ↓
Create vX.Y.Z-rc1 if an RC is warranted
        ↓
Test that exact release candidate
        ↓
Fix issues on main and create further RCs as needed
        ↓
Choose the exact final tested commit
        ↓
Create immutable vX.Y.Z tag
        ↓
Create final GitHub Release vX.Y.Z
        ↓
Submit the package built from vX.Y.Z to SSC
        ↓
Continue development on main
```

### Prepare and validate a candidate

1. Finish the intended changes on `main`; do not qualify an uncommitted tree.
2. Move completed changelog entries within `Unreleased` into appropriate
   `Added`, `Changed`, and `Fixed` groups. Do not create a dated final section
   until making the explicit final-release decision.
3. Update the ado/help version headers and `.pkg` distribution date together.
4. Run the metadata check, the complete Rust/Stata suite, license audit,
   platform gates, memory gate, package installation tests, and release
   readiness checks described in `docs/RELEASE.md`.
5. Require exact-SHA receipts for every supported runtime. A build-only binary,
   the tip of `main`, or a receipt for another commit is not release evidence.
6. Build all candidate assets from the chosen commit and record their hashes.
7. Before the first cross-platform freeze, obtain the SSC archive maintainer's
   confirmation that one package may ship the three platform plugins plus the
   compressed `texpdf_licenses.zip`. Record the approved recipient, subject,
   body, and response without committing private correspondence.

If external testing is useful, create an annotated `vX.Y.Z-rcN` tag at that
exact commit and a GitHub prerelease with the corresponding artifacts. RC
notes should be concise and derived from `CHANGELOG.md`. Never send RC files to
SSC.

### Promote tested code to a final release

1. Make an explicit decision that a specific tested commit is the final source.
2. Replace the relevant `Unreleased` entries with a dated
   `## X.Y.Z - YYYY-MM-DD` changelog section; leave a fresh `Unreleased`
   section at the top.
3. Re-run `ci/check_release_metadata.py --tag vX.Y.Z` and the strict final
   release gate. If the final metadata commit differs from the last RC, test
   that exact final commit rather than assuming the RC evidence transfers.
4. Create an annotated `vX.Y.Z` tag at the exact qualified source. Push it once
   and treat it as immutable.
5. Create a normal GitHub Release from that tag. Use concise notes derived from
   the changelog, mark it latest when appropriate, and attach each supported
   platform package, manifests, notices, and a combined checksum file.
6. Verify every asset was built from the tag, then perform clean installation
   and offline compilation checks from the release distribution.

Compiled release assets may be produced by CI, but their build receipt and
embedded source identity must match the tagged commit. Never attach a binary
built from a later `main` tip.

## SSC publication

SSC is the supported stable Stata channel. Submit only a final GitHub release,
never `main`, an RC, or an untagged rebuild.

Prepare the SSC submission from a clean checkout of `vX.Y.Z` and the exact
platform artifacts attached to that GitHub Release. Before submission:

1. verify `git rev-parse HEAD` is the final tag's commit;
2. run `git status --short` and require an empty worktree;
3. verify the ado/help headers, `.pkg` distribution date, changelog entry, and
   Git tag using `ci/check_release_metadata.py --tag vX.Y.Z`;
4. compare every SSC-bound plugin and package hash with the GitHub Release
   checksum manifest and committed qualification record;
5. run a clean local `net install` from the exact SSC submission directory on
   each supported platform and compile the release corpus offline;
6. archive the submitted file list, hashes, final tag, GitHub Release URL, and
   SSC correspondence in the release record.

The SSC submission is assembled with `tools/assemble_ssc_package.py`. It
combines the already-qualified platform plugins, compresses the identical
license tree as `texpdf_licenses.zip`, and deliberately omits `texpdf.pkg`;
SSC generates the package index. Do not rebuild a plugin during combination.

Run `tools/write_release_index.py` over the macOS, Linux, Windows, and SSC
archives. Its source-bound manifest and combined `SHA256SUMS` are the release
asset index; publish only archives accepted by that invocation.

The SSC package version and GitHub final release must remain the same. If SSC
review reveals a source defect, make the fix on `main` and publish a patch
release before submitting revised files. Do not silently alter the existing
tag or substitute files built from another commit.

## Installation documentation

Once SSC publishes the package, the README's normal installation command is:

```stata
ssc install texpdf
```

GitHub `main` is always labeled as the development version. An exact historical
release is addressed by its immutable tag, for example:

```stata
net install texpdf, replace ///
    from("https://raw.githubusercontent.com/johannes-schmieder/texpdf/v0.2.0/stata/")
```

Because `texpdf` contains a compiled platform plugin, a raw tag is installable
only when that tag contains the applicable installation tree. Otherwise use
the platform-specific immutable asset or installation URL documented by that
GitHub Release. Never point a stable-install instruction at `main`.

## After release

Continue work on `main` under the new `Unreleased` section. If a defect is
reported, record it there, fix and test it normally, and choose the appropriate
patch/minor/major release. Preserve the original final tag and assets as the
answer to “what exactly was version X.Y.Z?”
