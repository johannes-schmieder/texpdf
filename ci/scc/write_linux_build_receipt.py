#!/usr/bin/env python3
"""Write the compact, source-bound SCC Linux build receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--binary-policy", type=Path, required=True)
    parser.add_argument("--plugin-smoke", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    manifest = load(args.package_manifest)
    policy = load(args.binary_policy)
    smoke = load(args.plugin_smoke)
    identities = {
        "plugin_sha256": sha256(args.plugin),
        "helper_sha256": sha256(args.helper),
        "package_sha256": sha256(args.package),
    }
    expected = {
        "plugin_sha256": manifest.get("plugin_sha256"),
        "helper_sha256": manifest.get("embedded_helper_sha256"),
        "package_sha256": manifest.get("package_zip_sha256"),
    }
    if identities != expected:
        raise ValueError(f"artifact identity mismatch: actual={identities} expected={expected}")
    if policy.get("violations") != [] or smoke.get("compile") != "success":
        raise ValueError("binary policy or plugin smoke did not pass")

    payload = {
        "schema_version": 1,
        "status": "success",
        "source_sha": args.source_sha,
        "job_id": args.job_id,
        "host": os.environ.get("HOSTNAME"),
        "slots": int(os.environ.get("NSLOTS", "1")),
        "platform": platform.platform(),
        "glibc": platform.libc_ver(),
        "rustc": subprocess.check_output([os.environ["RUSTC"], "--version"], text=True).strip(),
        "rust_tests": "success",
        "cargo_target_seed": "fresh-empty-run-directory",
        "plugin_sha256": identities["plugin_sha256"],
        "plugin_size_bytes": args.plugin.stat().st_size,
        "helper_sha256": identities["helper_sha256"],
        "helper_size_bytes": args.helper.stat().st_size,
        "package_sha256": identities["package_sha256"],
        "package_size_bytes": args.package.stat().st_size,
        "package_manifest": manifest,
        "binary_policy": policy,
        "plugin_smoke": smoke,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
