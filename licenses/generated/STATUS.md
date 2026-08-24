# Third-party license audit status

- Source SHA: `471b4ea93d24d664ba82c5ab6c034c2606702ec7`
- Pipeline complete: **false**
- Release-license complete: **false**
- Embedded resources: 556
- Mapped resources: 358
- Ambiguous resources: 56
- Unmapped resources: 5
- Resources missing license metadata: 137
- Cargo packages: 448
- Cargo packages missing metadata: 0
- Rust packages without collected notice files: 37
- Native libraries without collected notice files: 0

## Pipeline stages

| Stage | Return code | Error tail |
|---|---:|---|
| `prepare_rust_toolchain` | 0 |  |
| `prepare_native_dependencies` | 0 |  |
| `tex_inventory` | 1 |  |
| `cargo_inventory` | 0 |  |
| `dependency_inventory` | 0 |  |
| `collect_license_texts` | 1 |  |
| `download_tlpdb` | 0 |  |

A successful workflow run means the audit produced durable evidence.
Public release remains fail-closed until every blocking count is zero
and `release_license_complete` is true in `STATUS.json`.
