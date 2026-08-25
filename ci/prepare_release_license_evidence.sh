#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

python_bin="${TEXPDF_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$python_bin" ]] || [[ ! -x "$python_bin" ]] || \
   ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "TEXPDF_RELEASE_LICENSE_ERROR Python 3.9 or newer is required" >&2
  exit 2
fi

"$python_bin" ci/run_license_audit.py
"$python_bin" - <<'PY'
from pathlib import Path
import json

status = json.loads(
    Path("licenses/generated/STATUS.json").read_text(encoding="utf-8")
)
if status.get("release_license_complete") is not True:
    raise SystemExit("release license evidence is incomplete")
texts = Path("licenses/generated/texts")
if not texts.is_dir() or not any(path.is_file() for path in texts.rglob("*")):
    raise SystemExit("release license text tree is absent")
print(
    "TEXPDF_RELEASE_LICENSE_EVIDENCE_READY "
    f"source_sha={status.get('source_sha')} "
    f"tex_resources={status.get('tex_resources', {}).get('resource_count')}"
)
PY
