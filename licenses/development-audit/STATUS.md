# Third-party license audit status

- Source SHA: `d0cdc9fe06dfe9795840ab516bc5c98b1415c01a`
- Pipeline complete: **true**
- Release-license complete: **true**
- Embedded resources: 392
- Mapped resources: 392
- Ambiguous resources: 0
- Unmapped resources: 0
- Resources missing license metadata: 0
- Cargo packages: 369
- Cargo packages missing metadata: 0
- Rust packages without collected notice files: 0
- Native libraries without collected notice files: 0
- TeX resource notice tree complete: **true**
- TeX resource notice files: 10

## Pipeline stages

| Stage | Return code | Error tail |
|---|---:|---|
| `prepare_rust_toolchain` | 0 |  |
| `prepare_native_dependencies` | 0 |  |
| `tex_inventory` | 0 |  |
| `cargo_inventory` | 0 |  |
| `dependency_inventory` | 0 |  |
| `collect_license_texts` | 0 |  |
| `collect_tex_license_notices` | 0 |  |
| `download_tlpdb` | 0 |  |

A successful workflow run means the audit produced durable evidence.
Public release remains fail-closed until every blocking count is zero
and `release_license_complete` is true in `STATUS.json`.
