# texpdf release-readiness audit

macOS ARM64 implementation qualified: **true**
Private macOS universal candidate ready: **false**
Public cross-platform v1 ready: **false**

| Check | Result | Candidate blocker | Public blocker | Detail |
|---|---|---|---|---|
| `package_file_texpdf.ado` | PASS | no | no | stata/texpdf.ado |
| `package_file_texpdf.sthlp` | PASS | no | no | stata/texpdf.sthlp |
| `package_file_texpdf.pkg` | PASS | no | no | stata/texpdf.pkg |
| `package_file_stata.toc` | PASS | no | no | stata/stata.toc |
| `cargo_lock` | PASS | no | no | Cargo.lock is committed |
| `target_registry` | PASS | no | no | target count=4 |
| `macos_arm_runtime` | PASS | no | no | source=5ba3a83e098dcf7eb47c7b0db92b28ac46a9297b; plugin_bytes=51146384; Stata=MP 18; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | no | architectures=['arm64', 'x86_64']; universal_bytes=98532032; arm_runtime=True |
| `macos_intel_build` | PASS | no | no | source=d9be7615bd69b260b5841730d51d9a9ee03958f0; plugin_bytes=49098688 |
| `macos_intel_runtime` | FAIL | yes | yes | Intel slice built, inspected, and packaged into an ARM-tested universal plugin; Intel Stata runtime qualification pending; runtime_record=missing/invalid; qualified source SHA is missing or malformed |
| `x86_64-pc-windows-msvc_build` | FAIL | no | no | native build and Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_runtime` | FAIL | no | yes | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_build` | FAIL | no | no | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_runtime` | FAIL | no | yes | native build and Stata runtime qualification pending |
| `third_party_license_complete` | PASS | no | no | source=d9be7615bd69b260b5841730d51d9a9ee03958f0; resources=381; mapped=381; ambiguous=0; unmapped=0; missing_license=0; missing_rust_texts=0; missing_native_texts=0 |
| `macos_arm_memory_stress` | FAIL | yes | yes | source=2906be9e4628cd44197e5d6310a810b74f2aca7e; iterations=1000; peak_rss_kib=1249968; post_warmup_growth_kib=819480; growth_ratio=3.163449353721382 |
| `release_scope` | PASS | no | no | kind=private_release_candidate; version=0.1.0-rc.1; required_targets=['aarch64-apple-darwin', 'x86_64-apple-darwin'] |
| `public_distribution` | FAIL | no | yes | public repository and net-install publication are deferred by owner decision |

## Active private-candidate blockers

- `macos_intel_runtime`
- `macos_arm_memory_stress`

## Deferred public-release blockers

- `macos_intel_runtime`
- `x86_64-pc-windows-msvc_runtime`
- `x86_64-unknown-linux-gnu_runtime`
- `macos_arm_memory_stress`
- `public_distribution`
