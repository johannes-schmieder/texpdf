#!/usr/bin/env python3
"""Import validated Windows runtime evidence into release records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def compact_package(manifest: dict[str, object]) -> dict[str, object]:
    keys = (
        "package_version",
        "target",
        "installed_plugin",
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
    build = load(receipts / "windows-build.json")
    environment = load(receipts / "windows-environment.json")
    runtimes = {
        "stata_19_quick": load(receipts / "stata-19-quick/receipt.json"),
        "stata_19_stress1000": load(receipts / "stata-19-stress1000/receipt.json"),
    }
    source_sha = str(build.get("source_sha", ""))
    if not SHA.fullmatch(source_sha) or build.get("status") != "success":
        raise ValueError("Windows build receipt is not exact and successful")
    if (
        environment.get("status") != "success"
        or environment.get("source_sha") != source_sha
        or environment.get("system_tex_required") is not False
        or environment.get("system_tex_commands_on_path") != []
        or environment.get("stata_version") != "19"
        or environment.get("stata_edition") != "MP"
    ):
        raise ValueError("Windows environment receipt is unsafe or belongs to another source")
    manifest = build.get("package_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("Windows build receipt has no package manifest")
    package = compact_package(manifest)
    for key in ("package_zip_sha256", "plugin_sha256", "embedded_helper_sha256", "bundle_zip_sha256"):
        if not SHA256.fullmatch(str(package.get(key, ""))):
            raise ValueError(f"Windows package identity is invalid: {key}")
    for key, profile in (("stata_19_quick", "quick"), ("stata_19_stress1000", "stress1000")):
        receipt = runtimes[key]
        artifact = receipt.get("artifact")
        markers = receipt.get("required_log_markers", [])
        present = {
            str(item.get("marker"))
            for item in markers
            if isinstance(item, dict) and item.get("present") is True
        }
        expected_markers = (
            {"TEXPDF STRESS 1000 PASS"}
            if profile == "stress1000"
            else {
                "TEXPDF REALISTIC CORPUS PASS",
                "TEXPDF HELP EXAMPLES PASS",
                "TEXPDF FULL ENGINE STATA PASS",
            }
        )
        if (
            receipt.get("tested_sha") != source_sha
            or receipt.get("status") != "success"
            or receipt.get("stata_status") != "success"
            or receipt.get("profile") != profile
            or str(receipt.get("stata_version", "")).split(".", 1)[0] != "19"
            or receipt.get("stata_edition") != "MP"
            or "Windows" not in str(receipt.get("platform", ""))
            or not isinstance(artifact, dict)
            or artifact.get("plugin_sha256") != package["plugin_sha256"]
            or artifact.get("package_zip_sha256") != package["package_zip_sha256"]
            or artifact.get("bundle_zip_sha256") != package["bundle_zip_sha256"]
            or not expected_markers <= present
        ):
            raise ValueError(f"Windows runtime receipt mismatch: {key}")

    record = {
        "schema_version": 1,
        "qualified": True,
        "source_sha": source_sha,
        "target": "x86_64-pc-windows-msvc",
        "tested_stata_versions": ["19"],
        "build_receipt": build,
        "package": package,
        "runtimes": runtimes,
        "environment": environment,
    }
    args.release_dir.mkdir(parents=True, exist_ok=True)
    record_path = args.release_dir / "windows-x86_64.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    targets_path = args.release_dir / "targets.json"
    registry = load(targets_path)
    target = registry.setdefault("targets", {}).setdefault("x86_64-pc-windows-msvc", {})
    target.update(
        {
            "artifact": "_texpdf_plugin_windows.plugin",
            "build_qualified": True,
            "build_source_sha": source_sha,
            "qualified_source_sha": source_sha,
            "stata_runtime_qualified": True,
            "tested_stata_versions": ["19"],
            "plugin_sha256": package["plugin_sha256"],
            "plugin_size_bytes": package["plugin_size_bytes"],
            "embedded_helper_sha256": package["embedded_helper_sha256"],
            "embedded_helper_size_bytes": package["embedded_helper_size_bytes"],
            "bundle_zip_sha256": package["bundle_zip_sha256"],
            "bundle_zip_size_bytes": package["bundle_zip_size_bytes"],
            "candidate_package_sha256": package["package_zip_sha256"],
            "candidate_package_size_bytes": package["package_zip_size_bytes"],
            "candidate_package_version": package["package_version"],
            "receipt": "release/windows-x86_64.json",
            "status": "qualified in licensed Stata/MP 19 on Windows x86-64 with system TeX absent",
        }
    )
    targets_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEXPDF_WINDOWS_QUALIFICATION_IMPORTED source={source_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
