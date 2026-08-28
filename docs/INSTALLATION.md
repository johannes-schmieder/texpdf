# Installation channels

The authoritative release and distribution policy is
[`../RELEASING.md`](../RELEASING.md). Installation instructions must preserve
the distinction between stable SSC distribution, development on `main`, and an
exact historical GitHub release.

## Stable installation from SSC

SSC will be the normal stable channel. Version 0.1.0 has been submitted and is
awaiting publication; once it is available, ordinary users install with:

```stata
ssc install texpdf
```

The submitted SSC archive is the verified asset from the immutable GitHub
0.1.0 release. SSC must never receive a release candidate or files rebuilt
from a later `main` tip. Until publication completes, use the GitHub release.

## Stable installation from GitHub

Download the ZIP for macOS universal, Linux x86-64, or Windows x86-64 from
[`v0.1.0`](https://github.com/johannes-schmieder/texpdf/releases/tag/v0.1.0),
extract it, and install from that directory:

```stata
net install texpdf, replace from("/path/to/extracted/texpdf")
```

## Development installation from `main`

`main` answers “what are we developing now?” and may differ from the stable
release. `texpdf` contains a compiled plugin, and the source tree does not
commit platform binaries under `stata/`. Install development builds only from
the appropriate platform-specific CI artifact and verify its manifest.

## Exact historical versions

A final tag is the immutable answer to “what exactly was this version?” Use
the platform-specific asset attached to that GitHub Release. Never substitute
a binary from `main` into a historical tagged installation.

## Compiled release artifacts

A final GitHub Release contains:

- one deterministic ZIP per supported platform;
- a combined SHA-256 manifest;
- source and qualification metadata;
- complete third-party notices and inventories.

Each installable GitHub platform tree contains `stata.toc`, `texpdf.pkg`, the
ado and help files, exactly one of `_texpdf_plugin_macosx.plugin`,
`_texpdf_plugin_unix.plugin`, or `_texpdf_plugin_windows.plugin`, project and third-party
notices, `BUILD_INFO.json`, and `CHECKSUMS.sha256`. A package is supported only
when its plugin was built from and qualified for the final tag.

The SSC submission contains all three native source plugin files. Its `.pkg`
uses Stata platform `g` directives to install exactly the matching source as
`_texpdf_plugin.plugin`, then uses an `h` directive to require that installed
plugin to load. A versioned `_texpdf_ssc_install.ado` marker lets the dispatcher
accept this generic destination only for a coherent SSC installation. GitHub
packages instead install one explicit platform filename. Mixed channels,
missing marker/plugin pairs, and stale generic files fail with an actionable
reinstallation error.

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
