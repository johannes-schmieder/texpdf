param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [Parameter(Mandatory = $true)][string]$SourceSha,
    [Parameter(Mandatory = $true)][string]$StataExecutable,
    [Parameter(Mandatory = $true)][string]$PythonExecutable,
    [Parameter(Mandatory = $true)][string]$PackageDirectory,
    [Parameter(Mandatory = $true)][string]$PackageZip,
    [Parameter(Mandatory = $true)][string]$PackageManifest,
    [Parameter(Mandatory = $true)][string]$Helper,
    [Parameter(Mandatory = $true)][string]$BinaryPolicy,
    [Parameter(Mandatory = $true)][string]$HostedManifest,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$Repository = (Resolve-Path -LiteralPath $Repository).Path
$PackageDirectory = (Resolve-Path -LiteralPath $PackageDirectory).Path
$PackageZip = (Resolve-Path -LiteralPath $PackageZip).Path
$PackageManifest = (Resolve-Path -LiteralPath $PackageManifest).Path
$Helper = (Resolve-Path -LiteralPath $Helper).Path
$BinaryPolicy = (Resolve-Path -LiteralPath $BinaryPolicy).Path
$HostedManifest = (Resolve-Path -LiteralPath $HostedManifest).Path
$StataExecutable = (Resolve-Path -LiteralPath $StataExecutable).Path
$PythonExecutable = (Resolve-Path -LiteralPath $PythonExecutable).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

Set-Location $Repository
$head = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $SourceSha) {
    throw "Windows qualification source mismatch: expected $SourceSha, found $head"
}
if ((& git status --porcelain).Count -ne 0) {
    throw 'Windows qualification repository is not clean'
}

$manifest = Get-Content -Raw -LiteralPath $PackageManifest | ConvertFrom-Json
if ($manifest.target -ne 'x86_64-pc-windows-msvc' -or
        $manifest.installed_plugin -ne '_texpdf_plugin_windows.plugin') {
    throw 'Windows package manifest target/plugin mismatch'
}
$plugin = Join-Path $PackageDirectory '_texpdf_plugin_windows.plugin'
if (-not (Test-Path -LiteralPath $plugin)) { throw 'Windows package plugin is missing' }
$actualPluginHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $plugin).Hash.ToLowerInvariant()
if ($actualPluginHash -ne $manifest.plugin_sha256) { throw 'Windows package plugin hash mismatch' }
$actualZipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PackageZip).Hash.ToLowerInvariant()
if ($actualZipHash -ne $manifest.package_zip_sha256) { throw 'Windows package ZIP hash mismatch' }

$receipts = Join-Path $OutputDirectory 'receipts'
New-Item -ItemType Directory -Force -Path $receipts | Out-Null
$env:STATA_BIN = $StataExecutable
$env:GITHUB_SHA = $SourceSha
$env:GITHUB_REPOSITORY = 'johannes-schmieder/texpdf'
$env:GITHUB_REF = 'refs/heads/main'
$env:GITHUB_RUN_ID = 'windows-ec2-runtime'
$env:GITHUB_RUN_ATTEMPT = '1'
$env:RUNNER_NAME = 'windows-stata-mp19-release'
$env:TEXPDF_STATA_PACKAGE_DIR = $PackageDirectory
$env:TEXPDF_STATA_PACKAGE_MANIFEST = $PackageManifest
$env:TEXPDF_STATA_PLUGIN = $plugin
$env:TEXPDF_CORPUS_OUTPUT = Join-Path $OutputDirectory 'corpus-pdfs'
$env:STATA_CI_KEEP_TEMP = '1'
$cleanPathParts = @($env:Path -split ';' | Where-Object {
    $entry = $_
    $entry -and -not (@('pdflatex.exe', 'latex.exe', 'tectonic.exe') | Where-Object {
        Test-Path -LiteralPath (Join-Path $entry $_)
    })
})
$env:Path = $cleanPathParts -join ';'

$texCommands = @('pdflatex.exe', 'latex.exe', 'tectonic.exe') | Where-Object {
    Get-Command $_ -ErrorAction SilentlyContinue
}
if ($texCommands.Count -ne 0) { throw "system TeX remains on PATH: $texCommands" }

foreach ($profile in @('quick', 'stress1000')) {
    $profileDirectory = Join-Path $receipts ("stata-19-" + $profile)
    $env:TEXPDF_STATA_ARTIFACT_DIR = $profileDirectory
    $env:RUNNER_TEMP = Join-Path $OutputDirectory ("work-" + $profile)
    if ($profile -eq 'stress1000') { $env:TEXPDF_STRESS_ITERATIONS = '1000' }
    & $PythonExecutable ci\run_stata_ci.py $profile
    if ($LASTEXITCODE -ne 0) { throw "licensed Windows Stata profile failed: $profile" }
    & $PythonExecutable ci\check_stata_receipt.py (Join-Path $profileDirectory 'receipt.json') `
        --expect-tested-sha $SourceSha --expect-profile $profile --require-success
    if ($LASTEXITCODE -ne 0) { throw "Windows Stata receipt validation failed: $profile" }
}

& $PythonExecutable ci\windows\write_build_receipt.py `
    --source-sha $SourceSha --plugin $plugin --helper $Helper --package $PackageZip `
    --package-manifest $PackageManifest --binary-policy $BinaryPolicy `
    --hosted-manifest $HostedManifest --output (Join-Path $receipts 'windows-build.json')
if ($LASTEXITCODE -ne 0) { throw 'Windows build receipt validation failed' }

$environment = [ordered]@{
    schema_version = 1
    status = 'success'
    source_sha = $SourceSha
    system_tex_required = $false
    system_tex_commands_on_path = @()
    operating_system = (Get-CimInstance Win32_OperatingSystem).Caption
    architecture = $env:PROCESSOR_ARCHITECTURE
    stata_version = '19'
    stata_edition = 'MP'
}
$environment | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 `
    (Join-Path $receipts 'windows-environment.json')
Write-Output "TEXPDF_WINDOWS_QUALIFICATION_PASS source=$SourceSha"
