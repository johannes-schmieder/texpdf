#!/bin/bash -l

#$ -P welfgr
#$ -N texpdf_linux_stata
#$ -pe omp 4
#$ -l mem_per_core=2G
#$ -j y

set -euo pipefail

run_dir=${TEXPDF_SCC_RUN_DIR:?TEXPDF_SCC_RUN_DIR is required}
source_sha=${TEXPDF_SCC_SOURCE_SHA:?TEXPDF_SCC_SOURCE_SHA is required}
profile=${TEXPDF_SCC_PROFILE:?TEXPDF_SCC_PROFILE is required}
stata_version=${TEXPDF_SCC_STATA_VERSION:?TEXPDF_SCC_STATA_VERSION is required}
code_dir="$run_dir/code"
build_dir="$run_dir/output/linux-build"
evidence_dir="$run_dir/receipts/stata-${stata_version}-${profile}"

case "$profile:$stata_version" in
  quick:18|quick:19|stress1000:18) ;;
  *) echo "unsupported Linux qualification pair: $profile / Stata $stata_version" >&2; exit 2 ;;
esac

module purge
module load miniconda/25.3.1
module load "stata-mp/$stata_version"
python_bin=/share/pkg.8/miniconda/25.3.1/install/bin/python3
stata_bin=$(command -v stata-mp)

"$python_bin" - "$run_dir/receipts/linux-build.json" "$source_sha" <<'PY'
from pathlib import Path
import json
import sys
value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if value.get("status") != "success" or value.get("source_sha") != sys.argv[2]:
    raise SystemExit("Linux build receipt is absent, failed, or for another source SHA")
PY

export TEXPDF_PYTHON="$python_bin"
export STATA_BIN="$stata_bin"
export TEXPDF_STATA_PLUGIN="$build_dir/_texpdf_plugin.plugin"
export TEXPDF_STATA_PACKAGE_DIR="$build_dir/package"
export TEXPDF_STATA_PACKAGE_MANIFEST="$build_dir/package-manifest.json"
export GITHUB_SHA="$source_sha"
export GITHUB_REPOSITORY=johannes-schmieder/texpdf
export GITHUB_REF="refs/heads/main"
export GITHUB_RUN_ID="${JOB_ID:-scc-local}"
export GITHUB_RUN_ATTEMPT=1
export RUNNER_NAME="${HOSTNAME:-scc}"
export RUNNER_TEMP="$run_dir/work/stata-${stata_version}-${profile}-temp"
export STATA_CI_LOCK_FILE=/projectnb/welfgr/texpdf/stata-ci.lock

mkdir -p "$RUNNER_TEMP" "$evidence_dir"
cd "$code_dir"
"$python_bin" ci/run_stata_ci.py "$profile"
"$python_bin" ci/check_stata_receipt.py .ci/stata/run/receipt.json \
  --expect-tested-sha "$source_sha" --expect-profile "$profile" --require-success
cp -R .ci/stata/run/. "$evidence_dir/"
printf 'TEXPDF_SCC_STATA_PASS source=%s version=%s profile=%s\n' \
  "$source_sha" "$stata_version" "$profile"
