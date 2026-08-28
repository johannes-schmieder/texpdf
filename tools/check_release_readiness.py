#!/usr/bin/env python3
"""Audit texpdf implementation and public-release readiness.

This tool is deliberately fail-closed. A file's presence is never enough: all
source, artifact, target, license, and stress records must carry internally
consistent status fields and exact hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_PACKAGE_FILES = (
    "stata/texpdf.ado",
    "stata/texpdf.sthlp",
    "stata/texpdf_run.ado",
    "stata/texpdf.pkg",
    "stata/stata.toc",
)
TARGETS_PATH = Path("release/targets.json")
UNIVERSAL_PATH = Path("release/macos-universal.json")
LINUX_RUNTIME_PATH = Path("release/linux-x86_64.json")
WINDOWS_RUNTIME_PATH = Path("release/windows-x86_64.json")
WINDOWS_RUNTIME_EQUIVALENCE_PATH = Path("release/windows-runtime-equivalence.json")
MEMORY_PATH = Path("release/memory-stress-macos-arm64.json")
LICENSE_STATUS_PATH = Path("licenses/generated/STATUS.json")
SCOPE_PATH = Path("release/scope.json")
PUBLICATION_PATH = Path("release/publication.json")
EVIDENCE_ONLY_PREFIXES = (".ci/", "docs/generated/", "licenses/generated/")
EVIDENCE_ONLY_FILES = {
    "STATUS.md",
    "bundle/QUALIFICATION.json",
    "release/READINESS.json",
    "release/READINESS.md",
    "release/macos-universal.json",
    "release/memory-probe-rust-macos-arm64.json",
    "release/memory-stress-macos-arm64.json",
    "release/targets.json",
}
WINDOWS_RUNTIME_EQUIVALENCE_FILES = {
    "CHANGELOG.md",
    "PLAN.md",
    "README.md",
    "STATUS.md",
    "bundle/QUALIFICATION.json",
    "stata/texpdf.ado",
    "stata/texpdf.pkg",
    "stata/texpdf.sthlp",
    "tools/check_release_readiness.py",
    "tools/package_release.py",
    "tools/sync_project_state.py",
}
WINDOWS_RUNTIME_EQUIVALENCE_PREFIXES = (
    ".ci/",
    "ci/tests/",
    "docs/generated/",
    "licenses/generated/",
    "release/",
)


class AuditError(RuntimeError):
    """A malformed repository record."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise AuditError(f"{path} does not contain a JSON object")
    return value


def add_check(
    checks: list[dict[str, Any]],
    key: str,
    passed: bool,
    detail: str,
    release_blocker: bool = True,
    public_release_blocker: bool | None = None,
) -> None:
    failed = not passed
    if public_release_blocker is None:
        public_release_blocker = release_blocker
    checks.append(
        {
            "key": key,
            "passed": bool(passed),
            "detail": detail,
            "release_blocker": bool(release_blocker and failed),
            "candidate_release_blocker": bool(release_blocker and failed),
            "public_release_blocker": bool(public_release_blocker and failed),
        }
    )


def valid_sha256(value: object) -> bool:
    return SHA256_RE.fullmatch(str(value or "")) is not None


def valid_source_sha(value: object) -> bool:
    return SOURCE_SHA_RE.fullmatch(str(value or "")) is not None


def evidence_only_path(path: str) -> bool:
    return path in EVIDENCE_ONLY_FILES or path.startswith(EVIDENCE_ONLY_PREFIXES)


def windows_runtime_equivalence_path(path: str) -> bool:
    return path in WINDOWS_RUNTIME_EQUIVALENCE_FILES or path.startswith(
        WINDOWS_RUNTIME_EQUIVALENCE_PREFIXES
    )


