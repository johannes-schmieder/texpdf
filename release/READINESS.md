# texpdf release-readiness audit

macOS ARM64 implementation qualified: **true**
Private required-target candidate ready: **false**
Public cross-platform v1 ready: **false**

| Check | Result | Candidate blocker | Public blocker | Detail |
|---|---|---|---|---|
| `package_file_texpdf.ado` | PASS | no | no | stata/texpdf.ado |
| `package_file_texpdf.sthlp` | PASS | no | no | stata/texpdf.sthlp |
| `package_file_texpdf.pkg` | PASS | no | no | stata/texpdf.pkg |
| `package_file_stata.toc` | PASS | no | no | stata/stata.toc |
| `cargo_lock` | PASS | no | no | Cargo.lock is committed |
| `release_scope` | PASS | no | no | kind=private_release_candidate; version=0.1.0-rc.2; source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu'] |
| `public_distribution` | FAIL | no | yes | public repository and net-install publication are deferred by owner decision |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; plugin_bytes=49429136; Stata=MP 18; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=98532016; arm_runtime=True |
| `macos_intel_build` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; plugin_bytes=49098680 |
| `macos_intel_runtime` | PASS | no | no | qualified in an actual x86_64 Stata process under Rosetta; runtime_record=valid; exact receipt profile=quick rust_mode=repository-engine |
| `private_candidate_package` | FAIL | yes | yes | version=0.1.0-rc.2; zip_bytes=45982571; license_evidence=True; both_runtimes=True |
| `linux_x86_64_runtime` | FAIL | yes | yes | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; glibc_max=2.28; package_version=0.1.0-rc.2; Stata18_quick=True; Stata18_stress1000=True; Stata19_quick=True |
| `x86_64-pc-windows-msvc_build` | FAIL | no | no | native build and Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_runtime` | FAIL | no | yes | native build and Stata runtime qualification pending |
| `required_target_source_coherence` | PASS | no | no | required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu']; expected=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; sources=['7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8'] |
| `third_party_license_complete` | FAIL | yes | yes | source=21cf28493624191d52488146b914b8d26cc5291d; resources=392; mapped=392; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `candidate_license_source_coherence` | FAIL | yes | yes | candidate_source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; license_source=21cf28493624191d52488146b914b8d26cc5291d; ancestor=False; non_evidence_changes=[] |
| `macos_arm_memory_stress` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; iterations=1000; peak_rss_kib=72304; post_warmup_growth_kib=32; growth_ratio=1.0004427717511624 |

## Active private-candidate blockers

- `private_candidate_package`
- `linux_x86_64_runtime`
- `third_party_license_complete`
- `candidate_license_source_coherence`

## Deferred public-release blockers

- `public_distribution`
- `private_candidate_package`
- `linux_x86_64_runtime`
- `x86_64-pc-windows-msvc_runtime`
- `third_party_license_complete`
- `candidate_license_source_coherence`
