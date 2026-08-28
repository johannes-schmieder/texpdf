#!/usr/bin/env python3
"""Validate and materialize an exact universal-package memory-test input."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


SHA256 = re.compile(r"[0-9a-f]{64}")
SOURCE_SHA = re.compile(r"[0-9a-f]{40}")


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def require_positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"invalid {label}")
    return value


def safe_relative(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"unsafe package path: {value}")
    return relative


def validate_checksums(package_dir: Path, installed_files: object) -> None:
    if not isinstance(installed_files, list) or not all(
        isinstance(value, str) for value in installed_files
    ):
        raise ValueError("package manifest has an invalid installed_files list")
    installed = {str(safe_relative(value)) for value in installed_files}
    checksum_path = package_dir / "CHECKSUMS.sha256"
    rows: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise ValueError("malformed package checksum line")
        expected, raw_name = parts
        require_sha256(expected, "package checksum")
        name = str(safe_relative(raw_name))
        if name in rows:
            raise ValueError(f"duplicate package checksum path: {name}")
        rows[name] = expected
    expected_names = installed - {"CHECKSUMS.sha256"}
    if set(rows) != expected_names:
        raise ValueError("package checksum inventory does not match installed files")
    for name, expected in rows.items():
        path = (package_dir / name).resolve()
        if not path.is_relative_to(package_dir.resolve()) or not path.is_file():
            raise ValueError(f"missing package file: {name}")
        if digest(path) != expected:
            raise ValueError(f"package checksum mismatch: {name}")


def parse_status(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expect-source-sha", required=True)
    parser.add_argument("--expect-package-version", required=True)
    parser.add_argument("--universal-run-id", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--artifact-digest", required=True)
    args = parser.parse_args()

    if SOURCE_SHA.fullmatch(args.expect_source_sha) is None:
        raise ValueError("invalid expected source SHA")
    if not args.universal_run_id.isdigit() or int(args.universal_run_id) <= 0:
        raise ValueError("invalid universal workflow run ID")
    artifact_digest = args.artifact_digest.removeprefix("sha256:")
    require_sha256(artifact_digest, "workflow artifact digest")

    root = args.artifact_root.resolve()
    universal_dir = root / "dist" / "macos-universal"
    package_dir = universal_dir / "texpdf"
    universal_path = universal_dir / "manifest.json"
    package_path = universal_dir / "package-manifest.json"
    rust_status_path = root / ".ci" / "stata" / "run" / "rust-quick.status"
    bundle_path = root / ".ci" / "stata" / "run" / "bundle-info.json"
    for path in (
        package_dir,
        universal_path,
        package_path,
        rust_status_path,
        bundle_path,
    ):
        if not path.exists():
            raise FileNotFoundError(f"universal artifact input is missing: {path}")

    universal = read_json(universal_path)
    package = read_json(package_path)
    build = read_json(package_dir / "BUILD_INFO.json")
    bundle = read_json(bundle_path)
    if universal.get("schema_version") != 1:
        raise ValueError("unsupported universal manifest schema")
    if universal.get("source_sha") != args.expect_source_sha:
        raise ValueError("universal manifest source does not match the tested source")
    if universal.get("arm_runtime_qualified") is not True:
        raise ValueError(
            "universal artifact lacks its licensed ARM quick qualification"
        )
    if universal.get("intel_runtime_qualified") is not False:
        raise ValueError("universal artifact makes an unexpected Intel runtime claim")
    if set(universal.get("architectures", [])) != {"arm64", "x86_64"}:
        raise ValueError("universal artifact does not contain both required slices")
    if universal.get("exports") != ["pginit", "stata_call"]:
        raise ValueError("universal plugin export inventory is invalid")

    universal_record = universal.get("universal")
    slices = universal.get("slices")
    if not isinstance(universal_record, dict) or not isinstance(slices, dict):
        raise ValueError("universal manifest lacks binary records")
    arm = slices.get("arm64")
    if not isinstance(arm, dict) or not isinstance(arm.get("embedded_helper"), dict):
        raise ValueError("universal manifest lacks ARM helper provenance")
    helper = arm["embedded_helper"]
    helper_sha = require_sha256(helper.get("sha256"), "ARM helper SHA-256")
    helper_size = require_positive_int(helper.get("size_bytes"), "ARM helper size")
    if helper.get("target") != "aarch64-apple-darwin":
        raise ValueError("universal manifest ARM helper target is invalid")

    plugin_name = "_texpdf_plugin_macosx.plugin"
    plugin_path = package_dir / plugin_name
    plugin_sha = require_sha256(
        universal_record.get("sha256"), "universal plugin SHA-256"
    )
    plugin_size = require_positive_int(
        universal_record.get("size_bytes"), "universal plugin size"
    )
    if digest(plugin_path) != plugin_sha or plugin_path.stat().st_size != plugin_size:
        raise ValueError("universal package plugin does not match its manifest")

    required_package_values = {
        "schema_version": 1,
        "package_version": args.expect_package_version,
        "target": "universal2-apple-darwin",
        "installed_plugin": plugin_name,
        "plugin_sha256": plugin_sha,
        "plugin_size_bytes": plugin_size,
        "public_release_mode": True,
        "license_evidence_included": True,
        "release_license_complete": True,
        "license_audit_source_sha": args.expect_source_sha,
        "embedded_helper_count": 2,
    }
    for key, expected in required_package_values.items():
        if package.get(key) != expected:
            raise ValueError(f"universal package manifest has invalid {key}")
        if build.get(key) != expected:
            raise ValueError(f"universal BUILD_INFO has invalid {key}")
    helpers = package.get("embedded_helpers")
    if not isinstance(helpers, dict) or helpers.get("aarch64-apple-darwin") != {
        "sha256": helper_sha,
        "size_bytes": helper_size,
    }:
        raise ValueError("package helper inventory does not match the ARM slice")
    if build.get("embedded_helpers") != helpers:
        raise ValueError("BUILD_INFO and package manifest helper inventories differ")

    for key, value in build.items():
        if package.get(key) != value:
            raise ValueError(f"BUILD_INFO and package manifest differ at {key}")
    bundle_sha = require_sha256(package.get("bundle_zip_sha256"), "bundle ZIP SHA-256")
    if bundle.get("zip_sha256") != bundle_sha:
        raise ValueError("package and Rust evidence bundle identities differ")
    validate_checksums(package_dir, package.get("installed_files"))

    zip_name = package.get("package_zip")
    if not isinstance(zip_name, str):
        raise ValueError("package manifest lacks package_zip")
    zip_path = universal_dir / safe_relative(zip_name)
    zip_sha = require_sha256(package.get("package_zip_sha256"), "package ZIP SHA-256")
    zip_size = require_positive_int(
        package.get("package_zip_size_bytes"), "package ZIP size"
    )
    if digest(zip_path) != zip_sha or zip_path.stat().st_size != zip_size:
        raise ValueError("universal package ZIP does not match its manifest")

    rust_status = parse_status(rust_status_path)
    if not (
        rust_status.get("rust_status") == "success"
        and rust_status.get("rust_mode") == "repository-engine"
        and rust_status.get("completed") == "1"
    ):
        raise ValueError(
            "universal artifact lacks successful full-engine Rust evidence"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    runtime_package = {
        **package,
        "source_sha": args.expect_source_sha,
        "target": "aarch64-apple-darwin",
        "embedded_helper_sha256": helper_sha,
        "embedded_helper_size_bytes": helper_size,
        "qualification_input_run_id": int(args.universal_run_id),
        "qualification_input_artifact": args.artifact_name,
        "qualification_input_artifact_digest": artifact_digest,
    }
    plugin_manifest = {
        "schema_version": 1,
        "sha256": plugin_sha,
        "size_bytes": plugin_size,
        "target": "universal2-apple-darwin",
        "exports": universal["exports"],
        "external_dynamic_dependencies": universal.get("dynamic_dependencies", []),
    }
    helper_manifest = {
        "schema_version": 1,
        "sha256": helper_sha,
        "size_bytes": helper_size,
        "target": "aarch64-apple-darwin",
    }
    provenance = {
        "schema_version": 1,
        "source_sha": args.expect_source_sha,
        "universal_run_id": int(args.universal_run_id),
        "artifact_name": args.artifact_name,
        "artifact_digest": artifact_digest,
        "package_version": args.expect_package_version,
        "package_zip_sha256": zip_sha,
        "package_zip_size_bytes": zip_size,
        "plugin_sha256": plugin_sha,
        "plugin_size_bytes": plugin_size,
        "arm_helper_sha256": helper_sha,
        "arm_helper_size_bytes": helper_size,
        "bundle_zip_sha256": bundle_sha,
    }
    write_json(args.output_dir / "package-manifest.json", runtime_package)
    write_json(args.output_dir / "plugin-manifest.json", plugin_manifest)
    write_json(args.output_dir / "helper-manifest.json", helper_manifest)
    write_json(args.output_dir / "memory-input.json", provenance)
    shutil.copy2(bundle_path, args.output_dir / "bundle-info.json")
    shutil.copy2(rust_status_path, args.output_dir / "rust-quick.status")
    print(
        "TEXPDF_MACOS_MEMORY_INPUT_READY "
        f"source={args.expect_source_sha} run_id={args.universal_run_id} "
        f"package_sha256={zip_sha} plugin_sha256={plugin_sha} "
        f"helper_sha256={helper_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
