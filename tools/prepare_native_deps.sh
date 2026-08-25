#!/bin/bash
# Prepare Tectonic's native C/C++ dependencies in private, pinned build trees.
# This script is meant to be sourced so that VCPKG_ROOT and related variables
# remain visible to subsequent Cargo invocations.

set -euo pipefail

vcpkg_rev="a62ce77d56ee07513b4b67de1ec2daeaebfae51a"
vcpkg_short="${vcpkg_rev:0:12}"
temp_base="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
vcpkg_root="${TEXPDF_VCPKG_ROOT:-$temp_base/texpdf-vcpkg-$vcpkg_short}"
vcpkg_binary_cache="${TEXPDF_VCPKG_BINARY_CACHE:-$temp_base/texpdf-vcpkg-binary-cache}"

pkgconf_rev="4fc570f91d9d8d843ab32d2198a5c064538d8ffd"
pkgconf_short="${pkgconf_rev:0:12}"
pkgconf_root="${TEXPDF_PKGCONF_ROOT:-$temp_base/texpdf-pkgconf-$pkgconf_short}"
pkgconf_bootstrap_revision="2:$pkgconf_rev"

python_bin="${TEXPDF_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$python_bin" ]] || [[ ! -x "$python_bin" ]]; then
  echo "TEXPDF_NATIVE_DEPS_ERROR Python 3.9 or newer is required" >&2
  return 2 2>/dev/null || exit 2
fi
if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "TEXPDF_NATIVE_DEPS_ERROR Python 3.9 or newer is required: $python_bin" >&2
  return 2 2>/dev/null || exit 2
fi

host="$(${RUSTC:-rustc} -vV | /usr/bin/sed -n 's/^host: //p')"
case "$host" in
  aarch64-apple-darwin)
    triplet="arm64-osx"
    cc="${CC:-/usr/bin/clang}"
    ;;
  x86_64-apple-darwin)
    triplet="x64-osx"
    cc="${CC:-/usr/bin/clang}"
    ;;
  x86_64-unknown-linux-gnu)
    triplet="x64-linux"
    cc="${CC:-cc}"
    ;;
  x86_64-pc-windows-msvc)
    triplet="x64-windows-static-release"
    echo "TEXPDF_NATIVE_DEPS_ERROR private pkgconf bootstrap is not yet implemented for MSVC" >&2
    return 2 2>/dev/null || exit 2
    ;;
  *)
    echo "TEXPDF_NATIVE_DEPS_ERROR unsupported Rust host: $host" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac

probe_declaration() {
  local symbol="$1"
  local header="$2"

  # The current Apple SDK exposes these interfaces, with strlcpy/strlcat
  # potentially wrapped in fortified function-like macros. Feature-test macros
  # used by generic probes can hide those declarations and incorrectly enable
  # pkgconf's fallback implementations, which then collide with the SDK.
  if [[ "$host" == *-apple-darwin ]]; then
    case "$symbol" in
      strlcat|strlcpy|strndup)
        printf '1'
        return
        ;;
      reallocarray|pledge|unveil)
        printf '0'
        return
        ;;
    esac
  fi

  local probe_dir="$pkgconf_root/.texpdf-probes"
  local source="$probe_dir/$symbol.c"
  local object="$probe_dir/$symbol.o"
  mkdir -p "$probe_dir"
  cat > "$source" <<EOF
#include <$header>
#ifdef $symbol
int main(void) { return 0; }
#else
int main(void) { (void) $symbol; return 0; }
#endif
EOF
  local standard=c99
  local feature_flags=()
  if [[ "$host" == *-unknown-linux-gnu ]]; then
    standard=gnu99
    feature_flags=(-D_GNU_SOURCE)
  fi
  if "$cc" "-std=$standard" "${feature_flags[@]}" \
      -Werror=implicit-function-declaration -c "$source" -o "$object" \
      >/dev/null 2>&1; then
    printf '1'
  else
    printf '0'
  fi
}

write_pkgconf_config() {
  local config="$pkgconf_root/libpkgconf/config.h"
  local temporary="$config.tmp"
  local name header macro declared
  {
    echo '#define PACKAGE_NAME "pkgconf-lite"'
    echo '#define PACKAGE_BUGREPORT "https://github.com/pkgconf/pkgconf/issues"'
    echo '#define PACKAGE_VERSION "2.5.1"'
    echo '#define PACKAGE "pkgconf-lite 2.5.1"'
    echo '#define STDC_HEADERS 1'
    echo '#define _DARWIN_USE_64_BIT_INODE 1'
    echo '#define __EXTENSIONS__ 1'
    for entry in \
      'strlcat:string.h' \
      'strlcpy:string.h' \
      'strndup:string.h' \
      'reallocarray:stdlib.h' \
      'pledge:unistd.h' \
      'unveil:unistd.h'; do
      name="${entry%%:*}"
      header="${entry#*:}"
      macro="$(printf '%s' "$name" | /usr/bin/tr '[:lower:]' '[:upper:]')"
      declared="$(probe_declaration "$name" "$header")"
      echo "#define HAVE_DECL_${macro} ${declared}"
      echo "#define HAVE_${macro} ${declared}"
    done
  } > "$temporary"
  mv "$temporary" "$config"
}

