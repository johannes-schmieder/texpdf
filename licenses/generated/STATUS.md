# Third-party license audit status

- Source SHA: `b468ec0d4b934f9825ae4fb6711967a84ebce52f`
- Pipeline complete: **false**
- Release-license complete: **false**
- Embedded resources: 381
- Mapped resources: 381
- Ambiguous resources: 0
- Unmapped resources: 0
- Resources missing license metadata: 0
- Cargo packages: 369
- Cargo packages missing metadata: 0
- Rust packages without collected notice files: 0
- Native libraries without collected notice files: 0
- TeX resource notice tree complete: **true**
- TeX resource notice files: 9

## Pipeline stages

| Stage | Return code | Error tail |
|---|---:|---|
| `prepare_rust_toolchain` | 0 |  |
| `prepare_native_dependencies` | 2 | From github.com:pkgconf/pkgconf  * branch            4fc570f91d9d8d843ab32d2198a5c064538d8ffd -> FETCH_HEAD HEAD is now at 4fc570f pkgconf 2.5.1. libpkgconf/argvsplit.c:16:10: fatal error: 'libpkgconf/stdinc.h' file not found    16 \| #include <libpkgconf/stdinc.h>       \|          ^~~~~~~~~~~~~~~~~~~~~ 1 error generated. make: *** [libpkgconf/argvsplit.o] Error 1 |
| `tex_inventory` | 0 |  |
| `cargo_inventory` | 0 |  |
| `dependency_inventory` | 0 |  |
| `collect_license_texts` | 125 | skipped because a prerequisite stage failed |
| `collect_tex_license_notices` | 0 |  |
| `download_tlpdb` | 0 |  |

A successful workflow run means the audit produced durable evidence.
Public release remains fail-closed until every blocking count is zero
and `release_license_complete` is true in `STATUS.json`.
