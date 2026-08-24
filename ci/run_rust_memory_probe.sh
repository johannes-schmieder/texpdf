#!/bin/bash
set -euo pipefail

iterations="${TEXPDF_RUST_MEMORY_ITERATIONS:-1000}"
repo_root="$(git rev-parse --show-toplevel)"
rustup_bin="${RUSTUP_BIN:-/opt/homebrew/bin/rustup}"
toolchain="${RUST_TOOLCHAIN:-1.97.1}"
cargo_bin="$($rustup_bin which --toolchain "$toolchain" cargo)"
export RUSTC="$($rustup_bin which --toolchain "$toolchain" rustc)"
export PATH="$(dirname "$cargo_bin"):/opt/homebrew/bin:/usr/local/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/private/tmp/texpdf-cargo-target}"
evidence_dir="${TEXPDF_RUST_MEMORY_EVIDENCE_DIR:-.ci/rust-memory/run}"
progress="$evidence_dir/progress.txt"
samples="$evidence_dir/rss-samples.tsv"
summary="$evidence_dir/rust-memory-probe.json"
probe_log="$evidence_dir/probe.log"

case "$iterations" in
  ''|*[!0-9]*) echo "TEXPDF_RUST_MEMORY_SETUP_ERROR iterations must be an integer" >&2; exit 2 ;;
esac
if (( iterations < 1 || iterations > 10000 )); then
  echo "TEXPDF_RUST_MEMORY_SETUP_ERROR iterations must be between 1 and 10000" >&2
  exit 2
fi

cd "$repo_root"
test -f bundle/generated/texpdf-bundle.zip
test -f bundle/generated/bundle-info.json
rm -rf "$evidence_dir"
mkdir -p "$evidence_dir"
: > "$samples"

source tools/prepare_native_deps.sh
"$cargo_bin" build --locked --release --package texpdf-core --example memory_probe
probe="$CARGO_TARGET_DIR/release/examples/memory_probe"
test -x "$probe"

export TEXPDF_MEMORY_PROBE_PROGRESS="$progress"
export TEXPDF_MEMORY_PROBE_DIR="${RUNNER_TEMP:-/private/tmp}/texpdf-rust-memory-work-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
"$probe" "$iterations" > "$probe_log" 2>&1 &
probe_pid=$!
started_epoch="$(/bin/date +%s)"

sample_process() {
  /usr/bin/python3 - "$probe_pid" "$progress" <<'PY'
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

tree_rss = sum(rss[pid] for pid in selected)
root_rss = rss.get(root, 0)
print(
    f"{iteration}\t{root_rss}\t{tree_rss}\t"
    f"{','.join(map(str, selected))}\t"
    f"{';'.join(command.get(pid, '') for pid in selected)}"
)
PY
}

while /bin/kill -0 "$probe_pid" 2>/dev/null; do
  timestamp="$(/bin/date +%s)"
  row="$(sample_process 2>/dev/null || true)"
  if [[ -n "$row" ]]; then
    printf '%s\t%s\n' "$timestamp" "$row" >> "$samples"
  fi
  /bin/sleep 0.2
done

set +e
wait "$probe_pid"
probe_rc=$?
set -e
completed_epoch="$(/bin/date +%s)"

set +e
/usr/bin/python3 - \
  "$samples" "$summary" "$iterations" "$probe_rc" \
  "$started_epoch" "$completed_epoch" "$probe_log" <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import statistics
import sys

samples_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
iterations = int(sys.argv[3])
probe_rc = int(sys.argv[4])
started = int(sys.argv[5])
completed = int(sys.argv[6])
log_path = Path(sys.argv[7])

rows = []
for line in samples_path.read_text(encoding="utf-8").splitlines():
    parts = line.split("\t")
    if len(parts) < 6:
        continue
    try:
        rows.append(
            {
                "timestamp": int(parts[0]),
                "iteration": int(parts[1]),
                "probe_rss_kib": int(parts[2]),
                "tree_rss_kib": int(parts[3]),
                "pids": parts[4],
                "commands": parts[5],
            }
        )
    except ValueError:
        continue

probe_values = [row["probe_rss_kib"] for row in rows if row["probe_rss_kib"] > 0]
tree_values = [row["tree_rss_kib"] for row in rows if row["tree_rss_kib"] > 0]
iteration_rows = [
    row for row in rows if row["iteration"] > 0 and row["probe_rss_kib"] > 0
]


def window_values(lower: int, upper: int) -> list[int]:
    return [
        row["probe_rss_kib"]
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
    late_median / warm_median if warm_median and late_median is not None else None
)
max_allowed_growth_kib = 512 * 1024
growth_gate = growth_kib is not None and growth_kib <= max_allowed_growth_kib

payload = {
    "schema_version": 1,
    "kind": "Rust-only repeated texpdf-core compilation probe",
    "iterations_requested": iterations,
    "probe_rc": probe_rc,
    "duration_seconds": completed - started,
    "sample_count": len(rows),
    "probe_sample_count": len(probe_values),
    "peak_probe_rss_kib": max(probe_values) if probe_values else None,
    "peak_tree_rss_kib": max(tree_values) if tree_values else None,
    "warm_window": [warm_lower, warm_upper],
    "late_window": [late_lower, iterations],
    "warm_median_probe_rss_kib": warm_median,
    "late_median_probe_rss_kib": late_median,
    "post_warmup_growth_kib": growth_kib,
    "post_warmup_growth_ratio": growth_ratio,
    "max_allowed_growth_kib": max_allowed_growth_kib,
    "growth_gate": growth_gate,
    "probe_log_tail": "\n".join(
        log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
    )[-8000:],
}
summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "TEXPDF_RUST_MEMORY_RESULT "
    + " ".join(
        f"{key}={value}"
        for key, value in payload.items()
        if key not in {"schema_version", "kind", "warm_window", "late_window", "probe_log_tail"}
    )
)
if probe_rc != 0 or not growth_gate:
    raise SystemExit(2)
PY
analyzer_rc=$?
set -e

if [[ $probe_rc -ne 0 ]]; then
  exit "$probe_rc"
fi
exit "$analyzer_rc"