patch_pkgconf_lite_sources() {
  "$python_bin" - "$pkgconf_root/Makefile.lite" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if "libpkgconf/buffer.c" not in text:
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if "libpkgconf/argvsplit.c" in line:
            lines.insert(index + 1, "\tlibpkgconf/buffer.c\t\t\\\n")
            break
    else:
        raise SystemExit("cannot locate Makefile.lite SRCS anchor")
    path.write_text("".join(lines), encoding="utf-8")
PY
}

patch_vcpkg_ports() {
  # The pinned GNU gperf and ICU release archives both contain generated
  # configure scripts. Their AUTORECONF flags needlessly require host-level
  # autoconf, automake, and libtoolize. Remove exactly those flags while leaving
  # vcpkg's source URLs, hashes, patches, and configure options unchanged.
  "$python_bin" - \
    "$vcpkg_root/ports/gperf/portfile.cmake:gperf" \
    "$vcpkg_root/ports/icu/portfile.cmake:icu" <<'PY'
from pathlib import Path
import sys

for specification in sys.argv[1:]:
    path_text, label = specification.rsplit(":", 1)
    path = Path(path_text)
    text = path.read_text(encoding="utf-8")
    needle = "    AUTORECONF\n"
    if needle in text:
        if text.count(needle) != 1:
            raise SystemExit(f"unexpected number of {label} AUTORECONF flags")
        text = text.replace(needle, "", 1)
    elif "vcpkg_make_configure(" not in text:
        raise SystemExit(f"cannot validate pinned {label} portfile")
    path.write_text(text, encoding="utf-8")
PY
}

# vcpkg requires a pkg-config frontend even while it is building the libraries
# that later supply .pc files. Build pkgconf-lite from a pinned upstream commit.
# Makefile.lite's stock config target uses obsolete HAVE_* names and omits the
# newer buffer module, so patch both defects in the pinned private checkout.
if [[ ! -x "$pkgconf_root/bin/pkg-config" ]] ||
   [[ ! -f "$pkgconf_root/.texpdf-revision" ]] ||
   [[ "$(cat "$pkgconf_root/.texpdf-revision" 2>/dev/null || true)" != "$pkgconf_bootstrap_revision" ]]; then
  rm -rf "$pkgconf_root"
  mkdir -p "$pkgconf_root"
  git -C "$pkgconf_root" init -q
  git -C "$pkgconf_root" remote add origin https://github.com/pkgconf/pkgconf.git
  git -C "$pkgconf_root" fetch --depth 1 origin "$pkgconf_rev"
  git -C "$pkgconf_root" checkout --detach FETCH_HEAD
  [[ "$(git -C "$pkgconf_root" rev-parse HEAD)" == "$pkgconf_rev" ]]
  write_pkgconf_config
  patch_pkgconf_lite_sources
  /usr/bin/make -C "$pkgconf_root" -f Makefile.lite \
    CC="$cc" \
    STRIP=/usr/bin/strip \
    SYSTEM_LIBDIR='/usr/lib:/usr/local/lib:/opt/homebrew/lib' \
    SYSTEM_INCLUDEDIR='/usr/include:/usr/local/include:/opt/homebrew/include' \
    PKG_DEFAULT_PATH='/usr/lib/pkgconfig:/usr/share/pkgconfig:/usr/local/lib/pkgconfig:/opt/homebrew/lib/pkgconfig'
  mkdir -p "$pkgconf_root/bin"
  cp "$pkgconf_root/pkgconf-lite" "$pkgconf_root/bin/pkgconf"
  ln -sf pkgconf "$pkgconf_root/bin/pkg-config"
  printf '%s\n' "$pkgconf_bootstrap_revision" > "$pkgconf_root/.texpdf-revision"
fi
export PATH="$pkgconf_root/bin:$PATH"
echo "TEXPDF_PKGCONF_READY version=$(pkg-config --version) path=$(command -v pkg-config)"

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
patch_vcpkg_ports

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
