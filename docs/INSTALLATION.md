# Installation channels

The authoritative release and distribution policy is
[`../RELEASING.md`](../RELEASING.md). Installation instructions must preserve
the distinction between stable SSC distribution, development on `main`, and an
exact historical GitHub release.

## Stable installation from SSC

SSC is the normal stable channel. After the first final version is accepted,
ordinary users install with:

```stata
ssc install texpdf
```

The SSC files must be taken from the corresponding final immutable GitHub tag
and Release. SSC must never receive a release candidate or files rebuilt from a
later `main` tip. The project is not yet available on SSC, so this command is
documented policy rather than a currently working installation route.

## Development installation from `main`

`main` answers “what are we developing now?” It is never described as the
latest stable release. When a public development installation tree is enabled,
its command is:

```stata
net install texpdf, replace ///
    from("https://raw.githubusercontent.com/johannes-schmieder/texpdf/main/stata/")
```

`texpdf` contains a compiled plugin, and the private source tree does not
currently commit a platform binary under `stata/`. Until CI publishes a public
flat development tree, install development builds from the platform-specific
CI artifact and verify its manifest. This limitation must not be hidden by
publishing a command that cannot supply the plugin.

## Exact historical versions

A final tag such as `v0.2.0` is the immutable answer to “what exactly was
version 0.2.0?” If the tag contains the applicable installation tree:

```stata
net install texpdf, replace ///
    from("https://raw.githubusercontent.com/johannes-schmieder/texpdf/v0.2.0/stata/")
```

When compiled binaries are distributed only as GitHub Release assets, use the
platform-specific immutable asset or versioned installation URL recorded in
that Release. Never substitute a binary from `main` into a historical tagged
installation.

## Compiled release artifacts

A final GitHub Release may contain:

- one deterministic ZIP per supported platform;
- a combined SHA-256 manifest;
- source and qualification metadata;
- complete third-party notices and inventories.

Each installable platform tree contains `stata.toc`, `texpdf.pkg`, the ado and
help files, the correct `_texpdf_plugin.plugin`, project and third-party
notices, `BUILD_INFO.json`, and `CHECKSUMS.sha256`. A package is supported only
when its plugin was built from and qualified for the final tag.

## Offline operation

Internet access is needed only to install or update the package. After the ado,
help, notices, and target plugin are installed, compilation is offline and does
not retrieve TeX packages or a separate compiler.

## Release verification

Before publishing an installation tree or sending it to SSC:

1. check out the exact final tag and require a clean worktree;
2. run `python3 ci/check_release_metadata.py --tag vX.Y.Z`;
3. compare the plugin and ZIP hashes with the GitHub Release checksum manifest
   and committed qualification records;
4. run a clean local `net install` from the exact distribution directory on
   every supported platform;
5. compile the release corpus offline.

These checks establish that GitHub tag, GitHub Release, and SSC package all
refer to the same stable version even after development continues on `main`.
