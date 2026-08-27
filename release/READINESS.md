# texpdf release-readiness audit

macOS ARM64 implementation qualified: **true**
Required-target candidate ready: **false**
Public cross-platform release ready: **false**

| Check | Result | Candidate blocker | Public blocker | Detail |
|---|---|---|---|---|
| `package_file_texpdf.ado` | PASS | no | no | stata/texpdf.ado |
| `package_file_texpdf.sthlp` | PASS | no | no | stata/texpdf.sthlp |
| `package_file_texpdf_run.ado` | PASS | no | no | stata/texpdf_run.ado |
| `package_file_texpdf.pkg` | PASS | no | no | stata/texpdf.pkg |
| `package_file_stata.toc` | PASS | no | no | stata/stata.toc |
| `cargo_lock` | PASS | no | no | Cargo.lock is committed |
| `release_scope` | PASS | no | no | kind=public_release_candidate; version=0.1.0-rc2; source=ba7345243e3a3514f9080a9c26150708d7a2aabb; required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc'] |
| `public_distribution` | PASS | no | no | public GitHub distribution is explicitly authorized in release scope |
| `ssc_distribution` | PASS | no | no | SSC distribution is explicitly authorized in release scope |
| `public_repository_security` | PASS | no | no | visibility=public; audit_tip=ba7345243e3a3514f9080a9c26150708d7a2aabb; scope_source=ba7345243e3a3514f9080a9c26150708d7a2aabb; sha_pinning=True; vulnerability_reporting=True |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=719421d122617317119372534216fadf791f9842; plugin_bytes=49709840; Stata=MP 19; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=99091248; arm_runtime=True |
| `macos_intel_build` | PASS | no | no | source=ba7345243e3a3514f9080a9c26150708d7a2aabb; plugin_bytes=49377208 |
| `macos_intel_runtime` | FAIL | yes | yes | Intel slice built, inspected, and packaged into an ARM-tested universal plugin; Intel Stata runtime qualification pending; runtime_record=missing/invalid; qualified source SHA is missing or malformed |
| `macos_candidate_package` | FAIL | yes | yes | version=0.1.0-rc2; zip_bytes=46559664; license_evidence=True; both_runtimes=None |
| `linux_x86_64_runtime` | FAIL | yes | yes | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; glibc_max=2.28; package_version=0.1.0-rc.2; Stata18_quick=True; Stata18_stress1000=True; Stata19_quick=True |
| `windows_x86_64_runtime` | FAIL | yes | yes | missing release/windows-x86_64.json |
| `required_target_source_coherence` | FAIL | yes | yes | required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc']; expected=ba7345243e3a3514f9080a9c26150708d7a2aabb; sources=['', '719421d122617317119372534216fadf791f9842', '7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8'] |
| `third_party_license_complete` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; resources=381; mapped=381; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `candidate_license_source_coherence` | FAIL | yes | yes | candidate_source=missing; license_source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; ancestor=False; non_evidence_changes=[] |
| `macos_arm_memory_stress` | FAIL | yes | yes | source=ba7345243e3a3514f9080a9c26150708d7a2aabb; iterations=1000; peak_rss_kib=74208; post_warmup_growth_kib=80; growth_ratio=1.0010792143319662 |

## Active candidate blockers

- `macos_intel_runtime`
- `macos_candidate_package`
- `linux_x86_64_runtime`
- `windows_x86_64_runtime`
- `required_target_source_coherence`
- `candidate_license_source_coherence`
- `macos_arm_memory_stress`

## Public-release blockers

- `macos_intel_runtime`
- `macos_candidate_package`
- `linux_x86_64_runtime`
- `windows_x86_64_runtime`
- `required_target_source_coherence`
- `candidate_license_source_coherence`
- `macos_arm_memory_stress`
