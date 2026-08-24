# texpdf release-readiness audit

macOS ARM64 implementation qualified: **true**
Private macOS universal candidate ready: **true**
Public cross-platform v1 ready: **false**

| Check | Result | Candidate blocker | Public blocker | Detail |
|---|---|---|---|---|
| `package_file_texpdf.ado` | PASS | no | no | stata/texpdf.ado |
| `package_file_texpdf.sthlp` | PASS | no | no | stata/texpdf.sthlp |
| `package_file_texpdf.pkg` | PASS | no | no | stata/texpdf.pkg |
| `package_file_stata.toc` | PASS | no | no | stata/stata.toc |
| `cargo_lock` | PASS | no | no | Cargo.lock is committed |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=5960a7b476fafe9800a574eede23be7e3ac5c30d; plugin_bytes=49429136; Stata=MP 18; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=98532016; arm_runtime=True |
| `macos_intel_build` | PASS | no | no | source=68d7c8b2f4de569fad5fb583978cd13efb4c5dae; plugin_bytes=49098680 |
| `macos_intel_runtime` | PASS | no | no | qualified in an actual x86_64 Stata process under Rosetta; runtime_record=valid; exact receipt profile=quick rust_mode=repository-engine |
| `private_candidate_package` | PASS | no | no | version=0.1.0-rc.1; zip_bytes=45982321; license_evidence=True; both_runtimes=True |
| `x86_64-pc-windows-msvc_build` | FAIL | no | no | native build and Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_runtime` | FAIL | no | yes | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_build` | FAIL | no | no | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_runtime` | FAIL | no | yes | native build and Stata runtime qualification pending |
| `third_party_license_complete` | PASS | no | no | source=68d7c8b2f4de569fad5fb583978cd13efb4c5dae; resources=381; mapped=381; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `macos_arm_memory_stress` | PASS | no | no | source=e67de2cdf6a1cc7fff4aeb82c3a116a2b95e14a1; iterations=1000; peak_rss_kib=72304; post_warmup_growth_kib=16; growth_ratio=1.0002213368747233 |
| `release_scope` | PASS | no | no | kind=private_release_candidate; version=0.1.0-rc.1; required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin'] |
| `public_distribution` | FAIL | no | yes | public repository and net-install publication are deferred by owner decision |

## Active private-candidate blockers

None.

## Deferred public-release blockers

- `x86_64-pc-windows-msvc_runtime`
- `x86_64-unknown-linux-gnu_runtime`
- `public_distribution`
