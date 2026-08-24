# texpdf release-readiness audit

macOS ARM64 implementation qualified: **true**
Public cross-platform v1 ready: **false**

| Check | Result | Release blocker | Detail |
|---|---|---|---|
| `package_file_texpdf.ado` | PASS | no | stata/texpdf.ado |
| `package_file_texpdf.sthlp` | PASS | no | stata/texpdf.sthlp |
| `package_file_texpdf.pkg` | PASS | no | stata/texpdf.pkg |
| `package_file_stata.toc` | PASS | no | stata/stata.toc |
| `cargo_lock` | PASS | no | Cargo.lock is committed |
| `target_registry` | PASS | no | target count=4 |
| `macos_arm_runtime` | PASS | no | source=640ed14c0fe0da09ef9a8cee195805f0ea9b39bf; plugin_bytes=49998208; Stata=MP 18; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | architectures=['arm64', 'x86_64']; universal_bytes=100051312; arm_runtime=True |
| `macos_intel_build` | PASS | no | source=32bceb84df47a1c955c10cf75cb60a9d0fbb8d96; plugin_bytes=50043664 |
| `macos_intel_runtime` | FAIL | yes | Intel slice built, inspected, and packaged into an ARM-tested universal plugin; Intel Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_build` | FAIL | no | native build and Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_runtime` | FAIL | yes | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_build` | FAIL | no | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_runtime` | FAIL | yes | native build and Stata runtime qualification pending |
| `third_party_license_complete` | FAIL | yes | source=dc005e728971607a17a181f18ec2a2a06e944c6d; resources=556; mapped=406; ambiguous=8; unmapped=5; missing_license=137; missing_rust_texts=31; missing_native_texts=0 |
| `macos_arm_memory_stress` | FAIL | yes | source=2906be9e4628cd44197e5d6310a810b74f2aca7e; iterations=1000; peak_rss_kib=1249968; post_warmup_growth_kib=819480; growth_ratio=3.163449353721382 |

## Active public-release blockers

- `macos_intel_runtime`
- `x86_64-pc-windows-msvc_runtime`
- `x86_64-unknown-linux-gnu_runtime`
- `third_party_license_complete`
- `macos_arm_memory_stress`
