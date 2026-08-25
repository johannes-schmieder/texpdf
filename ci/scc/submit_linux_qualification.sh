#!/bin/bash -l

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: ci/scc/submit_linux_qualification.sh RUN_DIR" >&2
  exit 2
fi
run_dir=$1
code_dir="$run_dir/code"
source_sha=$(git -C "$code_dir" rev-parse HEAD)
candidate_version=$(/share/pkg.8/miniconda/25.3.1/install/bin/python3 - \
  "$code_dir/release/scope.json" <<'PY'
import json
from pathlib import Path
import sys
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["candidate_version"])
PY
)
mkdir -p "$run_dir/logs" "$run_dir/output" "$run_dir/receipts" "$run_dir/work"

common="TEXPDF_SCC_RUN_DIR=$run_dir,TEXPDF_SCC_SOURCE_SHA=$source_sha"
build_id=$(qsub -terse -P welfgr -o "$run_dir/logs/linux-build.log" \
  -v "$common,TEXPDF_CANDIDATE_VERSION=$candidate_version" \
  "$code_dir/ci/scc/build_linux.sh")
build_id=${build_id%%.*}
quick18_id=$(qsub -terse -P welfgr -hold_jid "$build_id" -l h_rt=00:45:00 \
  -o "$run_dir/logs/stata-18-quick.log" \
  -v "$common,TEXPDF_SCC_PROFILE=quick,TEXPDF_SCC_STATA_VERSION=18" \
  "$code_dir/ci/scc/run_stata_linux.sh")
quick18_id=${quick18_id%%.*}
stress18_id=$(qsub -terse -P welfgr -hold_jid "$build_id" -l h_rt=02:00:00 \
  -o "$run_dir/logs/stata-18-stress1000.log" \
  -v "$common,TEXPDF_SCC_PROFILE=stress1000,TEXPDF_SCC_STATA_VERSION=18" \
  "$code_dir/ci/scc/run_stata_linux.sh")
stress18_id=${stress18_id%%.*}
quick19_id=$(qsub -terse -P welfgr -hold_jid "$build_id" -l h_rt=00:45:00 \
  -o "$run_dir/logs/stata-19-quick.log" \
  -v "$common,TEXPDF_SCC_PROFILE=quick,TEXPDF_SCC_STATA_VERSION=19" \
  "$code_dir/ci/scc/run_stata_linux.sh")
quick19_id=${quick19_id%%.*}

printf '{"source_sha":"%s","candidate_version":"%s","build":"%s","stata_18_quick":"%s","stata_18_stress1000":"%s","stata_19_quick":"%s"}\n' \
  "$source_sha" "$candidate_version" "$build_id" "$quick18_id" "$stress18_id" "$quick19_id" \
  > "$run_dir/receipts/jobs.json"
printf 'TEXPDF_SCC_SUBMITTED build=%s stata18quick=%s stata18stress=%s stata19quick=%s\n' \
  "$build_id" "$quick18_id" "$stress18_id" "$quick19_id"
