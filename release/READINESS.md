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
| `macos_arm_runtime` | PASS | no | source=a644181b33109ea0eb594f2aefa1895e94b7bd11; plugin_bytes=49997392; Stata=MP 18; exact receipt profile=quick rust_mode=repository-engine |
| `macos_universal_build` | PASS | no | architectures=['arm64', 'x86_64']; universal_bytes=100051312; arm_runtime=True |
| `macos_intel_build` | PASS | no | source=32bceb84df47a1c955c10cf75cb60a9d0fbb8d96; plugin_bytes=50043664 |
| `macos_intel_runtime` | FAIL | yes | Intel slice built, inspected, and packaged into an ARM-tested universal plugin; Intel Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_build` | FAIL | no | native build and Stata runtime qualification pending |
| `x86_64-pc-windows-msvc_runtime` | FAIL | yes | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_build` | FAIL | no | native build and Stata runtime qualification pending |
| `x86_64-unknown-linux-gnu_runtime` | FAIL | yes | native build and Stata runtime qualification pending |
| `third_party_license_complete` | FAIL | yes | missing source-bound audit status licenses/generated/STATUS.json |
| `macos_arm_memory_stress` | FAIL | yes | missing permanent qualification record release/memory-stress-macos-arm64.json |

## Active public-release blockers

- `macos_intel_runtime`
- `x86_64-pc-windows-msvc_runtime`
- `x86_64-unknown-linux-gnu_runtime`
- `third_party_license_complete`
- `macos_arm_memory_stress`
