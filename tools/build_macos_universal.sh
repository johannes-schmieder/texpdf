#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
rustup_bin="${RUSTUP_BIN:-/opt/homebrew/bin/rustup}"
toolchain="${RUST_TOOLCHAIN:-1.97.1}"
cargo_bin="$($rustup_bin which --toolchain "$toolchain" cargo)"
export RUSTC="$($rustup_bin which --toolchain "$toolchain" rustc)"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/private/tmp/texpdf-cargo-target}"
output="${1:-dist/macos-universal/_texpdf_plugin_macosx.plugin}"
manifest="${2:-dist/macos-universal/manifest.json}"

cd "$repo_root"
test -f bundle/generated/texpdf-bundle.zip
test -f bundle/generated/bundle-info.json
"$rustup_bin" target add --toolchain "$toolchain" aarch64-apple-darwin x86_64-apple-darwin

build_slice() {
  local target="$1"
  export TEXPDF_BUILD_TARGET="$target"
  source tools/prepare_native_deps_for_target.sh "$target"
  "$cargo_bin" build --locked --release --package texpdf-helper --target "$target"
  export TEXPDF_HELPER_PATH="$CARGO_TARGET_DIR/$target/release/texpdf-helper"
  test -f "$TEXPDF_HELPER_PATH"
  "$cargo_bin" build --locked --release --package texpdf-stata --target "$target"
  unset TEXPDF_HELPER_PATH
  unset TEXPDF_BUILD_TARGET
}

build_slice aarch64-apple-darwin
build_slice x86_64-apple-darwin

arm_library="$CARGO_TARGET_DIR/aarch64-apple-darwin/release/libtexpdf_stata.dylib"
intel_library="$CARGO_TARGET_DIR/x86_64-apple-darwin/release/libtexpdf_stata.dylib"
arm_helper="$CARGO_TARGET_DIR/aarch64-apple-darwin/release/texpdf-helper"
intel_helper="$CARGO_TARGET_DIR/x86_64-apple-darwin/release/texpdf-helper"
test -f "$arm_library"
test -f "$intel_library"
test -f "$arm_helper"
test -f "$intel_helper"

mkdir -p "$(dirname "$output")" "$(dirname "$manifest")"
temporary="$output.tmp"
rm -f "$temporary"
/usr/bin/lipo -create "$arm_library" "$intel_library" -output "$temporary"
# With Apple's lipo, the input file precedes -verify_arch. Putting the file at
# the end makes it look like an architecture name.
/usr/bin/lipo "$temporary" -verify_arch arm64 x86_64
/usr/bin/nm -arch arm64 -gU "$temporary" | /usr/bin/grep -Eq '(^|[[:space:]])_pginit$'
/usr/bin/nm -arch arm64 -gU "$temporary" | /usr/bin/grep -Eq '(^|[[:space:]])_stata_call$'
/usr/bin/nm -arch x86_64 -gU "$temporary" | /usr/bin/grep -Eq '(^|[[:space:]])_pginit$'
/usr/bin/nm -arch x86_64 -gU "$temporary" | /usr/bin/grep -Eq '(^|[[:space:]])_stata_call$'

# For a dylib, the first indented otool -L entry is LC_ID_DYLIB (the library's
# own install name), not a runtime dependency. Inspect each architecture
# separately and exclude that self-ID before enforcing the standalone policy.
runtime_deps="$({
  for arch in arm64 x86_64; do
    /usr/bin/otool -arch "$arch" -L "$temporary" |
      /usr/bin/awk 'BEGIN { seen_id = 0 } /^[[:space:]]/ { if (seen_id == 0) { seen_id = 1; next } print }'
  done
} | /usr/bin/sort -u)"
if printf '%s\n' "$runtime_deps" | /usr/bin/grep -Eq '/(opt/homebrew|usr/local|private/tmp/texpdf|Users/[^/]+/\.vcpkg)/'; then
  echo "TEXPDF_UNIVERSAL_ERROR unexpected package-manager/build-tree runtime dependency" >&2
  printf '%s\n' "$runtime_deps" >&2
  rm -f "$temporary"
  exit 2
fi
mv "$temporary" "$output"

/usr/bin/python3 - "$arm_library" "$intel_library" "$arm_helper" "$intel_helper" "$output" "$manifest" <<'PY'
from pathlib import Path
import hashlib
import json
import subprocess
import sys

arm = Path(sys.argv[1])
intel = Path(sys.argv[2])
arm_helper = Path(sys.argv[3])
intel_helper = Path(sys.argv[4])
universal = Path(sys.argv[5])
manifest = Path(sys.argv[6])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path, target: str) -> dict[str, object]:
    return {
        "target": target,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def dependencies(architecture: str) -> list[str]:
    lines = subprocess.run(
        ["/usr/bin/otool", "-arch", architecture, "-L", str(universal)],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    libraries = [line.strip() for line in lines if line[:1].isspace()]
    # First entry is the dylib's own LC_ID_DYLIB value.
    return libraries[1:] if libraries else []


architectures = subprocess.run(
    ["/usr/bin/lipo", "-archs", str(universal)],
    check=True,
    text=True,
    capture_output=True,
).stdout.strip().split()
if set(architectures) != {"arm64", "x86_64"}:
    raise SystemExit(f"unexpected universal architectures: {architectures}")
dependencies_by_arch = {
    architecture: dependencies(architecture) for architecture in ("arm64", "x86_64")
}
all_dependencies = sorted(
    {value for values in dependencies_by_arch.values() for value in values}
)
payload = {
    "schema_version": 1,
    "kind": "macOS universal Stata plugin",
    "architectures": architectures,
    "slices": {
        "arm64": {
            **record(arm, "aarch64-apple-darwin"),
            "embedded_helper": record(arm_helper, "aarch64-apple-darwin"),
        },
        "x86_64": {
            **record(intel, "x86_64-apple-darwin"),
            "embedded_helper": record(intel_helper, "x86_64-apple-darwin"),
        },
    },
    "universal": record(universal, "universal2-apple-darwin"),
    "exports": ["pginit", "stata_call"],
    "dynamic_dependencies": all_dependencies,
    "dynamic_dependencies_by_arch": dependencies_by_arch,
    "intel_runtime_qualified": False,
    "arm_runtime_qualified": False,
}
manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "TEXPDF_MACOS_UNIVERSAL_READY "
    f"architectures={','.join(architectures)} size_bytes={universal.stat().st_size} "
    f"sha256={payload['universal']['sha256']}"
)
PY
