#!/bin/bash
set -euo pipefail

profile="${1:-stress1000}"
iterations="${TEXPDF_STRESS_ITERATIONS:-1000}"
repo_root="$(git rev-parse --show-toplevel)"
evidence_dir="${TEXPDF_MEMORY_EVIDENCE_DIR:-${RUNNER_TEMP:-/private/tmp}/texpdf-memory-stress-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}}"
progress="$evidence_dir/progress.txt"
samples="$evidence_dir/rss-samples.tsv"
summary="$evidence_dir/memory-stress.json"

mkdir -p "$evidence_dir"
: > "$samples"
rm -f "$progress"
export TEXPDF_STRESS_ITERATIONS="$iterations"
export TEXPDF_STRESS_PROGRESS="$progress"

cd "$repo_root"
/bin/bash ci/run_stata_ci.sh "$profile" &
runner_pid=$!
started_epoch="$(/bin/date +%s)"

sample_tree() {
  /usr/bin/python3 - "$runner_pid" "$progress" <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

root = int(sys.argv[1])
progress_path = Path(sys.argv[2])
result = subprocess.run(
    ["/bin/ps", "-axo", "pid=,ppid=,rss=,comm="],
    check=True,
    text=True,
    capture_output=True,
)
rows = []
children: dict[int, list[int]] = {}
rss: dict[int, int] = {}
command: dict[int, str] = {}
for line in result.stdout.splitlines():
    parts = line.strip().split(None, 3)
    if len(parts) < 3:
        continue
    try:
        pid = int(parts[0])
        ppid = int(parts[1])
        resident = int(parts[2])
    except ValueError:
        continue
    children.setdefault(ppid, []).append(pid)
    rss[pid] = resident
    command[pid] = parts[3] if len(parts) == 4 else ""

selected = []
stack = [root]
seen = set()
while stack:
    pid = stack.pop()
    if pid in seen:
        continue
    seen.add(pid)
    if pid in rss:
        selected.append(pid)
    stack.extend(children.get(pid, []))

iteration = 0
try:
    iteration = int(progress_path.read_text(encoding="utf-8").strip())
except (OSError, ValueError):
    pass

stata_rss = sum(
    rss[pid]
    for pid in selected
    if "stata" in command.get(pid, "").lower()
)
tree_rss = sum(rss[pid] for pid in selected)
print(f"{iteration}\t{stata_rss}\t{tree_rss}\t{','.join(map(str, selected))}")
PY
}

while /bin/kill -0 "$runner_pid" 2>/dev/null; do
  timestamp="$(/bin/date +%s)"
  row="$(sample_tree 2>/dev/null || true)"
  if [[ -n "$row" ]]; then
    printf '%s\t%s\n' "$timestamp" "$row" >> "$samples"
  fi
  /bin/sleep 0.2
done

set +e
wait "$runner_pid"
runner_rc=$?
set -e
completed_epoch="$(/bin/date +%s)"

/usr/bin/python3 - "$samples" "$summary" "$iterations" "$runner_rc" "$started_epoch" "$completed_epoch" <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import math
import statistics
import sys

samples_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
iterations = int(sys.argv[3])
runner_rc = int(sys.argv[4])
started = int(sys.argv[5])
completed = int(sys.argv[6])

rows = []
for line in samples_path.read_text(encoding="utf-8").splitlines():
    parts = line.split("\t")
    if len(parts) < 5:
        continue
    try:
        rows.append(
            {
                "timestamp": int(parts[0]),
                "iteration": int(parts[1]),
                "stata_rss_kib": int(parts[2]),
                "tree_rss_kib": int(parts[3]),
                "pids": parts[4],
            }
        )
    except ValueError:
        continue

if not rows:
    raise SystemExit("memory stress collected no process samples")

stata_values = [row["stata_rss_kib"] for row in rows if row["stata_rss_kib"] > 0]
tree_values = [row["tree_rss_kib"] for row in rows if row["tree_rss_kib"] > 0]
if not tree_values:
    raise SystemExit("memory stress collected no RSS values")

iteration_rows = [
    row for row in rows if row["iteration"] > 0 and row["stata_rss_kib"] > 0
]

def window_values(lower: int, upper: int) -> list[int]:
    return [
        row["stata_rss_kib"]
        for row in iteration_rows
        if lower <= row["iteration"] <= upper
    ]

warm_lower = max(1, iterations // 10)
warm_upper = max(warm_lower, iterations // 5)
late_lower = max(1, iterations - max(50, iterations // 10))
warm = window_values(warm_lower, warm_upper)
late = window_values(late_lower, iterations)
warm_median = int(statistics.median(warm)) if warm else None
late_median = int(statistics.median(late)) if late else None
growth_kib = (
    late_median - warm_median
    if warm_median is not None and late_median is not None
    else None
)
growth_ratio = (
    late_median / warm_median
    if warm_median and late_median is not None
    else None
)

# A deliberately loose automated guard catches severe monotone leaks while
# leaving the exact measurements available for engineering review.
max_allowed_growth_kib = 512 * 1024
growth_gate = growth_kib is not None and growth_kib <= max_allowed_growth_kib

payload = {
    "schema_version": 1,
    "iterations_requested": iterations,
    "runner_rc": runner_rc,
    "duration_seconds": completed - started,
    "sample_count": len(rows),
    "stata_sample_count": len(stata_values),
    "peak_stata_rss_kib": max(stata_values) if stata_values else None,
    "peak_tree_rss_kib": max(tree_values),
    "warm_window": [warm_lower, warm_upper],
    "late_window": [late_lower, iterations],
    "warm_median_stata_rss_kib": warm_median,
    "late_median_stata_rss_kib": late_median,
    "post_warmup_growth_kib": growth_kib,
    "post_warmup_growth_ratio": growth_ratio,
    "max_allowed_growth_kib": max_allowed_growth_kib,
    "growth_gate": growth_gate,
}
summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("TEXPDF_MEMORY_STRESS " + " ".join(f"{key}={value}" for key, value in payload.items() if key not in {"schema_version", "warm_window", "late_window"}))
if runner_rc != 0 or not growth_gate:
    raise SystemExit(2)
PY

mkdir -p .ci/stata/run
cp "$samples" .ci/stata/run/rss-samples.tsv
cp "$summary" .ci/stata/run/memory-stress.json
exit "$runner_rc"