def git_bytes(revision: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{revision}:{path}"])


def normalized_stata_metadata(revision: str, path: str) -> bytes:
    lines = git_bytes(revision, path).splitlines(keepends=True)
    if path == "stata/texpdf.ado":
        return b"".join(lines[1:])
    if path == "stata/texpdf.sthlp":
        return b"".join(lines[:1] + lines[2:])
    if path == "stata/texpdf.pkg":
        return b"".join(
            line for line in lines if not line.startswith(b"d Distribution-Date:")
        )
    raise ValueError(f"unsupported Stata metadata path: {path}")


def validate_windows_runtime_equivalence(
    data: dict[str, Any],
    historical: dict[str, Any],
    target: dict[str, Any],
    candidate_version: str,
    public_release: bool,
) -> tuple[bool, str]:
    candidate_source = str(data.get("candidate_source_sha", ""))
    runtime_source = str(data.get("runtime_evidence_source_sha", ""))
    final_build = data.get("final_build", {})
    final_package = final_build.get("package", {}) if isinstance(final_build, dict) else {}
    historical_package = historical.get("package", {})
    historical_runtimes = historical.get("runtimes", {})
    diff = data.get("source_diff", {})
    diagnostic = data.get("final_runtime_attempt", {})

    if not (
        data.get("schema_version") == 1
        and data.get("approved_by_owner") is True
        and valid_source_sha(candidate_source)
        and valid_source_sha(runtime_source)
        and candidate_source != runtime_source
        and historical.get("schema_version") == 1
        and historical.get("qualified") is True
        and historical.get("source_sha") == runtime_source
        and historical.get("target") == "x86_64-pc-windows-msvc"
        and isinstance(final_build, dict)
        and final_build.get("status") == "success"
        and final_build.get("source_sha") == candidate_source
        and final_build.get("rust_tests") == "success"
        and final_build.get("target") == "x86_64-pc-windows-msvc"
        and final_build.get("static_msvc_crt") is True
        and final_build.get("binary_policy_violations") == []
        and isinstance(final_package, dict)
        and final_package.get("package_version") == candidate_version
        and final_package.get("public_release_mode") is public_release
        and final_package.get("license_audit_source_sha") == candidate_source
        and final_package.get("release_license_complete") is True
        and final_package.get("license_evidence_included") is True
        and final_package.get("target") == "x86_64-pc-windows-msvc"
        and final_package.get("installed_plugin") == "_texpdf_plugin_windows.plugin"
        and all(
            valid_sha256(final_package.get(key))
            for key in (
                "package_zip_sha256",
                "plugin_sha256",
                "embedded_helper_sha256",
                "bundle_zip_sha256",
            )
        )
        and diagnostic.get("status") == "FAIL"
        and diagnostic.get("error_code") == "STATA_DRIVER_FAILED"
        and diagnostic.get("instance_stopped") is True
        and diagnostic.get("transient_objects_deleted") is True
        and diagnostic.get("lock_released") is True
    ):
        return False, "equivalence record or exact final build is incomplete"

    if not isinstance(historical_package, dict) or not isinstance(
        historical_runtimes, dict
    ):
        return False, "historical Windows runtime evidence is malformed"

    historical_plugin = historical_package.get("plugin_sha256")
    historical_package_sha = historical_package.get("package_zip_sha256")
    historical_bundle = historical_package.get("bundle_zip_sha256")

    def historical_runtime_ok(key: str, profile: str) -> bool:
        receipt = historical_runtimes.get(key)
        if not isinstance(receipt, dict):
            return False
        artifact = receipt.get("artifact", {})
        markers = receipt.get("required_log_markers", [])
        present = {
            str(item.get("marker"))
            for item in markers
            if isinstance(item, dict) and item.get("present") is True
        }
        required = (
            {"TEXPDF STRESS 1000 PASS"}
            if profile == "stress1000"
            else {
                "TEXPDF REALISTIC CORPUS PASS",
                "TEXPDF HELP EXAMPLES PASS",
                "TEXPDF FULL ENGINE STATA PASS",
            }
        )
        return (
            receipt.get("tested_sha") == runtime_source
            and receipt.get("status") == "success"
            and receipt.get("stata_status") == "success"
            and receipt.get("profile") == profile
            and str(receipt.get("stata_version", "")).split(".", 1)[0] == "19"
            and receipt.get("stata_edition") == "MP"
            and "Windows" in str(receipt.get("platform", ""))
            and isinstance(artifact, dict)
            and artifact.get("plugin_sha256") == historical_plugin
            and artifact.get("package_zip_sha256") == historical_package_sha
            and artifact.get("bundle_zip_sha256") == historical_bundle
            and required <= present
        )

    if not (
        historical_runtime_ok("stata_19_quick", "quick")
        and historical_runtime_ok("stata_19_stress1000", "stress1000")
        and historical_bundle == final_package.get("bundle_zip_sha256")
    ):
        return False, "historical runtime receipts or bundle identity do not match"

    try:
        changed_output = subprocess.check_output(
            ["git", "diff", "--name-only", f"{runtime_source}..{candidate_source}"],
            text=True,
        )
        changed_paths = [line for line in changed_output.splitlines() if line]
        binary_diff = subprocess.check_output(
            ["git", "diff", "--binary", f"{runtime_source}..{candidate_source}"]
        )
    except subprocess.CalledProcessError:
        return False, "cannot reproduce the source equivalence diff"
    unexpected = [path for path in changed_paths if not windows_runtime_equivalence_path(path)]
    if (
        unexpected
        or diff.get("base_source_sha") != runtime_source
        or diff.get("candidate_source_sha") != candidate_source
        or diff.get("changed_path_count") != len(changed_paths)
        or diff.get("git_diff_sha256") != hashlib.sha256(binary_diff).hexdigest()
    ):
        return False, f"source equivalence diff mismatch; unexpected={unexpected}"

    try:
        metadata_equal = all(
            normalized_stata_metadata(runtime_source, path)
            == normalized_stata_metadata(candidate_source, path)
            for path in ("stata/texpdf.ado", "stata/texpdf.sthlp", "stata/texpdf.pkg")
        )
    except (subprocess.CalledProcessError, ValueError):
        metadata_equal = False
    if not metadata_equal:
        return False, "Stata runtime/package metadata changed beyond date headers"

    registry_ok = (
        target.get("artifact") == "_texpdf_plugin_windows.plugin"
        and target.get("build_qualified") is True
        and target.get("build_source_sha") == candidate_source
        and target.get("qualified_source_sha") == candidate_source
        and target.get("runtime_evidence_source_sha") == runtime_source
        and target.get("stata_runtime_qualified") is True
        and target.get("plugin_sha256") == final_package.get("plugin_sha256")
        and target.get("embedded_helper_sha256")
        == final_package.get("embedded_helper_sha256")
        and target.get("candidate_package_sha256")
        == final_package.get("package_zip_sha256")
        and target.get("candidate_package_version") == candidate_version
        and target.get("tested_stata_versions") == ["19"]
        and target.get("receipt") == str(WINDOWS_RUNTIME_EQUIVALENCE_PATH)
        and target.get("runtime_receipt") == str(WINDOWS_RUNTIME_PATH)
    )
    if not registry_ok:
        return False, "target registry does not bind the final build and carried runtime"
    return True, (
        f"final_build_source={candidate_source}; runtime_source={runtime_source}; "
        f"carry_forward=true; changed_paths={len(changed_paths)}"
    )


def successful_receipt(source_sha: str) -> tuple[bool, str]:
    path = Path(".ci/stata/results") / f"{source_sha}.json"
    if not path.is_file():
        return False, f"missing exact receipt {path}"
    receipt = read_json(path)
    expected = {
        "tested_sha": source_sha,
        "status": "success",
        "stata_status": "success",
        "rust_status": "success",
    }
    mismatches = [
        f"{key}={receipt.get(key)!r}"
        for key, value in expected.items()
        if receipt.get(key) != value
    ]
    if mismatches:
        return False, "receipt mismatch: " + ", ".join(mismatches)
    return True, (
        f"exact receipt profile={receipt.get('profile')} "
        f"rust_mode={receipt.get('rust_mode')}"
    )


def read_targets(checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not TARGETS_PATH.is_file():
        add_check(checks, "target_registry", False, f"missing {TARGETS_PATH}")
        return {}
    payload = read_json(TARGETS_PATH)
    targets = payload.get("targets")
    valid = isinstance(targets, dict)
    add_check(
        checks,
        "target_registry",
        valid,
        f"target count={len(targets) if isinstance(targets, dict) else 0}",
    )
    if not valid:
        return {}
    return {
        str(key): value
        for key, value in targets.items()
        if isinstance(value, dict)
    }


def validate_arm_target(
    targets: dict[str, dict[str, Any]], checks: list[dict[str, Any]]
) -> None:
    record = targets.get("aarch64-apple-darwin")
    if record is None:
        add_check(checks, "macos_arm_runtime", False, "target record is absent")
        return
    source_sha = str(record.get("qualified_source_sha", ""))
    artifact_valid = (
        record.get("stata_runtime_qualified") is True
        and record.get("build_qualified") is True
        and record.get("build_source_sha") == source_sha
        and valid_source_sha(source_sha)
        and int(record.get("plugin_size_bytes", 0)) > 0
        and valid_sha256(record.get("plugin_sha256"))
        and int(record.get("bundle_zip_size_bytes", 0)) > 0
        and valid_sha256(record.get("bundle_zip_sha256"))
        and int(record.get("embedded_helper_size_bytes", 0)) > 0
        and valid_sha256(record.get("embedded_helper_sha256"))
        and record.get("receipt") == f".ci/stata/results/{source_sha}.json"
        and bool(record.get("stata_version"))
    )
    receipt_ok, receipt_detail = (
        successful_receipt(source_sha)
        if valid_source_sha(source_sha)
        else (False, "qualified source SHA is missing or malformed")
    )
    add_check(
        checks,
        "macos_arm_runtime",
        artifact_valid and receipt_ok,
        (
            f"source={source_sha or 'missing'}; plugin_bytes={record.get('plugin_size_bytes')}; "
            f"Stata={record.get('stata_edition')} {record.get('stata_version')}; "
            f"{receipt_detail}"
        ),
    )


def validate_universal(
    targets: dict[str, dict[str, Any]],
    checks: list[dict[str, Any]],
    candidate_version: str = "0.1.0-rc.2",
    public_release: bool = False,
) -> None:
    data: dict[str, Any] = {}
    if not UNIVERSAL_PATH.is_file():
        add_check(
            checks,
            "macos_universal_build",
            False,
            f"missing {UNIVERSAL_PATH}",
        )
    else:
        data = read_json(UNIVERSAL_PATH)
        architectures = set(data.get("architectures", []))
        universal = data.get("universal", {})
        slices = data.get("slices", {})
        source_sha = data.get("source_sha")
        build_ok = (
            valid_source_sha(source_sha)
            and architectures == {"arm64", "x86_64"}
            and isinstance(universal, dict)
            and int(universal.get("size_bytes", 0)) > 0
            and valid_sha256(universal.get("sha256"))
            and all(
                isinstance(slices.get(name), dict)
                and int(slices[name].get("size_bytes", 0)) > 0
                and valid_sha256(slices[name].get("sha256"))
                and isinstance(slices[name].get("embedded_helper"), dict)
                and int(slices[name]["embedded_helper"].get("size_bytes", 0)) > 0
                and valid_sha256(slices[name]["embedded_helper"].get("sha256"))
                for name in ("arm64", "x86_64")
            )
            and data.get("arm_runtime_qualified") is True
        )
        add_check(
            checks,
            "macos_universal_build",
            build_ok,
            (
                f"architectures={sorted(architectures)}; "
                f"universal_bytes={universal.get('size_bytes')}; "
                f"arm_runtime={data.get('arm_runtime_qualified')}"
            ),
        )

    intel = targets.get("x86_64-apple-darwin", {})
    slices = data.get("slices", {}) if isinstance(data, dict) else {}
    intel_slice = slices.get("x86_64", {}) if isinstance(slices, dict) else {}
    universal = data.get("universal", {}) if isinstance(data, dict) else {}
    intel_compatibility_slice = (
        intel.get("build_qualified") is True
        and valid_source_sha(intel.get("build_source_sha"))
        and int(intel.get("plugin_size_bytes", 0)) > 0
        and valid_sha256(intel.get("plugin_sha256"))
        and intel.get("build_source_sha") == data.get("source_sha")
        and intel.get("plugin_size_bytes") == intel_slice.get("size_bytes")
        and intel.get("plugin_sha256") == intel_slice.get("sha256")
        and intel.get("embedded_helper_size_bytes")
        == intel_slice.get("embedded_helper", {}).get("size_bytes")
        and intel.get("embedded_helper_sha256")
        == intel_slice.get("embedded_helper", {}).get("sha256")
        and intel.get("universal_plugin_size_bytes") == universal.get("size_bytes")
        and intel.get("universal_plugin_sha256") == universal.get("sha256")
        and intel.get("stata_runtime_qualified") is False
        and not intel.get("qualified_source_sha")
        and data.get("intel_runtime_qualified") is False
    )
    add_check(
        checks,
        "macos_intel_compatibility_slice",
        intel_compatibility_slice,
        (
            f"source={intel.get('build_source_sha')}; "
            f"plugin_bytes={intel.get('plugin_size_bytes')}; "
            "runtime=untested-by-policy"
        ),
    )

    candidate = data.get("candidate_package", {}) if isinstance(data, dict) else {}
    arm = targets.get("aarch64-apple-darwin", {})
    package_ok = (
        isinstance(candidate, dict)
        and candidate.get("version") == candidate_version
        and int(candidate.get("zip_size_bytes", 0)) > 0
        and valid_sha256(candidate.get("zip_sha256"))
        and candidate.get("license_evidence_included") is True
        and LICENSE_STATUS_PATH.is_file()
        and candidate.get("license_audit_source_sha")
        == read_json(LICENSE_STATUS_PATH).get("source_sha")
        and candidate.get("public_release") is public_release
        and data.get("arm_runtime_qualified") is True
        and data.get("intel_runtime_qualified") is False
        and intel_compatibility_slice
        and arm.get("candidate_package_sha256") == candidate.get("zip_sha256")
        and intel.get("candidate_package_sha256") == candidate.get("zip_sha256")
    )
    add_check(
        checks,
        "macos_candidate_package",
        package_ok,
        (
            f"version={candidate.get('version')}; "
            f"zip_bytes={candidate.get('zip_size_bytes')}; "
            f"license_evidence={candidate.get('license_evidence_included')}; "
            "arm_runtime=true; intel_runtime=untested-by-policy"
        ),
    )


def validate_other_targets(
    targets: dict[str, dict[str, Any]], checks: list[dict[str, Any]]
) -> None:
    for target, label in (("x86_64-pc-windows-msvc", "Windows x86-64"),):
        record = targets.get(target, {})
        build_ok = (
            record.get("build_qualified") is True
            and valid_source_sha(record.get("build_source_sha"))
            and int(record.get("plugin_size_bytes", 0)) > 0
            and valid_sha256(record.get("plugin_sha256"))
        )
        add_check(
            checks,
            f"{target}_build",
            build_ok,
            str(record.get("status", f"no {label} build record")),
            release_blocker=False,
            public_release_blocker=False,
        )
        runtime_ok = (
            record.get("stata_runtime_qualified") is True
            and valid_source_sha(record.get("qualified_source_sha"))
        )
        add_check(
            checks,
            f"{target}_runtime",
            runtime_ok,
            str(record.get("status", f"no licensed {label} Stata qualification")),
            release_blocker=False,
            public_release_blocker=True,
        )


def successful_linux_runtime(
    receipt: object,
    *,
    source_sha: str,
    stata_version: str,
    profile: str,
    plugin_sha256: object,
    package_sha256: object,
    bundle_sha256: object,
) -> bool:
    if not isinstance(receipt, dict):
        return False
    artifact = receipt.get("artifact", {})
    markers = receipt.get("required_log_markers", [])
    return (
        receipt.get("tested_sha") == source_sha
        and receipt.get("status") == "success"
        and receipt.get("stata_status") == "success"
        and str(receipt.get("stata_version", "")).split(".", 1)[0] == stata_version
        and receipt.get("profile") == profile
        and "PC (64-bit x86-64)" in str(receipt.get("platform", ""))
        and isinstance(artifact, dict)
        and artifact.get("plugin_sha256") == plugin_sha256
        and artifact.get("package_zip_sha256") == package_sha256
        and artifact.get("bundle_zip_sha256") == bundle_sha256
        and isinstance(markers, list)
        and bool(markers)
        and all(isinstance(item, dict) and item.get("present") is True for item in markers)
    )


def validate_linux_target(
    targets: dict[str, dict[str, Any]],
    checks: list[dict[str, Any]],
    candidate_version: str,
    public_release: bool = False,
) -> None:
    target = targets.get("x86_64-unknown-linux-gnu", {})
    if not LINUX_RUNTIME_PATH.is_file():
        add_check(checks, "linux_x86_64_runtime", False, f"missing {LINUX_RUNTIME_PATH}")
        return
    data = read_json(LINUX_RUNTIME_PATH)
    source_sha = str(data.get("source_sha", ""))
    build = data.get("build_receipt", {})
    package = data.get("package", {})
    runtimes = data.get("runtimes", {})
    policy = build.get("binary_policy", {}) if isinstance(build, dict) else {}
    plugin_sha = package.get("plugin_sha256") if isinstance(package, dict) else None
    helper_sha = package.get("embedded_helper_sha256") if isinstance(package, dict) else None
    package_sha = package.get("package_zip_sha256") if isinstance(package, dict) else None
    bundle_sha = package.get("bundle_zip_sha256") if isinstance(package, dict) else None
    build_ok = (
        data.get("schema_version") == 1
        and data.get("qualified") is True
        and data.get("target") == "x86_64-unknown-linux-gnu"
        and valid_source_sha(source_sha)
        and isinstance(build, dict)
        and build.get("status") == "success"
        and build.get("source_sha") == source_sha
        and build.get("rust_tests") == "success"
        and build.get("cargo_target_seed") == "fresh-empty-run-directory"
        and isinstance(policy, dict)
        and policy.get("maximum_allowed_glibc") == "2.28"
        and policy.get("violations") == []
    )
    package_ok = (
        isinstance(package, dict)
        and package.get("package_version") == candidate_version
        and package.get("target") == "x86_64-unknown-linux-gnu"
        and package.get("installed_plugin") == "_texpdf_plugin_unix.plugin"
        and package.get("license_evidence_included") is True
        and package.get("release_license_complete") is True
        and package.get("public_release_mode") is public_release
        and LICENSE_STATUS_PATH.is_file()
        and package.get("license_audit_source_sha")
        == read_json(LICENSE_STATUS_PATH).get("source_sha")
        and valid_sha256(plugin_sha)
        and valid_sha256(helper_sha)
        and valid_sha256(package_sha)
        and valid_sha256(bundle_sha)
        and build.get("plugin_sha256") == plugin_sha
        and build.get("helper_sha256") == helper_sha
        and build.get("package_sha256") == package_sha
    )
    runtime_ok = isinstance(runtimes, dict) and all(
        successful_linux_runtime(
            runtimes.get(key),
            source_sha=source_sha,
            stata_version=version,
            profile=profile,
            plugin_sha256=plugin_sha,
            package_sha256=package_sha,
            bundle_sha256=bundle_sha,
        )
        for key, version, profile in (
            ("stata_18_quick", "18", "quick"),
            ("stata_18_stress1000", "18", "stress1000"),
            ("stata_19_quick", "19", "quick"),
        )
    )
    registry_ok = (
        target.get("artifact") == "_texpdf_plugin_unix.plugin"
        and target.get("build_qualified") is True
        and target.get("stata_runtime_qualified") is True
        and target.get("build_source_sha") == source_sha
        and target.get("qualified_source_sha") == source_sha
        and target.get("plugin_sha256") == plugin_sha
        and target.get("embedded_helper_sha256") == helper_sha
        and target.get("candidate_package_sha256") == package_sha
        and target.get("minimum_glibc") == "2.28"
        and target.get("tested_stata_versions") == ["18", "19"]
        and target.get("receipt") == str(LINUX_RUNTIME_PATH)
    )
    add_check(
        checks,
        "linux_x86_64_runtime",
        build_ok and package_ok and runtime_ok and registry_ok,
        (
            f"source={source_sha or 'missing'}; glibc_max={policy.get('maximum_allowed_glibc')}; "
            f"package_version={package.get('package_version') if isinstance(package, dict) else None}; "
            f"Stata18_quick={runtime_ok and bool(runtimes.get('stata_18_quick'))}; "
            f"Stata18_stress1000={runtime_ok and bool(runtimes.get('stata_18_stress1000'))}; "
            f"Stata19_quick={runtime_ok and bool(runtimes.get('stata_19_quick'))}"
        ),
    )


def validate_windows_target(
    targets: dict[str, dict[str, Any]],
    checks: list[dict[str, Any]],
    candidate_version: str,
    public_release: bool = False,
) -> None:
    target = targets.get("x86_64-pc-windows-msvc", {})
    if not WINDOWS_RUNTIME_PATH.is_file():
        add_check(checks, "windows_x86_64_runtime", False, f"missing {WINDOWS_RUNTIME_PATH}")
        return
    data = read_json(WINDOWS_RUNTIME_PATH)
    if WINDOWS_RUNTIME_EQUIVALENCE_PATH.is_file():
        equivalence = read_json(WINDOWS_RUNTIME_EQUIVALENCE_PATH)
        passed, detail = validate_windows_runtime_equivalence(
            equivalence,
            data,
            target,
            candidate_version,
            public_release,
        )
        add_check(checks, "windows_x86_64_runtime", passed, detail)
        return
    source_sha = str(data.get("source_sha", ""))
    build = data.get("build_receipt", {})
    package = data.get("package", {})
    runtimes = data.get("runtimes", {})
    policy = build.get("binary_policy", {}) if isinstance(build, dict) else {}
    plugin_sha = package.get("plugin_sha256") if isinstance(package, dict) else None
    helper_sha = package.get("embedded_helper_sha256") if isinstance(package, dict) else None
    package_sha = package.get("package_zip_sha256") if isinstance(package, dict) else None
    bundle_sha = package.get("bundle_zip_sha256") if isinstance(package, dict) else None
    build_ok = (
        data.get("schema_version") == 1
        and data.get("qualified") is True
        and data.get("target") == "x86_64-pc-windows-msvc"
        and valid_source_sha(source_sha)
        and isinstance(build, dict)
        and build.get("status") == "success"
        and build.get("source_sha") == source_sha
        and build.get("rust_tests") == "success"
        and isinstance(policy, dict)
        and policy.get("violations") == []
        and policy.get("static_msvc_crt") is True
    )
    package_ok = (
        isinstance(package, dict)
        and package.get("package_version") == candidate_version
        and package.get("target") == "x86_64-pc-windows-msvc"
        and package.get("installed_plugin") == "_texpdf_plugin_windows.plugin"
        and package.get("license_evidence_included") is True
        and package.get("release_license_complete") is True
        and package.get("public_release_mode") is public_release
        and LICENSE_STATUS_PATH.is_file()
        and package.get("license_audit_source_sha")
        == read_json(LICENSE_STATUS_PATH).get("source_sha")
        and valid_sha256(plugin_sha)
        and valid_sha256(helper_sha)
        and valid_sha256(package_sha)
        and valid_sha256(bundle_sha)
        and build.get("plugin_sha256") == plugin_sha
        and build.get("helper_sha256") == helper_sha
        and build.get("package_sha256") == package_sha
    )

    def runtime_ok(key: str, profile: str) -> bool:
        receipt = runtimes.get(key) if isinstance(runtimes, dict) else None
        if not isinstance(receipt, dict):
            return False
        artifact = receipt.get("artifact", {})
        markers = receipt.get("required_log_markers", [])
        marker_names = {
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
        return (
            receipt.get("tested_sha") == source_sha
            and receipt.get("status") == "success"
            and receipt.get("stata_status") == "success"
            and str(receipt.get("stata_version", "")).split(".", 1)[0] == "19"
            and receipt.get("stata_edition") == "MP"
            and receipt.get("profile") == profile
            and "Windows" in str(receipt.get("platform", ""))
            and isinstance(artifact, dict)
            and artifact.get("plugin_sha256") == plugin_sha
            and artifact.get("package_zip_sha256") == package_sha
            and artifact.get("bundle_zip_sha256") == bundle_sha
            and expected_markers <= marker_names
        )

    runtimes_ok = runtime_ok("stata_19_quick", "quick") and runtime_ok(
        "stata_19_stress1000", "stress1000"
    )
    registry_ok = (
        target.get("artifact") == "_texpdf_plugin_windows.plugin"
        and target.get("build_qualified") is True
        and target.get("stata_runtime_qualified") is True
        and target.get("build_source_sha") == source_sha
        and target.get("qualified_source_sha") == source_sha
        and target.get("plugin_sha256") == plugin_sha
        and target.get("embedded_helper_sha256") == helper_sha
        and target.get("candidate_package_sha256") == package_sha
        and target.get("tested_stata_versions") == ["19"]
        and target.get("receipt") == str(WINDOWS_RUNTIME_PATH)
    )
    add_check(
        checks,
        "windows_x86_64_runtime",
        build_ok and package_ok and runtimes_ok and registry_ok,
        (
            f"source={source_sha or 'missing'}; package_version="
            f"{package.get('package_version') if isinstance(package, dict) else None}; "
            f"static_crt={policy.get('static_msvc_crt')}; "
            f"Stata19_quick={runtime_ok('stata_19_quick', 'quick')}; "
            f"Stata19_stress1000={runtime_ok('stata_19_stress1000', 'stress1000')}"
        ),
    )


def validate_required_source_coherence(
    scope: dict[str, Any],
    targets: dict[str, dict[str, Any]],
    checks: list[dict[str, Any]],
) -> None:
    required = scope.get("required_runtime_targets", [])
    expected = str(scope.get("candidate_source_sha", ""))
    sources = {
        str(targets.get(str(target), {}).get("qualified_source_sha", ""))
        for target in required
    }
    passed = (
        bool(required)
        and valid_source_sha(expected)
        and sources == {expected}
    )
    add_check(
        checks,
        "required_target_source_coherence",
        passed,
        f"required_targets={required}; expected={expected}; sources={sorted(sources)}",
    )


def validate_license_source_coherence(
    scope: dict[str, Any],
    targets: dict[str, dict[str, Any]],
    checks: list[dict[str, Any]],
) -> None:
    required = scope.get("required_runtime_targets", [])
    sources = {
        str(targets.get(str(target), {}).get("qualified_source_sha", ""))
        for target in required
    }
    license_source = ""
    if LICENSE_STATUS_PATH.is_file():
        license_source = str(read_json(LICENSE_STATUS_PATH).get("source_sha", ""))
    candidate_source = next(iter(sources)) if len(sources) == 1 else ""
    changed_paths: list[str] = []
    ancestor = False
    if valid_source_sha(license_source) and valid_source_sha(candidate_source):
        ancestor_result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", license_source, candidate_source],
            text=True,
            capture_output=True,
            check=False,
        )
        ancestor = ancestor_result.returncode == 0
        if ancestor:
            diff = subprocess.run(
                ["git", "diff", "--name-only", f"{license_source}..{candidate_source}"],
                text=True,
                capture_output=True,
                check=False,
            )
            if diff.returncode == 0:
                changed_paths = [line for line in diff.stdout.splitlines() if line]
            else:
                ancestor = False
    allowed = all(evidence_only_path(path) for path in changed_paths)
    passed = ancestor and allowed
    add_check(
        checks,
        "candidate_license_source_coherence",
        passed,
        (
            f"candidate_source={candidate_source or 'missing'}; "
            f"license_source={license_source or 'missing'}; ancestor={ancestor}; "
            f"non_evidence_changes={sorted(path for path in changed_paths if not evidence_only_path(path))}"
        ),
    )


def validate_license_status(checks: list[dict[str, Any]]) -> None:
    if not LICENSE_STATUS_PATH.is_file():
        add_check(
            checks,
            "third_party_license_complete",
            False,
            f"missing source-bound audit status {LICENSE_STATUS_PATH}",
        )
        return
    data = read_json(LICENSE_STATUS_PATH)
    tex = data.get("tex_resources", {})
    return_codes = data.get("return_codes") or data.get("stage_return_codes", {})
    complete = (
        data.get("release_license_complete") is True
        and valid_source_sha(data.get("source_sha"))
        and isinstance(tex, dict)
        and int(tex.get("resource_count", 0)) > 0
        and int(tex.get("ambiguous", -1)) == 0
        and int(tex.get("unmapped", -1)) == 0
        and int(tex.get("missing_license", -1)) == 0
        and isinstance(return_codes, dict)
        and return_codes
        and all(value == 0 for value in return_codes.values())
        and int(data.get("dependency_undeclared_count", -1)) == 0
        and int(data.get("missing_rust_notice_files", -1)) == 0
        and int(data.get("missing_native_notice_files", -1)) == 0
    )
    add_check(
        checks,
        "third_party_license_complete",
        complete,
        (
            f"source={data.get('source_sha')}; resources={tex.get('resource_count')}; "
            f"mapped={tex.get('mapped')}; ambiguous={tex.get('ambiguous')}; "
            f"unmapped={tex.get('unmapped')}; missing_license={tex.get('missing_license')}; "
            f"missing_rust_texts={data.get('missing_rust_notice_files')}; "
            f"missing_native_texts={data.get('missing_native_notice_files')}"
        ),
    )


def validate_memory(
    targets: dict[str, dict[str, Any]], checks: list[dict[str, Any]]
) -> None:
    if not MEMORY_PATH.is_file():
        add_check(
            checks,
            "macos_arm_memory_stress",
            False,
            f"missing permanent qualification record {MEMORY_PATH}",
        )
        return
    data = read_json(MEMORY_PATH)
    memory = data.get("memory", {})
    plugin = data.get("plugin", {})
    helper = data.get("helper", {})
    universal_package = data.get("universal_package", {})
    arm = targets.get("aarch64-apple-darwin", {})
    iterations = (
        memory.get("iterations_requested") if isinstance(memory, dict) else None
    )
    expected_failures = iterations // 25 + 2 if isinstance(iterations, int) else None
    passed = (
        data.get("schema_version") == 3
        and valid_source_sha(data.get("source_sha"))
        and data.get("qualified") is True
        and data.get("overall_status") == "success"
        and data.get("stata_status") == "success"
        and data.get("rust_status") == "success"
        and data.get("rust_mode") == "repository-engine"
        and isinstance(plugin, dict)
        and valid_sha256(plugin.get("sha256"))
        and int(plugin.get("size_bytes", 0)) > 0
        and isinstance(helper, dict)
        and valid_sha256(helper.get("sha256"))
        and int(helper.get("size_bytes", 0)) > 0
        and arm.get("universal_plugin_sha256") == plugin.get("sha256")
        and isinstance(universal_package, dict)
        and universal_package.get("source_sha") == data.get("source_sha")
        and isinstance(universal_package.get("universal_run_id"), int)
        and int(universal_package.get("universal_run_id", 0)) > 0
        and valid_sha256(universal_package.get("artifact_digest"))
        and universal_package.get("package_zip_sha256")
        == arm.get("candidate_package_sha256")
        and universal_package.get("plugin_sha256") == plugin.get("sha256")
        and universal_package.get("arm_helper_sha256") == helper.get("sha256")
        and universal_package.get("bundle_zip_sha256") == arm.get("bundle_zip_sha256")
        and isinstance(memory, dict)
        and isinstance(iterations, int)
        and iterations >= 1000
        and memory.get("runner_rc") == 0
        and memory.get("growth_gate") is True
        and memory.get("successful_compile_count") == iterations
        and memory.get("injected_failure_count") == expected_failures
        and memory.get("expected_injected_failure_count") == expected_failures
        and memory.get("post_error_recovery") is True
        and int(memory.get("helper_sample_count", 0)) > 0
        and memory.get("max_concurrent_helpers") == 1
        and memory.get("retained_helper_pids") == []
        and valid_sha256(memory.get("stata_log_sha256"))
        and int(memory.get("max_allowed_growth_kib", 0)) <= 64 * 1024
    )
    add_check(
        checks,
        "macos_arm_memory_stress",
        passed,
        (
            f"source={data.get('source_sha')}; iterations={memory.get('iterations_requested')}; "
            f"universal_run_id={universal_package.get('universal_run_id')}; "
            f"peak_rss_kib={memory.get('peak_stata_rss_kib')}; "
            f"post_warmup_growth_kib={memory.get('post_warmup_growth_kib')}; "
            f"growth_ratio={memory.get('post_warmup_growth_ratio')}"
        ),
    )


def validate_scope(checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not SCOPE_PATH.is_file():
        add_check(checks, "release_scope", False, f"missing {SCOPE_PATH}")
        return {}
    scope = read_json(SCOPE_PATH)
    required = scope.get("required_runtime_targets")
    release_kind = scope.get("release_kind")
    version = scope.get("candidate_version")
    version_ok = (
        isinstance(version, str)
        and (
            (release_kind == "public_release_candidate" and re.fullmatch(r"\d+\.\d+\.\d+-rc\d+", version))
            or (release_kind == "final_release" and re.fullmatch(r"\d+\.\d+\.\d+", version))
        )
    )
    valid = (
        scope.get("schema_version") == 1
        and release_kind in {"public_release_candidate", "final_release"}
        and version_ok
        and valid_source_sha(scope.get("candidate_source_sha"))
        and required
        == [
            "aarch64-apple-darwin",
            "x86_64-unknown-linux-gnu",
            "x86_64-pc-windows-msvc",
        ]
        and scope.get("deferred_runtime_targets") == []
        and scope.get("repository_publication_authorized") is True
        and scope.get("public_distribution_enabled") is True
        and scope.get("github_release_enabled") is True
        and scope.get("ssc_distribution_enabled") is True
    )
    add_check(
        checks,
        "release_scope",
        valid,
        (
            f"kind={scope.get('release_kind')}; version={scope.get('candidate_version')}; "
            f"source={scope.get('candidate_source_sha')}; "
            f"required_targets={required}"
        ),
    )
    public_enabled = scope.get("public_distribution_enabled") is True
    add_check(
        checks,
        "public_distribution",
        public_enabled,
        "public GitHub distribution is explicitly authorized in release scope",
    )
    add_check(
        checks,
        "ssc_distribution",
        scope.get("ssc_distribution_enabled") is True,
        "SSC distribution is explicitly authorized in release scope",
    )
    return scope


def validate_publication_state(
    scope: dict[str, Any], checks: list[dict[str, Any]]
) -> None:
    if not PUBLICATION_PATH.is_file():
        add_check(
            checks,
            "public_repository_security",
            False,
            f"missing {PUBLICATION_PATH}",
        )
        return
    data = read_json(PUBLICATION_PATH)
    audit = data.get("history_audit", {})
    settings = data.get("settings", {})
    branch = settings.get("branch_protection", {}) if isinstance(settings, dict) else {}
    rc1 = data.get("historical_rc1", {})
    passed = (
        data.get("schema_version") == 1
        and data.get("repository") == "johannes-schmieder/texpdf"
        and data.get("repository_visibility") == "public"
        and isinstance(audit, dict)
        and audit.get("scanner") == "gitleaks"
        and bool(audit.get("scanner_version"))
        and audit.get("tip_sha") == scope.get("candidate_source_sha")
        and int(audit.get("commits_scanned", 0)) > 0
        and audit.get("secrets_found") == 0
        and audit.get("history_rewritten") is False
        and isinstance(settings, dict)
        and settings.get("default_workflow_permissions") == "read"
        and settings.get("can_approve_pull_request_reviews") is False
        and settings.get("sha_pinning_required") is True
        and settings.get("private_vulnerability_reporting") is True
        and isinstance(branch, dict)
        and branch.get("allow_force_pushes") is False
        and branch.get("allow_deletions") is False
        and isinstance(rc1, dict)
        and rc1.get("tag_preserved") is True
        and rc1.get("assets_preserved") is True
        and rc1.get("superseded_label") is True
    )
    add_check(
        checks,
        "public_repository_security",
        passed,
        (
            f"visibility={data.get('repository_visibility')}; "
            f"audit_tip={audit.get('tip_sha') if isinstance(audit, dict) else None}; "
            f"scope_source={scope.get('candidate_source_sha')}; "
            f"sha_pinning={settings.get('sha_pinning_required') if isinstance(settings, dict) else None}; "
            f"vulnerability_reporting={settings.get('private_vulnerability_reporting') if isinstance(settings, dict) else None}"
        ),
    )


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# texpdf release-readiness audit",
        "",
        f"macOS ARM64 implementation qualified: **{str(result['implementation_complete_macos_arm64']).lower()}**",
        f"Required-target candidate ready: **{str(result['candidate_ready']).lower()}**",
        f"Public cross-platform release ready: **{str(result['public_release_ready']).lower()}**",
        "",
        "| Check | Result | Candidate blocker | Public blocker | Detail |",
        "|---|---|---|---|---|",
    ]
    for check in result["checks"]:
        detail = str(check["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{check['key']}` | {'PASS' if check['passed'] else 'FAIL'} | "
            f"{'yes' if check['candidate_release_blocker'] else 'no'} | "
            f"{'yes' if check['public_release_blocker'] else 'no'} | {detail} |"
        )
    lines.extend(["", "## Active candidate blockers", ""])
    blockers = result["candidate_blockers"]
    if blockers:
        lines.extend(f"- `{item}`" for item in blockers)
    else:
        lines.append("None.")
    lines.extend(["", "## Public-release blockers", ""])
    public_blockers = result["public_release_blockers"]
    if public_blockers:
        lines.extend(f"- `{item}`" for item in public_blockers)
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def build_result() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for file_name in REQUIRED_PACKAGE_FILES:
        add_check(
            checks,
            f"package_file_{Path(file_name).name}",
            Path(file_name).is_file(),
            file_name,
        )
    add_check(
        checks,
        "cargo_lock",
        Path("Cargo.lock").is_file(),
        "Cargo.lock is committed",
    )
    scope = validate_scope(checks)
    validate_publication_state(scope, checks)
    targets = read_targets(checks)
    validate_arm_target(targets, checks)
    public_release = scope.get("public_distribution_enabled") is True
    validate_universal(
        targets, checks, str(scope.get("candidate_version", "")), public_release
    )
    validate_linux_target(
        targets, checks, str(scope.get("candidate_version", "")), public_release
    )
    validate_windows_target(
        targets, checks, str(scope.get("candidate_version", "")), public_release
    )
    validate_required_source_coherence(scope, targets, checks)
    validate_license_status(checks)
    validate_license_source_coherence(scope, targets, checks)
    validate_memory(targets, checks)

    mac_required = {
        "package_file_texpdf.ado",
        "package_file_texpdf.sthlp",
        "package_file_texpdf_run.ado",
        "package_file_texpdf.pkg",
        "package_file_stata.toc",
        "cargo_lock",
        "target_registry",
        "macos_arm_runtime",
    }
    by_key = {check["key"]: check for check in checks}
    implementation_complete = all(
        by_key.get(key, {}).get("passed") for key in mac_required
    )
    candidate_blockers = [
        check["key"] for check in checks if check["candidate_release_blocker"]
    ]
    public_blockers = [
        check["key"] for check in checks if check["public_release_blocker"]
    ]
    result = {
        "schema_version": 3,
        "candidate_version": scope.get("candidate_version", "0.1.0-rc.2"),
        "release_kind": scope.get("release_kind", "public_release_candidate"),
        "implementation_complete_macos_arm64": implementation_complete,
        "candidate_ready": not candidate_blockers,
        "public_release_ready": not public_blockers,
        "candidate_blockers": candidate_blockers,
        "public_release_blockers": public_blockers,
        "release_blockers": candidate_blockers,
        "checks": checks,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=Path("release/READINESS.json"))
    parser.add_argument("--markdown", type=Path, default=Path("release/READINESS.md"))
    parser.add_argument("--require-candidate-ready", action="store_true")
    parser.add_argument("--require-public-release-ready", action="store_true")
    args = parser.parse_args()

    result = build_result()
    candidate_blockers = result["candidate_blockers"]
    public_blockers = result["public_release_blockers"]
    implementation_complete = result["implementation_complete_macos_arm64"]
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(render_markdown(result), encoding="utf-8")
    print(
        "TEXPDF_RELEASE_AUDIT "
        f"macos_arm_complete={str(implementation_complete).lower()} "
        f"candidate_ready={str(not candidate_blockers).lower()} "
        f"public_release_ready={str(not public_blockers).lower()} "
        f"candidate_blockers={','.join(candidate_blockers)}"
    )
    if args.require_candidate_ready and candidate_blockers:
        return 2
    if args.require_public_release_ready and public_blockers:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as error:
        print(f"TEXPDF_RELEASE_AUDIT_ERROR {error}", file=sys.stderr)
        raise SystemExit(2)
