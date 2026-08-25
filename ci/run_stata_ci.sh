#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
python_bin="${TEXPDF_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$python_bin" ]] || [[ ! -x "$python_bin" ]]; then
  echo "TEXPDF_STATA_CI_ERROR Python 3.9 or newer is required" >&2
  exit 127
fi
exec "$python_bin" "$script_dir/run_stata_ci.py" "${1:-quick}"
