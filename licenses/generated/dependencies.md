# Generated release dependency inventory

Release root: `texpdf-stata`  
Release target: `aarch64-apple-darwin`

This inventory follows the normal/build dependency closure of the
released plugin. It excludes dev/test-only and unrelated workspace crates.
It does not replace corresponding license texts or the TeX resource audit.

## Rust packages

| Package | Version | Declared license | Repository |
|---|---:|---|---|
| `bitflags` | `2.13.1` | `MIT OR Apache-2.0` | https://github.com/bitflags/bitflags |
| `block-buffer` | `0.10.4` | `MIT OR Apache-2.0` | https://github.com/RustCrypto/utils |
| `cfg-if` | `1.0.4` | `MIT OR Apache-2.0` | https://github.com/rust-lang/cfg-if |
| `cpufeatures` | `0.2.17` | `MIT OR Apache-2.0` | https://github.com/RustCrypto/utils |
| `crypto-common` | `0.1.7` | `MIT OR Apache-2.0` | https://github.com/RustCrypto/traits |
| `digest` | `0.10.7` | `MIT OR Apache-2.0` | https://github.com/RustCrypto/traits |
| `errno` | `0.3.14` | `MIT OR Apache-2.0` | https://github.com/lambda-fairy/rust-errno |
| `fastrand` | `2.5.0` | `Apache-2.0 OR MIT` | https://github.com/smol-rs/fastrand |
| `generic-array` | `0.14.7` | `MIT` | https://github.com/fizyk20/generic-array.git |
| `getrandom` | `0.4.3` | `MIT OR Apache-2.0` | https://github.com/rust-random/getrandom |
| `libc` | `0.2.189` | `MIT OR Apache-2.0` | https://github.com/rust-lang/libc |
| `once_cell` | `1.21.4` | `MIT OR Apache-2.0` | https://github.com/matklad/once_cell |
| `rand_core` | `0.10.1` | `MIT OR Apache-2.0` | https://github.com/rust-random/rand_core |
| `rustix` | `1.1.4` | `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` | https://github.com/bytecodealliance/rustix |
| `sha2` | `0.10.9` | `MIT OR Apache-2.0` | https://github.com/RustCrypto/hashes |
| `tempfile` | `3.27.0` | `MIT OR Apache-2.0` | https://github.com/Stebalien/tempfile |
| `texpdf-protocol` | `0.1.0` | `MIT` | https://github.com/johannes-schmieder/texpdf |
| `texpdf-stata` | `0.1.0` | `MIT` | https://github.com/johannes-schmieder/texpdf |
| `typenum` | `1.20.1` | `MIT OR Apache-2.0` | https://github.com/paholg/typenum |
| `version_check` | `0.9.5` | `MIT/Apache-2.0` | https://github.com/SergioBenitez/version_check |

## Native libraries

| Library | License | Role |
|---|---|---|
| `fontconfig` | `MIT-style Fontconfig license` | font discovery/configuration used by the embedded engine |
| `freetype` | `FTL OR GPL-2.0-or-later` | font rasterization |
| `graphite2` | `MPL-2.0` | Graphite smart-font shaping |
| `harfbuzz` | `MIT` | OpenType text shaping |
| `icu` | `ICU` | Unicode and internationalization support |
| `libpng` | `libpng-2.0` | PNG image support |
| `zlib` | `Zlib` | compression support |
