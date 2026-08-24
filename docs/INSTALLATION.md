# Installation design

Public installation is not enabled until the target and third-party license
gates pass. The final distribution uses two GitHub mechanisms for different
purposes.

## Human-downloadable release assets

A tagged GitHub Release contains:

- one deterministic ZIP per supported platform;
- a combined SHA-256 manifest;
- source and qualification metadata;
- complete third-party notices and inventories.

The ZIP is useful for archival verification and manual installation.

## Stata `net install` tree

Stata's package installer expects a directory containing `stata.toc`, a `.pkg`
file, and every file referenced by that package. A flat GitHub Release asset URL
is not treated as such a directory. The release workflow therefore publishes a
versioned static installation tree, for example:

```text
/v0.1.0/macos-arm64/
    stata.toc
    texpdf.pkg
    texpdf.ado
    texpdf.sthlp
    _texpdf_plugin.plugin
    LICENSE
    THIRD_PARTY_NOTICES.md
    CHECKSUMS.sha256
```

The intended installation command is then:

```stata
net install texpdf, from("https://<GitHub-hosted-site>/texpdf/v0.1.0/macos-arm64")
```

A separate directory is published for each platform so the installed package
still contains exactly one plugin file. The static tree may be served by GitHub
Pages or another GitHub-hosted static branch; it is generated from the same
checked release ZIP and checksum manifest and is not maintained manually.

## Platform selection

The first public documentation must not advertise one generic URL unless a
small installer can select a platform without weakening checksum verification.
Until such an installer is qualified, users choose the explicit platform URL:

- macOS Apple Silicon;
- macOS Intel/universal, when qualified;
- Windows x86-64, when qualified;
- Linux x86-64, when qualified.

## Offline operation

Internet access is needed only to install or update the package. After the ado,
help file, notices, and one native plugin are installed, compilation is fully
offline and performs no package retrieval.

## Verification

Every installation directory includes `CHECKSUMS.sha256`. The release notes
publish the same digests independently. CI performs a clean local `net install`
from the generated directory and compiles the release corpus before the files
are published.
