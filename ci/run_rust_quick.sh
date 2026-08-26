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
python_bin="${TEXPDF_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$python_bin" ]] || [[ ! -x "$python_bin" ]] || \
   ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Rust quick check requires Python 3.9 or newer" >&2
  exit 127
fi
"$python_bin" ci/check_release_metadata.py
temp_base="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"

rustc_version="$($RUSTC --version)"
echo "RUST_TOOLCHAIN=$toolchain"
echo "RUSTC_VERSION=$rustc_version"

if [[ -f Cargo.toml ]]; then
  export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$temp_base/texpdf-cargo-target}"
  export TEXPDF_BUNDLE_CACHE="${TEXPDF_BUNDLE_CACHE:-$temp_base/texpdf-bundle-cache}"
  rust_profile="${TEXPDF_RUST_PROFILE:-quick}"
  if [[ -f ci/FULL_ENGINE ]]; then
    rust_profile=engine
  fi

  if [[ ! -f Cargo.lock ]]; then
    "$toolchain_cargo" generate-lockfile
  fi
  /bin/mkdir -p .ci/stata/run
  /bin/cp Cargo.lock .ci/stata/run/Cargo.lock.generated

  "$python_bin" tools/prepare_stub_bundle.py
  source tools/prepare_native_deps.sh

  case "$rust_profile" in
    quick)
      ;;
    engine)
      source_tar="$TEXPDF_BUNDLE_CACHE/tlextras-2022.0r0.tar"
      common_bundle_args=(--cache-dir "$TEXPDF_BUNDLE_CACHE")
      if [[ -f "$source_tar" ]]; then
        common_bundle_args+=(--source-tar "$source_tar")
      fi

      if [[ -f bundle/curated-manifest.json ]]; then
        "$python_bin" tools/prepare_curated_bundle.py \
          --manifest bundle/curated-manifest.json \
          "${common_bundle_args[@]}"
      else
        trace_path="bundle/generated/resource-trace.txt"
        if [[ -f bundle/resource-trace.txt.gz.b64 ]]; then
          "$python_bin" - <<'PY'
from pathlib import Path
import base64
import gzip

source = Path("bundle/resource-trace.txt.gz.b64")
destination = Path("bundle/generated/resource-trace.txt")
destination.parent.mkdir(parents=True, exist_ok=True)
compressed = base64.b64decode(source.read_bytes(), validate=True)
names = set(gzip.decompress(compressed).decode("utf-8").splitlines())
required = Path("bundle/required-resources.txt")
if required.is_file():
    names.update(required.read_text(encoding="utf-8").splitlines())
names.discard("")
destination.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
print(
    "TEXPDF_COMMITTED_TRACE_READY "
    f"path={destination} lines={len(names)}"
)
PY
          "$python_bin" tools/prepare_curated_bundle.py \
            --trace "$trace_path" \
            --write-manifest bundle/generated/curated-manifest.json \
            "${common_bundle_args[@]}"
        else
          source_url="$("$python_bin" - <<'PY'
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
          resource_dir="bundle/generated/resolved-resources"
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
          "$python_bin" tools/prepare_curated_bundle.py \
            --trace "$trace_path" \
            --resource-dir "$resource_dir" \
            --write-manifest bundle/generated/curated-manifest.json \
            "${common_bundle_args[@]}"
        fi
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

  "$toolchain_cargo" build --locked --release --package texpdf-helper
  helper_name=texpdf-helper
  if [[ "${OS:-}" == Windows_NT ]]; then helper_name=texpdf-helper.exe; fi
  export TEXPDF_HELPER_PATH="$CARGO_TARGET_DIR/release/$helper_name"
  test -f "$TEXPDF_HELPER_PATH"
  "$python_bin" - "$TEXPDF_HELPER_PATH" .ci/stata/run/helper-manifest.json <<'PY'
from pathlib import Path
import hashlib
import json
import os
import sys

source = Path(sys.argv[1])
output = Path(sys.argv[2])
payload = {
    "schema_version": 1,
    "path": str(source),
    "size_bytes": source.stat().st_size,
    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "target": os.environ.get("TARGET", "native"),
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "TEXPDF_HELPER_READY "
    f"path={source} size_bytes={payload['size_bytes']} sha256={payload['sha256']}"
)
PY

  "$toolchain_cargo" fmt --all --check
  "$python_bin" ci/check_workflow_security.py
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
  "$python_bin" tools/stage_plugin.py --target-dir "$CARGO_TARGET_DIR"
  staged_plugin=stata/_texpdf_plugin_macosx.plugin
  if [[ "${OS:-}" == Windows_NT ]]; then staged_plugin=stata/_texpdf_plugin_windows.plugin; fi
  if [[ "$(uname -s)" == Linux ]]; then staged_plugin=stata/_texpdf_plugin_unix.plugin; fi
  git add -f "$staged_plugin"

  if [[ "$rust_profile" == engine ]]; then
    "$python_bin" tools/package_release.py \
      --plugin "$staged_plugin" \
      --embedded-helper "$TEXPDF_HELPER_PATH" \
      --bundle-info bundle/generated/bundle-info.json \
      --output-dir dist/texpdf-macos-arm64 \
      --zip dist/texpdf-macos-arm64.zip \
      --manifest .ci/stata/run/package-manifest.json \
      --target aarch64-apple-darwin
    git add -f dist/texpdf-macos-arm64
  fi

  echo "RUST_QUICK_MODE=$rust_mode"
else
  smoke_root="$temp_base/texpdf-rust-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
  /bin/mkdir -p "$smoke_root"
  /usr/bin/printf '%s\n' 'fn main() { println!("TEXPDF_RUST_CI_OK"); }' > "$smoke_root/main.rs"
  "$RUSTC" "$smoke_root/main.rs" -o "$smoke_root/texpdf-rust-smoke"
  "$smoke_root/texpdf-rust-smoke"
  echo "RUST_QUICK_MODE=toolchain-smoke"
fi
