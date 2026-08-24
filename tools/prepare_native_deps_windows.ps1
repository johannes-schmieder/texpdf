param(
    [string]$Target = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($Target -ne "x86_64-pc-windows-msvc") {
    throw "Unsupported Windows Rust target: $Target"
}

$VcpkgRevision = "a62ce77d56ee07513b4b67de1ec2daeaebfae51a"
$VcpkgShort = $VcpkgRevision.Substring(0, 12)
$Base = if ($env:TEXPDF_VCPKG_ROOT) {
    $env:TEXPDF_VCPKG_ROOT
} elseif ($env:RUNNER_TEMP) {
    Join-Path $env:RUNNER_TEMP "texpdf-vcpkg-$VcpkgShort"
} else {
    Join-Path $env:TEMP "texpdf-vcpkg-$VcpkgShort"
}
$BinaryCache = if ($env:TEXPDF_VCPKG_BINARY_CACHE) {
    $env:TEXPDF_VCPKG_BINARY_CACHE
} elseif ($env:RUNNER_TEMP) {
    Join-Path $env:RUNNER_TEMP "texpdf-vcpkg-binary-cache"
} else {
    Join-Path $env:TEMP "texpdf-vcpkg-binary-cache"
}
$Triplet = "x64-windows-static-release"
$RevisionFile = Join-Path $Base ".texpdf-revision"
$VcpkgExe = Join-Path $Base "vcpkg.exe"

New-Item -ItemType Directory -Force -Path $BinaryCache | Out-Null
$CurrentRevision = if (Test-Path $RevisionFile) {
    (Get-Content -Raw $RevisionFile).Trim()
} else {
    ""
}
if (-not (Test-Path $VcpkgExe) -or $CurrentRevision -ne $VcpkgRevision) {
    if (Test-Path $Base) {
        Remove-Item -Recurse -Force $Base
    }
    New-Item -ItemType Directory -Force -Path $Base | Out-Null
    git -C $Base init -q
    git -C $Base remote add origin https://github.com/microsoft/vcpkg.git
    git -C $Base fetch --depth 1 origin $VcpkgRevision
    git -C $Base checkout --detach FETCH_HEAD
    $Actual = (git -C $Base rev-parse HEAD).Trim()
    if ($Actual -ne $VcpkgRevision) {
        throw "Pinned vcpkg checkout mismatch: $Actual"
    }
    & (Join-Path $Base "bootstrap-vcpkg.bat") -disableMetrics
    Set-Content -NoNewline -Encoding ASCII -Path $RevisionFile -Value $VcpkgRevision
}

$env:VCPKG_ROOT = $Base
$env:VCPKGRS_TRIPLET = $Triplet
$env:VCPKG_DEFAULT_BINARY_CACHE = $BinaryCache
$env:TECTONIC_DEP_BACKEND = "vcpkg"

$StampDirectory = Join-Path $Base "installed\$Triplet"
$Stamp = Join-Path $StampDirectory ".texpdf-fontconfig-freetype-harfbuzz-graphite2-icu-libpng-zlib"
if (-not (Test-Path $Stamp)) {
    & $VcpkgExe install --triplet $Triplet `
        fontconfig `
        freetype `
        "harfbuzz[graphite2]" `
        icu `
        libpng `
        zlib
    New-Item -ItemType Directory -Force -Path $StampDirectory | Out-Null
    Set-Content -NoNewline -Encoding ASCII -Path $Stamp -Value $VcpkgRevision
}

if ($env:GITHUB_ENV) {
    @(
        "VCPKG_ROOT=$Base",
        "VCPKGRS_TRIPLET=$Triplet",
        "VCPKG_DEFAULT_BINARY_CACHE=$BinaryCache",
        "TECTONIC_DEP_BACKEND=vcpkg"
    ) | Add-Content -Encoding UTF8 $env:GITHUB_ENV
}

Write-Output "TEXPDF_WINDOWS_NATIVE_DEPS_READY target=$Target triplet=$Triplet root=$Base"
