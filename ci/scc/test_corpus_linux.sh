#!/bin/bash -l

#$ -P welfgr
#$ -N texpdf_corpus_core
#$ -pe omp 4
#$ -l h_rt=01:00:00
#$ -l mem_per_core=4G
#$ -j y

set -euo pipefail

run_dir=${TEXPDF_SCC_RUN_DIR:?TEXPDF_SCC_RUN_DIR is required}
source_sha=${TEXPDF_SCC_SOURCE_SHA:?TEXPDF_SCC_SOURCE_SHA is required}
code_dir="$run_dir/code"
output_dir="$run_dir/output/corpus"
receipt="$run_dir/receipts/linux-core-corpus.json"

module purge
module load gcc/12.2.0
module load cmake/3.31.7
module load ninja/1.10.2
module load miniconda/25.3.1

python_bin=/share/pkg.8/miniconda/25.3.1/install/bin/python3
export TEXPDF_PYTHON="$python_bin"
export RUSTUP_HOME=/projectnb/welfgr/texpdf/toolchains/rustup
export CARGO_HOME=/projectnb/welfgr/texpdf/toolchains/cargo
export PATH="/share/pkg.8/miniconda/25.3.1/install/bin:$CARGO_HOME/bin:$PATH"
export RUNNER_TEMP="$run_dir/work/core-temp"
export CARGO_TARGET_DIR="$run_dir/work/cargo-target"
export TEXPDF_BUNDLE_CACHE=/projectnb/welfgr/texpdf/cache/bundle
export TEXPDF_VCPKG_ROOT=/projectnb/welfgr/texpdf/cache/vcpkg
export TEXPDF_VCPKG_BINARY_CACHE=/projectnb/welfgr/texpdf/cache/vcpkg-binary
export TEXPDF_PKGCONF_ROOT=/projectnb/welfgr/texpdf/cache/pkgconf
export TEXPDF_CORPUS_OUTPUT="$output_dir/pdfs"
export VCPKG_MAX_CONCURRENCY=${NSLOTS:-4}
export CARGO_BUILD_JOBS=${NSLOTS:-4}
export CARGO_TERM_COLOR=never

mkdir -p "$RUNNER_TEMP" "$CARGO_TARGET_DIR" "$TEXPDF_CORPUS_OUTPUT" "$(dirname "$receipt")"
cd "$code_dir"
test "$(git rev-parse HEAD)" = "$source_sha"
test -z "$(git status --porcelain)"

toolchain=1.97.1
"$CARGO_HOME/bin/rustup" toolchain install "$toolchain" --profile minimal
cargo_bin=$("$CARGO_HOME/bin/rustup" which --toolchain "$toolchain" cargo)
export RUSTC=$("$CARGO_HOME/bin/rustup" which --toolchain "$toolchain" rustc)

"$python_bin" tools/rebuild_curated_bundle.py --cache-dir "$TEXPDF_BUNDLE_CACHE"
source tools/prepare_native_deps_for_target.sh x86_64-unknown-linux-gnu
"$python_bin" ci/check_real_world_corpus.py
"$cargo_bin" test --locked --package texpdf-core --test corpus --jobs "$CARGO_BUILD_JOBS"

"$python_bin" - "$source_sha" "$receipt" "$output_dir" <<'PY'
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import sys

source_sha, receipt_text, output_text = sys.argv[1:]
receipt = Path(receipt_text)
output = Path(output_text)
bundle = json.loads(Path("bundle/generated/bundle-info.json").read_text(encoding="utf-8"))

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

pdfs = []
for path in sorted((output / "pdfs").glob("*.pdf")):
    data = path.read_bytes()
    if not data.startswith(b"%PDF-") or len(data) <= 5000:
        raise SystemExit(f"invalid corpus PDF: {path}")
    pdfs.append({"name": path.name, "size_bytes": len(data), "sha256": sha256(path)})
if len(pdfs) != 3:
    raise SystemExit(f"expected 3 corpus PDFs, found {len(pdfs)}")

payload = {
    "schema_version": 1,
    "status": "success",
    "test": "texpdf-core real-world corpus",
    "tested_source_sha": source_sha,
    "job_id": os.environ.get("JOB_ID", "local"),
    "platform": {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "glibc": subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip(),
    },
    "bundle": {
        "name": bundle["bundle_name"],
        "version": bundle["bundle_version"],
        "content_digest": bundle["tectonic_bundle_digest"],
        "zip_sha256": bundle["zip_sha256"],
    },
    "outputs": pdfs,
    "licensed_stata_run": False,
}
receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

bundle_sha=$(python3 -c 'import json; print(json.load(open("bundle/generated/bundle-info.json"))["zip_sha256"])')
printf 'TEXPDF_SCC_LINUX_CORE_CORPUS_PASS source=%s bundle=%s\n' "$source_sha" "$bundle_sha"
