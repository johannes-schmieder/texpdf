#!/bin/bash
# Source the existing pinned native-dependency preparation for an explicit Rust
# target without permanently replacing Cargo's real rustc executable.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: source tools/prepare_native_deps_for_target.sh TARGET" >&2
  return 2 2>/dev/null || exit 2
fi

target="$1"
case "$target" in
  aarch64-apple-darwin|x86_64-apple-darwin|x86_64-unknown-linux-gnu|x86_64-pc-windows-msvc)
    ;;
  *)
    echo "TEXPDF_NATIVE_DEPS_ERROR unsupported explicit target: $target" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac

real_rustc="${RUSTC:-rustc}"
temp_base="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
wrapper_root="$temp_base/texpdf-rustc-target-wrapper"
mkdir -p "$wrapper_root"
wrapper="$wrapper_root/rustc-$target"
cat > "$wrapper" <<EOF
#!/bin/bash
set -euo pipefail
if [[ "\${1:-}" == "-vV" ]]; then
  "$real_rustc" -vV | /usr/bin/sed 's/^host: .*/host: $target/'
else
  exec "$real_rustc" "\$@"
fi
EOF
chmod +x "$wrapper"

export RUSTC="$wrapper"
# shellcheck source=tools/prepare_native_deps.sh
source tools/prepare_native_deps.sh
export RUSTC="$real_rustc"
export TEXPDF_BUILD_TARGET="$target"

echo "TEXPDF_NATIVE_TARGET_READY target=$target triplet=${VCPKGRS_TRIPLET:-unknown}"
