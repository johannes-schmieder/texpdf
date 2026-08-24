#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
rustup_bin="${RUSTUP_BIN:-/opt/homebrew/bin/rustup}"

if [[ ! -x "$rustup_bin" ]]; then
  echo "Rust quick check could not find rustup at $rustup_bin" >&2
  exit 127
fi

cd "$repo_root"
if [[ -n "${RUST_TOOLCHAIN:-}" ]]; then
  toolchain="$RUST_TOOLCHAIN"
else
  active_toolchain="$($rustup_bin show active-toolchain)"
  toolchain="${active_toolchain%% *}"
fi

if ! "$rustup_bin" toolchain list | /usr/bin/grep -Eq "^${toolchain}([[:space:]]|$)"; then
  echo "Required Rust toolchain $toolchain is not installed" >&2
  exit 127
fi

rustc_version="$($rustup_bin run "$toolchain" rustc --version)"
echo "RUST_TOOLCHAIN=$toolchain"
echo "RUSTC_VERSION=$rustc_version"

if [[ -f Cargo.toml ]]; then
  export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/private/tmp/texpdf-cargo-target}"
  export TEXPDF_BUNDLE_CACHE="${TEXPDF_BUNDLE_CACHE:-/private/tmp/texpdf-bundle-cache}"
  /usr/bin/python3 tools/prepare_bundle.py --cache-dir "$TEXPDF_BUNDLE_CACHE"
  /bin/cat bundle/generated/bundle-info.json

  if [[ ! -f Cargo.lock ]]; then
    "$rustup_bin" run "$toolchain" cargo generate-lockfile
  fi
  /bin/mkdir -p .ci/stata/run
  /bin/cp Cargo.lock .ci/stata/run/Cargo.lock.generated
  /bin/cp bundle/generated/bundle-info.json .ci/stata/run/bundle-info.json

  "$rustup_bin" run "$toolchain" cargo fmt --all --check
  "$rustup_bin" run "$toolchain" cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
  "$rustup_bin" run "$toolchain" cargo test --locked --workspace --all-targets --all-features
  echo "RUST_QUICK_MODE=repository"
else
  smoke_root="${RUNNER_TEMP:-/private/tmp}/texpdf-rust-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
  /bin/mkdir -p "$smoke_root"
  /usr/bin/printf '%s\n' 'fn main() { println!("TEXPDF_RUST_CI_OK"); }' > "$smoke_root/main.rs"
  "$rustup_bin" run "$toolchain" rustc "$smoke_root/main.rs" -o "$smoke_root/texpdf-rust-smoke"
  "$smoke_root/texpdf-rust-smoke"
  echo "RUST_QUICK_MODE=toolchain-smoke"
fi
