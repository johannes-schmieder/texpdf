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
| `release_scope` | PASS | no | no | kind=final_release; version=0.1.0; source=be8f9aead479386d102a86ee8d2ad56780c66eb2; required_targets=['aarch64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc'] |
| `public_distribution` | PASS | no | no | public GitHub distribution is explicitly authorized in release scope |
| `ssc_distribution` | PASS | no | no | SSC distribution is explicitly authorized in release scope |
| `public_repository_security` | PASS | no | no | visibility=public; audit_tip=be8f9aead479386d102a86ee8d2ad56780c66eb2; scope_source=be8f9aead479386d102a86ee8d2ad56780c66eb2; sha_pinning=True; vulnerability_reporting=True |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=be8f9aead479386d102a86ee8d2ad56780c66eb2; plugin_bytes=49709840; Stata=MP 19; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=99091248; arm_runtime=True |
| `macos_intel_compatibility_slice` | PASS | no | no | source=be8f9aead479386d102a86ee8d2ad56780c66eb2; plugin_bytes=49377208; runtime=untested-by-policy |
| `macos_candidate_package` | PASS | no | no | version=0.1.0; zip_bytes=46559388; license_evidence=True; arm_runtime=true; intel_runtime=untested-by-policy |
| `linux_x86_64_runtime` | PASS | no | no | source=be8f9aead479386d102a86ee8d2ad56780c66eb2; glibc_max=2.28; package_version=0.1.0; Stata18_quick=True; Stata18_stress1000=True; Stata19_quick=True |
| `windows_x86_64_runtime` | FAIL | yes | yes | source equivalence diff mismatch; unexpected=[] |
| `required_target_source_coherence` | PASS | no | no | required_targets=['aarch64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc']; expected=be8f9aead479386d102a86ee8d2ad56780c66eb2; sources=['be8f9aead479386d102a86ee8d2ad56780c66eb2'] |
| `third_party_license_complete` | PASS | no | no | source=be8f9aead479386d102a86ee8d2ad56780c66eb2; resources=392; mapped=392; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `candidate_license_source_coherence` | PASS | no | no | candidate_source=be8f9aead479386d102a86ee8d2ad56780c66eb2; license_source=be8f9aead479386d102a86ee8d2ad56780c66eb2; ancestor=True; non_evidence_changes=[] |
| `macos_arm_memory_stress` | PASS | no | no | source=be8f9aead479386d102a86ee8d2ad56780c66eb2; iterations=1000; universal_run_id=33203299282; peak_rss_kib=74208; post_warmup_growth_kib=112; growth_ratio=1.0015115525804361 |

## Active candidate blockers

- `windows_x86_64_runtime`

## Public-release blockers

- `windows_x86_64_runtime`
