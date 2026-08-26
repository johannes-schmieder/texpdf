#!/bin/bash -l

#$ -P welfgr
#$ -N texpdf_linux_build
#$ -pe omp 4
#$ -l h_rt=01:00:00
#$ -l mem_per_core=4G
#$ -j y

set -euo pipefail

run_dir=${TEXPDF_SCC_RUN_DIR:?TEXPDF_SCC_RUN_DIR is required}
source_sha=${TEXPDF_SCC_SOURCE_SHA:?TEXPDF_SCC_SOURCE_SHA is required}
candidate_version=${TEXPDF_CANDIDATE_VERSION:?TEXPDF_CANDIDATE_VERSION is required}
code_dir="$run_dir/code"
output_dir="$run_dir/output/linux-build"
receipt="$run_dir/receipts/linux-build.json"

module purge
module load gcc/12.2.0
module load cmake/3.31.7
module load ninja/1.10.2
module load miniconda/25.3.1

python_bin=/share/pkg.8/miniconda/25.3.1/install/bin/python3
test -x "$python_bin"
export TEXPDF_PYTHON="$python_bin"
export RUSTUP_HOME=/projectnb/welfgr/texpdf/toolchains/rustup
export CARGO_HOME=/projectnb/welfgr/texpdf/toolchains/cargo
export PATH="/share/pkg.8/miniconda/25.3.1/install/bin:$CARGO_HOME/bin:$PATH"
export RUNNER_TEMP="$run_dir/work/build-temp"
export CARGO_TARGET_DIR="$run_dir/work/cargo-target"
export TEXPDF_BUNDLE_CACHE=/projectnb/welfgr/texpdf/cache/bundle
export TEXPDF_VCPKG_ROOT=/projectnb/welfgr/texpdf/cache/vcpkg
export TEXPDF_VCPKG_BINARY_CACHE=/projectnb/welfgr/texpdf/cache/vcpkg-binary
export TEXPDF_PKGCONF_ROOT=/projectnb/welfgr/texpdf/cache/pkgconf
export VCPKG_MAX_CONCURRENCY=${NSLOTS:-4}
export CARGO_BUILD_JOBS=${NSLOTS:-4}
export CARGO_TERM_COLOR=never
export RUST_BACKTRACE=1

mkdir -p "$RUNNER_TEMP" "$CARGO_TARGET_DIR" "$output_dir" "$(dirname "$receipt")"
cd "$code_dir"
test "$(git rev-parse HEAD)" = "$source_sha"
test -z "$(git status --porcelain)"

toolchain=1.97.1
"$CARGO_HOME/bin/rustup" toolchain install "$toolchain" \
  --profile minimal --component rustfmt,clippy
cargo_bin=$("$CARGO_HOME/bin/rustup" which --toolchain "$toolchain" cargo)
export RUSTC=$("$CARGO_HOME/bin/rustup" which --toolchain "$toolchain" rustc)

"$python_bin" tools/rebuild_curated_bundle.py --cache-dir "$TEXPDF_BUNDLE_CACHE"
source tools/prepare_native_deps_for_target.sh x86_64-unknown-linux-gnu

"$cargo_bin" fmt --all --check
"$cargo_bin" build --locked --release --package texpdf-helper \
  --target x86_64-unknown-linux-gnu --jobs "$CARGO_BUILD_JOBS"
export TEXPDF_HELPER_PATH="$CARGO_TARGET_DIR/x86_64-unknown-linux-gnu/release/texpdf-helper"
test -x "$TEXPDF_HELPER_PATH"
"$cargo_bin" clippy --locked --workspace --all-targets --all-features \
  --jobs "$CARGO_BUILD_JOBS" -- -D warnings
"$cargo_bin" test --locked --workspace --all-targets --all-features \
  --jobs "$CARGO_BUILD_JOBS"
"$cargo_bin" build --locked --release --package texpdf-stata \
  --target x86_64-unknown-linux-gnu --jobs "$CARGO_BUILD_JOBS"

mkdir -p dist/linux-x86_64
plugin=dist/linux-x86_64/_texpdf_plugin_unix.plugin
cp "$CARGO_TARGET_DIR/x86_64-unknown-linux-gnu/release/libtexpdf_stata.so" "$plugin"
"$python_bin" tools/check_plugin_binary.py "$plugin" --platform linux \
  --maximum-glibc 2.28 --output dist/linux-x86_64/binary-policy.json
"$python_bin" tools/plugin_smoke.py "$plugin" \
  --bundle-info bundle/generated/bundle-info.json \
  --output dist/linux-x86_64/plugin-smoke.json
GITHUB_SHA="$source_sha" /bin/bash ci/prepare_release_license_evidence.sh
"$python_bin" tools/package_release.py \
  --plugin "$plugin" \
  --embedded-helper "$TEXPDF_HELPER_PATH" \
  --bundle-info bundle/generated/bundle-info.json \
  --output-dir dist/texpdf-linux-x86_64 \
  --zip dist/texpdf-linux-x86_64.zip \
  --manifest dist/linux-x86_64/package-manifest.json \
  --target x86_64-unknown-linux-gnu \
  --package-version "$candidate_version" \
  --public-release

cp "$plugin" "$output_dir/"
cp dist/linux-x86_64/binary-policy.json "$output_dir/"
cp dist/linux-x86_64/plugin-smoke.json "$output_dir/"
cp dist/linux-x86_64/package-manifest.json "$output_dir/"
cp dist/texpdf-linux-x86_64.zip "$output_dir/"
cp -R dist/texpdf-linux-x86_64 "$output_dir/package"
cp bundle/generated/bundle-info.json "$output_dir/"

"$python_bin" ci/scc/write_linux_build_receipt.py \
  --source-sha "$source_sha" \
  --job-id "${JOB_ID:-local}" \
  --plugin "$output_dir/_texpdf_plugin_unix.plugin" \
  --helper "$TEXPDF_HELPER_PATH" \
  --package "$output_dir/texpdf-linux-x86_64.zip" \
  --package-manifest "$output_dir/package-manifest.json" \
  --binary-policy "$output_dir/binary-policy.json" \
  --plugin-smoke "$output_dir/plugin-smoke.json" \
  --receipt "$receipt"

printf 'TEXPDF_SCC_LINUX_BUILD_PASS source=%s package_version=%s\n' \
  "$source_sha" "$candidate_version"
