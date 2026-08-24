#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

/usr/bin/python3 ci/run_license_audit.py
/usr/bin/python3 - <<'PY'
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
