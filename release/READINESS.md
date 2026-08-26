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
| `release_scope` | PASS | no | no | kind=public_release_candidate; version=0.1.0-rc2; source=11a07ef66f69db83e2a1317a900a1bcccf3b29ab; required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc'] |
| `public_distribution` | PASS | no | no | public GitHub distribution is explicitly authorized in release scope |
| `ssc_distribution` | PASS | no | no | SSC distribution is explicitly authorized in release scope |
| `public_repository_security` | FAIL | yes | yes | missing release/publication.json |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; plugin_bytes=49429136; Stata=MP 18; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=98532016; arm_runtime=True |
| `macos_intel_build` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; plugin_bytes=49098680 |
| `macos_intel_runtime` | PASS | no | no | qualified in an actual x86_64 Stata process under Rosetta; runtime_record=valid; exact receipt profile=quick rust_mode=repository-engine |
| `macos_candidate_package` | FAIL | yes | yes | version=0.1.0-rc.2; zip_bytes=45982571; license_evidence=True; both_runtimes=True |
| `linux_x86_64_runtime` | FAIL | yes | yes | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; glibc_max=2.28; package_version=0.1.0-rc.2; Stata18_quick=True; Stata18_stress1000=True; Stata19_quick=True |
| `windows_x86_64_runtime` | FAIL | yes | yes | missing release/windows-x86_64.json |
| `required_target_source_coherence` | FAIL | yes | yes | required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc']; expected=11a07ef66f69db83e2a1317a900a1bcccf3b29ab; sources=['', '7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8'] |
| `third_party_license_complete` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; resources=381; mapped=381; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `candidate_license_source_coherence` | FAIL | yes | yes | candidate_source=missing; license_source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; ancestor=False; non_evidence_changes=[] |
| `macos_arm_memory_stress` | PASS | no | no | source=7aa7b16aca8afc75ebfd6aa27a0aa04ab04a47d8; iterations=1000; peak_rss_kib=72304; post_warmup_growth_kib=32; growth_ratio=1.0004427717511624 |

## Active candidate blockers

- `public_repository_security`
- `macos_candidate_package`
- `linux_x86_64_runtime`
- `windows_x86_64_runtime`
- `required_target_source_coherence`
- `candidate_license_source_coherence`

## Public-release blockers

- `public_repository_security`
- `macos_candidate_package`
- `linux_x86_64_runtime`
- `windows_x86_64_runtime`
- `required_target_source_coherence`
- `candidate_license_source_coherence`
