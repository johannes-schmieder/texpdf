#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
rustup_bin="${RUSTUP_BIN:-/opt/homebrew/bin/rustup}"

if [[ ! -x "$rustup_bin" ]]; then
  echo "Rust quick check could not find rustup at $rustup_bin" >&2
  exit 127
fi

cd "$repo_root"
toolchain="${RUST_TOOLCHAIN:-1.97.1}"
if ! "$rustup_bin" run "$toolchain" rustc --version >/dev/null 2>&1; then
  echo "Required Rust toolchain $toolchain is not installed" >&2
  exit 127
fi
"$rustup_bin" component add --toolchain "$toolchain" rustfmt clippy

toolchain_cargo="$($rustup_bin which --toolchain "$toolchain" cargo)"
toolchain_bin="$(/usr/bin/dirname "$toolchain_cargo")"
export PATH="$toolchain_bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export RUSTC="$($rustup_bin which --toolchain "$toolchain" rustc)"

rustc_version="$($RUSTC --version)"
echo "RUST_TOOLCHAIN=$toolchain"
echo "RUSTC_VERSION=$rustc_version"

if [[ -f Cargo.toml ]]; then
  export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/private/tmp/texpdf-cargo-target}"
  export TEXPDF_BUNDLE_CACHE="${TEXPDF_BUNDLE_CACHE:-/private/tmp/texpdf-bundle-cache}"
  rust_profile="${TEXPDF_RUST_PROFILE:-quick}"
  if [[ -f ci/FULL_ENGINE ]]; then
    rust_profile=engine
  fi

  case "$rust_profile" in
    quick)
      /usr/bin/python3 tools/prepare_stub_bundle.py
      ;;
    engine)
      /usr/bin/python3 tools/prepare_bundle.py --cache-dir "$TEXPDF_BUNDLE_CACHE"
      ;;
    *)
      echo "Unknown TEXPDF_RUST_PROFILE: $rust_profile" >&2
      exit 2
      ;;
  esac
  /bin/cat bundle/generated/bundle-info.json

  if [[ ! -f Cargo.lock ]]; then
    "$toolchain_cargo" generate-lockfile
  fi
  /bin/mkdir -p .ci/stata/run
  /bin/cp Cargo.lock .ci/stata/run/Cargo.lock.generated
  /bin/cp bundle/generated/bundle-info.json .ci/stata/run/bundle-info.json

  "$toolchain_cargo" fmt --all --check
  # Tectonic's bridge crates require PNG, FreeType, Graphite2, HarfBuzz, ICU,
  # Fontconfig, and zlib. Build them statically in a repository-scoped vcpkg
  # tree so the eventual plugin does not depend on a user's package manager.
  source tools/prepare_native_deps.sh
  "$toolchain_cargo" clippy --locked --workspace --all-targets --all-features -- -D warnings
  if [[ "$rust_profile" == engine ]]; then
    "$toolchain_cargo" test --locked --workspace --all-targets --all-features
    rust_mode=repository-engine
  else
    "$toolchain_cargo" test --locked --workspace --all-targets --all-features diagnostics::tests
    "$toolchain_cargo" test --locked --package texpdf-stata --all-targets --all-features
    rust_mode=repository-compile
  fi

  "$toolchain_cargo" build --locked --release --package texpdf-stata
  /usr/bin/python3 tools/stage_plugin.py --target-dir "$CARGO_TARGET_DIR"
  # The licensed Stata harness stages files listed in the checkout's index.
  # Add the generated plugin only to this temporary CI index; it is ignored by
  # Git and is never committed by this script.
  git add -f stata/_texpdf_plugin.plugin
  echo "RUST_QUICK_MODE=$rust_mode"
else
  smoke_root="${RUNNER_TEMP:-/private/tmp}/texpdf-rust-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
  /bin/mkdir -p "$smoke_root"
  /usr/bin/printf '%s\n' 'fn main() { println!("TEXPDF_RUST_CI_OK"); }' > "$smoke_root/main.rs"
  "$RUSTC" "$smoke_root/main.rs" -o "$smoke_root/texpdf-rust-smoke"
  "$smoke_root/texpdf-rust-smoke"
  echo "RUST_QUICK_MODE=toolchain-smoke"
fi
