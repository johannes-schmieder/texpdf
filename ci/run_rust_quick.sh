#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
rustup_bin="${RUSTUP_BIN:-/opt/homebrew/bin/rustup}"

if [[ ! -x "$rustup_bin" ]]; then
  echo "Rust quick check could not find rustup at $rustup_bin" >&2
  exit 127
fi

cd "$repo_root"
# Use the release-pinned compiler. rustfmt and Clippy are rustup components,
# not intrinsic Cargo commands, so make their presence explicit and idempotent
# on the dedicated self-hosted runner.
toolchain="${RUST_TOOLCHAIN:-1.97.1}"
if ! "$rustup_bin" run "$toolchain" rustc --version >/dev/null 2>&1; then
  echo "Required Rust toolchain $toolchain is not installed" >&2
  exit 127
fi
if ! "$rustup_bin" run "$toolchain" cargo fmt --version >/dev/null 2>&1 ||
   ! "$rustup_bin" run "$toolchain" cargo clippy --version >/dev/null 2>&1; then
  "$rustup_bin" component add --toolchain "$toolchain" rustfmt clippy
fi

rustc_version="$($rustup_bin run "$toolchain" rustc --version)"
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
    "$rustup_bin" run "$toolchain" cargo generate-lockfile
  fi
  /bin/mkdir -p .ci/stata/run
  /bin/cp Cargo.lock .ci/stata/run/Cargo.lock.generated
  /bin/cp bundle/generated/bundle-info.json .ci/stata/run/bundle-info.json

  "$rustup_bin" run "$toolchain" cargo fmt --all --check
  "$rustup_bin" run "$toolchain" cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
  if [[ "$rust_profile" == engine ]]; then
    "$rustup_bin" run "$toolchain" cargo test --locked --workspace --all-targets --all-features
    echo "RUST_QUICK_MODE=repository-engine"
  else
    # Compile every test target, but execute only the lightweight diagnostics
    # tests. Runtime engine tests require the real bundle and run in the
    # explicit engine profile.
    "$rustup_bin" run "$toolchain" cargo test --locked --workspace --all-targets --all-features diagnostics::tests
    echo "RUST_QUICK_MODE=repository-compile"
  fi
else
  smoke_root="${RUNNER_TEMP:-/private/tmp}/texpdf-rust-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
  /bin/mkdir -p "$smoke_root"
  /usr/bin/printf '%s\n' 'fn main() { println!("TEXPDF_RUST_CI_OK"); }' > "$smoke_root/main.rs"
  "$rustup_bin" run "$toolchain" rustc "$smoke_root/main.rs" -o "$smoke_root/texpdf-rust-smoke"
  "$smoke_root/texpdf-rust-smoke"
  echo "RUST_QUICK_MODE=toolchain-smoke"
fi
