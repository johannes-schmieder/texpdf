# Licensed Stata/Rust CI runner

`texpdf` uses one repository-level GitHub Actions runner on the Mac Studio.
The repository is public, but self-hosted jobs run only for trusted pushes and
explicit dispatches—never for pull requests or fork code. Workflow code
executes as the logged-in `johannes` macOS account and therefore has the same
practical authority as that account.

## Machine and tools

- Mac Studio `Mac14,14`, Apple M2 Ultra, arm64, 24 CPU cores, 192 GB RAM.
- macOS 26.5.2 build 25F84.
- Stata/MP 19 at `/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp`;
  Stata/MP 18 is retained under `/Applications/Stata 18/` for explicit lanes.
- Batch invocation: `stata-mp -q -b do FILE.do`.
- Rust stable 1.97.1 with rustfmt and Clippy; installed pinned toolchains also
  include 1.81.0 and 1.85.1.
- Apple clang/Xcode and TeX Live 2023 are installed.

Stata can return shell status zero after a Stata-language error. CI therefore
requires an explicit `stata.status` file and a profile-specific PASS marker.
Launch errors, timeouts, crashes, missing outputs, Stata errors, and Rust
errors are distinct receipt failures.

## Repository interface

The workflow is `.github/workflows/stata-ci.yml`. Pushes to `main` and
`codex/**` run the `quick` Stata/Mata infrastructure smoke plus Rust quick
checks. Manual profiles are `version`, `smoke`, `quick`, and `stress1000`. There is no
`pull_request` trigger and no hosted matrix.

Run locally from repository root with:

```sh
./ci/run_stata_ci.sh version
./ci/run_stata_ci.sh smoke
./ci/run_stata_ci.sh quick
./ci/run_rust_quick.sh
```

Each Stata run stages Git-tracked source into a fresh temporary tree. Release
qualification may additionally supply `TEXPDF_STATA_PLUGIN`,
`TEXPDF_STATA_PACKAGE_DIR`, and `TEXPDF_STATA_PACKAGE_MANIFEST`; the runner
copies those exact artifacts into the isolated tree and records their hashes.
Writable Stata system directories are isolated. `STATA_CI_LOCK_FILE` selects
the shared licensed-Stata lock and otherwise defaults under the host temporary
directory. On macOS, the runner places an isolated `open` shim first on `PATH`;
help examples can therefore verify `view` requests in
`viewer-invocations.txt` without launching a GUI application during CI. A
timeout terminates only the test process group. Sanitized evidence is copied to
`.ci/stata/run/`; the raw Stata startup stream is not uploaded.

The publisher commits immutable
`.ci/stata/results/<tested-sha>.json` receipts and updates
`.ci/stata/latest.json` only when the tested SHA remains the newest source
change. Receipt paths are excluded from triggers and commits use `[skip ci]`.

## Runner installation and operation

- Installation: `/Users/johannes/actions-runners/texpdf-stata`.
- Runner name: `macstudio-stata-mp18-texpdf`.
- Scope: public `johannes-schmieder/texpdf` repository, trusted events only.
- Workflow labels: `self-hosted`, `macOS`, `ARM64`, `stata-mp`, `texpdf`.
- Work directory: `_work` under the installation.
- LaunchAgent:
  `/Users/johannes/Library/LaunchAgents/actions.runner.johannes-schmieder-texpdf.macstudio-stata-mp18-texpdf.plist`.

Manage the service from the installation directory with `./svc.sh status`,
`./svc.sh stop`, and `./svc.sh start`. The user must remain logged into the
GUI session. AC system sleep is disabled; display sleep is harmless. The
runner makes outbound GitHub connections only and opens no inbound port.

The authoritative service check is:

```sh
launchctl print \
  "gui/$(id -u)/actions.runner.johannes-schmieder-texpdf.macstudio-stata-mp18-texpdf"
```

For an offline or stuck runner, inspect **Settings → Actions → Runners** and
the bounded LaunchAgent stdout/stderr logs under
`/Users/johannes/Library/Logs/actions.runner.johannes-schmieder-texpdf.macstudio-stata-mp18-texpdf/`.

To unregister, stop and uninstall the service, remove the runner in repository
settings or use a fresh short-lived removal token, and then delete the
installation only after confirming registration is gone. Re-registration uses
a new short-lived repository token and the recorded name, labels, and work
directory. Never store a token in this file or Git.

## Security assumptions

- Repository writers and workflow dispatchers are trusted; the repository is
  public but fork and pull-request execution on this runner remain disabled.
- `pull_request_target` is prohibited everywhere and all third-party actions
  are pinned to full commit SHAs by the static workflow-security check.
- Artifacts are restricted to `.ci/stata/run/` and synthetic fixtures.
- Home-directory content, credentials, license material, and confidential
  research data are never uploaded.
- Platform support is limited to the targets and versions in `release/scope.json`.

## Qualification record

- Initial repository-runner success: source
  `2ecbf988c3ee300829480da892509dbd1da4e383`, run `32697818280`, with
  `status=success`, `stata_status=success`, and `rust_status=success`.
- Deliberate Stata failure: source
  `f464880fa2e8aa0a174c746b5b6d8f2c2ee39da5`, run `32698195283`, with
  `failure_kind=stata_error`, `process_rc=0`, `stata_rc=9`, and Rust still
  successful. This proves why the explicit Stata status is authoritative.
- Restored branch success: source
  `e7361956689feca0aade4d92061eaf6dc347372f`, run `32698294950`, with both
  Stata and Rust successful.
- Green `main` verification of the finalized infrastructure source:
  `2ecbf988c3ee300829480da892509dbd1da4e383`, run `32698298249`.

The deliberate failure remains only in bootstrap-branch history and its
immutable receipt; it is not an ancestor of `main`.
