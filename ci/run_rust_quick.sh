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

  if [[ ! -f Cargo.lock ]]; then
    "$toolchain_cargo" generate-lockfile
  fi
  /bin/mkdir -p .ci/stata/run
  /bin/cp Cargo.lock .ci/stata/run/Cargo.lock.generated

  /usr/bin/python3 tools/prepare_stub_bundle.py
  source tools/prepare_native_deps.sh

  case "$rust_profile" in
    quick)
      ;;
    engine)
      if [[ -f bundle/curated-manifest.json ]]; then
        /usr/bin/python3 tools/prepare_curated_bundle.py \
          --manifest bundle/curated-manifest.json \
          --cache-dir "$TEXPDF_BUNDLE_CACHE"
      else
        source_url="$(/usr/bin/python3 - <<'PY'
from pathlib import Path
for raw in Path('bundle/bundle.lock.toml').read_text(encoding='utf-8').splitlines():
    line = raw.strip()
    if line.startswith('source_url'):
        print(line.split('=', 1)[1].strip().strip('"'))
        break
else:
    raise SystemExit('source_url is absent from bundle lock')
PY
)"
        trace_path="bundle/generated/resource-trace.txt"
        set +e
        "$toolchain_cargo" run --locked --package texpdf-bundle-resolver -- \
          "$source_url" "$trace_path" tests/fixtures/bundle_corpus.tex
        resolver_rc=$?
        set -e
        if [[ -f "$trace_path" ]]; then
          /bin/cp "$trace_path" .ci/stata/run/resource-trace.txt
        fi
        if [[ $resolver_rc -ne 0 ]]; then
          echo "TEXPDF_BUNDLE_RESOLVER_FAILED rc=$resolver_rc trace=$trace_path" >&2
          exit "$resolver_rc"
        fi
        /usr/bin/python3 tools/prepare_curated_bundle.py \
          --trace "$trace_path" \
          --write-manifest bundle/generated/curated-manifest.json \
          --cache-dir "$TEXPDF_BUNDLE_CACHE"
      fi
      ;;
    *)
      echo "Unknown TEXPDF_RUST_PROFILE: $rust_profile" >&2
      exit 2
      ;;
  esac

  /bin/cat bundle/generated/bundle-info.json
  /bin/cp bundle/generated/bundle-info.json .ci/stata/run/bundle-info.json
  if [[ -f bundle/generated/resource-trace.txt ]]; then
    /bin/cp bundle/generated/resource-trace.txt .ci/stata/run/resource-trace.txt
  fi
  if [[ -f bundle/generated/curated-manifest.json ]]; then
    /bin/cp bundle/generated/curated-manifest.json .ci/stata/run/curated-manifest.json
  fi

  "$toolchain_cargo" fmt --all --check
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
