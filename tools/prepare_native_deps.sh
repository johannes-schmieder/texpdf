#!/bin/bash
# Prepare Tectonic's native C/C++ dependencies in a private, pinned vcpkg tree.
# This script is meant to be sourced so that VCPKG_ROOT and related variables
# remain visible to subsequent Cargo invocations.

set -euo pipefail

vcpkg_rev="a62ce77d56ee07513b4b67de1ec2daeaebfae51a"
vcpkg_short="${vcpkg_rev:0:12}"
vcpkg_root="${TEXPDF_VCPKG_ROOT:-/private/tmp/texpdf-vcpkg-$vcpkg_short}"
vcpkg_binary_cache="${TEXPDF_VCPKG_BINARY_CACHE:-/private/tmp/texpdf-vcpkg-binary-cache}"

host="$(${RUSTC:-rustc} -vV | /usr/bin/sed -n 's/^host: //p')"
case "$host" in
  aarch64-apple-darwin)
    triplet="arm64-osx"
    ;;
  x86_64-apple-darwin)
    triplet="x64-osx"
    ;;
  x86_64-unknown-linux-gnu)
    triplet="x64-linux"
    ;;
  x86_64-pc-windows-msvc)
    triplet="x64-windows-static-release"
    ;;
  *)
    echo "TEXPDF_NATIVE_DEPS_ERROR unsupported Rust host: $host" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac

mkdir -p "$vcpkg_binary_cache"

if [[ ! -x "$vcpkg_root/vcpkg" ]] ||
   [[ ! -f "$vcpkg_root/.texpdf-revision" ]] ||
   [[ "$(cat "$vcpkg_root/.texpdf-revision" 2>/dev/null || true)" != "$vcpkg_rev" ]]; then
  rm -rf "$vcpkg_root"
  mkdir -p "$vcpkg_root"
  git -C "$vcpkg_root" init -q
  git -C "$vcpkg_root" remote add origin https://github.com/microsoft/vcpkg.git
  git -C "$vcpkg_root" fetch --depth 1 origin "$vcpkg_rev"
  git -C "$vcpkg_root" checkout --detach FETCH_HEAD
  [[ "$(git -C "$vcpkg_root" rev-parse HEAD)" == "$vcpkg_rev" ]]
  "$vcpkg_root/bootstrap-vcpkg.sh" -disableMetrics
  printf '%s\n' "$vcpkg_rev" > "$vcpkg_root/.texpdf-revision"
fi

export VCPKG_ROOT="$vcpkg_root"
export VCPKGRS_TRIPLET="$triplet"
export VCPKG_DEFAULT_BINARY_CACHE="$vcpkg_binary_cache"
export TECTONIC_DEP_BACKEND=vcpkg

package_key="fontconfig-freetype-harfbuzz-graphite2-icu-libpng-zlib"
stamp="$vcpkg_root/installed/$triplet/.texpdf-$package_key"
if [[ ! -f "$stamp" ]]; then
  "$vcpkg_root/vcpkg" install \
    --triplet "$triplet" \
    fontconfig \
    freetype \
    'harfbuzz[graphite2]' \
    icu \
    libpng \
    zlib
  mkdir -p "$(dirname "$stamp")"
  printf '%s\n' "$vcpkg_rev" > "$stamp"
fi

echo "TEXPDF_NATIVE_DEPS_READY host=$host triplet=$triplet root=$vcpkg_root"
