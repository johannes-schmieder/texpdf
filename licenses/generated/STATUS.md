# Third-party license audit status

- Source SHA: `9d956b07b7577613b70f5f7efa9b322bdd74310f`
- Pipeline complete: **false**
- Release-license complete: **false**
- Embedded resources: unavailable
- Mapped resources: unavailable
- Ambiguous resources: unavailable
- Unmapped resources: unavailable
- Resources missing license metadata: unavailable
- Cargo packages: 448
- Cargo packages missing metadata: 0
- Rust packages without collected notice files: 40
- Native libraries without collected notice files: 0

## Pipeline stages

| Stage | Return code | Error tail |
|---|---:|---|
| `prepare_rust_toolchain` | 0 |  |
| `prepare_native_dependencies` | 0 |  |
| `tex_inventory` | 1 | rate_license_inventory.py", line 401, in <module>     raise SystemExit(main())   File "/Users/johannes/actions-runners/texpdf-stata/_work/texpdf/texpdf/tools/generate_license_inventory.py", line 378, in main     manifest = json.loads(args.manifest.read_text(encoding="utf-8"))   File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1256, in read_text     with self.open(mode='r', encoding=encoding, errors=errors) as f:   File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1242, in open     return io.open(self, mode, buffering, encoding, errors, newline,   File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1110, in _opener     return self._accessor.open(self, flags, mode) FileNotFoundError: [Errno 2] No such file or directory: 'bundle/curated-manifest.json' |
| `cargo_inventory` | 0 |  |
| `dependency_inventory` | 0 |  |
| `collect_license_texts` | 1 |  |
| `download_tlpdb` | 0 |  |

A successful workflow run means the audit produced durable evidence.
Public release remains fail-closed until every blocking count is zero
and `release_license_complete` is true in `STATUS.json`.
