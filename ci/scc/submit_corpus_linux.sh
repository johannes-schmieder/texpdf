#!/bin/bash -l

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: ci/scc/submit_corpus_linux.sh RUN_DIR" >&2
  exit 2
fi
run_dir=$1
code_dir="$run_dir/code"
source_sha=$(git -C "$code_dir" rev-parse HEAD)
mkdir -p "$run_dir/logs" "$run_dir/output" "$run_dir/receipts" "$run_dir/work"

job_id=$(qsub -terse -P welfgr -o "$run_dir/logs/linux-core-corpus.log" \
  -v "TEXPDF_SCC_RUN_DIR=$run_dir,TEXPDF_SCC_SOURCE_SHA=$source_sha" \
  "$code_dir/ci/scc/test_corpus_linux.sh")
job_id=${job_id%%.*}
printf '{"source_sha":"%s","linux_core_corpus":"%s"}\n' "$source_sha" "$job_id" \
  > "$run_dir/receipts/jobs.json"
printf 'TEXPDF_SCC_CORPUS_SUBMITTED job=%s source=%s\n' "$job_id" "$source_sha"
