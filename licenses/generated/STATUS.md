# Third-party license audit status

- Source SHA: `3dc6fe61fb0ef1380bdf0c90973d123e433cbe23`
- Pipeline complete: **false**
- Release-license complete: **false**
- Embedded resources: unavailable
- Mapped resources: unavailable
- Ambiguous resources: unavailable
- Unmapped resources: unavailable
- Resources missing license metadata: unavailable
- Cargo packages: 448
- Cargo packages missing metadata: 0
- Rust packages without collected notice files: 37
- Native libraries without collected notice files: 0

## Pipeline stages

| Stage | Return code | Error tail |
|---|---:|---|
| `prepare_rust_toolchain` | 0 |  |
| `prepare_native_dependencies` | 0 |  |
| `tex_inventory` | 1 | Traceback (most recent call last):   File "/Users/johannes/actions-runners/texpdf-stata/_work/texpdf/texpdf/tools/generate_license_inventory.py", line 401, in <module>     raise SystemExit(main())   File "/Users/johannes/actions-runners/texpdf-stata/_work/texpdf/texpdf/tools/generate_license_inventory.py", line 382, in main     load_overrides(args.overrides),   File "/Users/johannes/actions-runners/texpdf-stata/_work/texpdf/texpdf/tools/generate_license_inventory.py", line 172, in load_overrides     import tomllib ModuleNotFoundError: No module named 'tomllib' |
| `cargo_inventory` | 0 |  |
| `dependency_inventory` | 0 |  |
| `collect_license_texts` | 1 |  |
| `download_tlpdb` | 0 |  |

A successful workflow run means the audit produced durable evidence.
Public release remains fail-closed until every blocking count is zero
and `release_license_complete` is true in `STATUS.json`.
