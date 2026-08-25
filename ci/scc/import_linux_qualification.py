#!/usr/bin/env python3
"""Import validated SCC Linux receipts into the canonical release records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def compact_package(manifest: dict[str, object]) -> dict[str, object]:
    keys = (
        "package_version",
        "target",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "plugin_sha256",
        "plugin_size_bytes",
        "embedded_helper_sha256",
        "embedded_helper_size_bytes",
        "bundle_zip_sha256",
        "bundle_zip_size_bytes",
        "license_evidence_included",
        "release_license_complete",
        "license_audit_source_sha",
        "public_release_mode",
    )
    return {key: manifest.get(key) for key in keys}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--release-dir", type=Path, default=Path("release"))
    args = parser.parse_args()
    receipts = args.run / "receipts"
    build = load(receipts / "linux-build.json")
    scheduler = load(receipts / "scheduler.json")
    runtime_paths = {
        "stata_18_quick": receipts / "stata-18-quick/receipt.json",
        "stata_18_stress1000": receipts / "stata-18-stress1000/receipt.json",
        "stata_19_quick": receipts / "stata-19-quick/receipt.json",
    }
    runtimes = {key: load(path) for key, path in runtime_paths.items()}
    source_sha = str(build.get("source_sha", ""))
    if not SHA.fullmatch(source_sha):
        raise ValueError("Linux build receipt has no valid source SHA")
    if scheduler.get("status") != "success" or scheduler.get("source_sha") != source_sha:
        raise ValueError("scheduler evidence does not match the successful build")
    manifest = build.get("package_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("build receipt has no package manifest")
    package = compact_package(manifest)
    for key in ("package_zip_sha256", "plugin_sha256", "embedded_helper_sha256", "bundle_zip_sha256"):
        if not SHA256.fullmatch(str(package.get(key, ""))):
            raise ValueError(f"package identity is invalid: {key}")
    for key, receipt in runtimes.items():
        if receipt.get("tested_sha") != source_sha or receipt.get("status") != "success":
            raise ValueError(f"runtime receipt is not successful for the exact source: {key}")
        artifact = receipt.get("artifact")
        if not isinstance(artifact, dict):
            raise ValueError(f"runtime receipt has no artifact identity: {key}")
        expected = {
            "plugin_sha256": package["plugin_sha256"],
            "package_zip_sha256": package["package_zip_sha256"],
            "bundle_zip_sha256": package["bundle_zip_sha256"],
        }
        if any(artifact.get(name) != value for name, value in expected.items()):
            raise ValueError(f"runtime artifact mismatch: {key}")

    record = {
        "schema_version": 1,
        "qualified": True,
        "source_sha": source_sha,
        "target": "x86_64-unknown-linux-gnu",
        "minimum_glibc": "2.28",
        "tested_stata_versions": ["18", "19"],
        "build_receipt": build,
        "package": package,
        "runtimes": runtimes,
        "scheduler": scheduler,
    }
    args.release_dir.mkdir(parents=True, exist_ok=True)
    linux_path = args.release_dir / "linux-x86_64.json"
    linux_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    targets_path = args.release_dir / "targets.json"
    registry = load(targets_path)
    target = registry.setdefault("targets", {}).setdefault("x86_64-unknown-linux-gnu", {})
    target.update(
        {
            "artifact": "_texpdf_plugin.plugin",
            "build_qualified": True,
            "build_source_sha": source_sha,
            "qualified_source_sha": source_sha,
            "stata_runtime_qualified": True,
            "tested_stata_versions": ["18", "19"],
            "minimum_glibc": "2.28",
            "plugin_sha256": package["plugin_sha256"],
            "plugin_size_bytes": package["plugin_size_bytes"],
            "embedded_helper_sha256": package["embedded_helper_sha256"],
            "embedded_helper_size_bytes": package["embedded_helper_size_bytes"],
            "bundle_zip_sha256": package["bundle_zip_sha256"],
            "bundle_zip_size_bytes": package["bundle_zip_size_bytes"],
            "candidate_package_sha256": package["package_zip_sha256"],
            "candidate_package_size_bytes": package["package_zip_size_bytes"],
            "candidate_package_version": package["package_version"],
            "receipt": "release/linux-x86_64.json",
            "status": "qualified on RHEL 8 / glibc 2.28 in licensed Stata/MP 18 and 19",
        }
    )
    targets_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEXPDF_LINUX_QUALIFICATION_IMPORTED source={source_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
