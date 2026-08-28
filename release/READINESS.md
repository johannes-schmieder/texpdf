# texpdf release-readiness audit

macOS ARM64 implementation qualified: **true**
Required-target candidate ready: **true**
Public cross-platform release ready: **true**

| Check | Result | Candidate blocker | Public blocker | Detail |
|---|---|---|---|---|
| `package_file_texpdf.ado` | PASS | no | no | stata/texpdf.ado |
| `package_file_texpdf.sthlp` | PASS | no | no | stata/texpdf.sthlp |
| `package_file_texpdf_run.ado` | PASS | no | no | stata/texpdf_run.ado |
| `package_file_texpdf.pkg` | PASS | no | no | stata/texpdf.pkg |
| `package_file_stata.toc` | PASS | no | no | stata/stata.toc |
| `cargo_lock` | PASS | no | no | Cargo.lock is committed |
| `release_scope` | PASS | no | no | kind=public_release_candidate; version=0.1.0-rc2; source=366f16406773be5494a61e0badd55d0d1891e3c4; required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc'] |
| `public_distribution` | PASS | no | no | public GitHub distribution is explicitly authorized in release scope |
| `ssc_distribution` | PASS | no | no | SSC distribution is explicitly authorized in release scope |
| `public_repository_security` | PASS | no | no | visibility=public; audit_tip=366f16406773be5494a61e0badd55d0d1891e3c4; scope_source=366f16406773be5494a61e0badd55d0d1891e3c4; sha_pinning=True; vulnerability_reporting=True |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=366f16406773be5494a61e0badd55d0d1891e3c4; plugin_bytes=49709840; Stata=MP 19; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=99091248; arm_runtime=True |
| `macos_intel_build` | PASS | no | no | source=366f16406773be5494a61e0badd55d0d1891e3c4; plugin_bytes=49377208 |
| `macos_intel_runtime` | PASS | no | no | qualified in an actual x86_64 Stata process under Rosetta; runtime_record=valid; exact receipt profile=quick rust_mode=repository-engine |
| `macos_candidate_package` | PASS | no | no | version=0.1.0-rc2; zip_bytes=46559667; license_evidence=True; both_runtimes=True |
| `linux_x86_64_runtime` | PASS | no | no | source=366f16406773be5494a61e0badd55d0d1891e3c4; glibc_max=2.28; package_version=0.1.0-rc2; Stata18_quick=True; Stata18_stress1000=True; Stata19_quick=True |
| `windows_x86_64_runtime` | PASS | no | no | source=366f16406773be5494a61e0badd55d0d1891e3c4; package_version=0.1.0-rc2; static_crt=True; Stata19_quick=True; Stata19_stress1000=True |
| `required_target_source_coherence` | PASS | no | no | required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-unknown-linux-gnu', 'x86_64-pc-windows-msvc']; expected=366f16406773be5494a61e0badd55d0d1891e3c4; sources=['366f16406773be5494a61e0badd55d0d1891e3c4'] |
| `third_party_license_complete` | PASS | no | no | source=366f16406773be5494a61e0badd55d0d1891e3c4; resources=392; mapped=392; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `candidate_license_source_coherence` | PASS | no | no | candidate_source=366f16406773be5494a61e0badd55d0d1891e3c4; license_source=366f16406773be5494a61e0badd55d0d1891e3c4; ancestor=True; non_evidence_changes=[] |
| `macos_arm_memory_stress` | PASS | no | no | source=366f16406773be5494a61e0badd55d0d1891e3c4; iterations=1000; peak_rss_kib=73728; post_warmup_growth_kib=16; growth_ratio=1.0002170609941394 |

## Active candidate blockers

None.

## Public-release blockers

None.
