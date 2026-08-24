#!/usr/bin/env python3
"""Audit texpdf implementation and public-release readiness.

This tool is deliberately fail-closed. A file's presence is never enough: all
source, artifact, target, license, and stress records must carry internally
consistent status fields and exact hashes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_PACKAGE_FILES = (
    "stata/texpdf.ado",
    "stata/texpdf.sthlp",
    "stata/texpdf.pkg",
    "stata/stata.toc",
)
TARGETS_PATH = Path("release/targets.json")
UNIVERSAL_PATH = Path("release/macos-universal.json")
INTEL_RUNTIME_PATH = Path("release/macos-intel-runtime.json")
MEMORY_PATH = Path("release/memory-stress-macos-arm64.json")
LICENSE_STATUS_PATH = Path("licenses/generated/STATUS.json")
SCOPE_PATH = Path("release/scope.json")


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
        and valid_source_sha(source_sha)
        and int(record.get("plugin_size_bytes", 0)) > 0
        and valid_sha256(record.get("plugin_sha256"))
        and int(record.get("bundle_zip_size_bytes", 0)) > 0
        and valid_sha256(record.get("bundle_zip_sha256"))
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
    targets: dict[str, dict[str, Any]], checks: list[dict[str, Any]]
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
    intel_build = (
        intel.get("build_qualified") is True
        and valid_source_sha(intel.get("build_source_sha"))
        and int(intel.get("plugin_size_bytes", 0)) > 0
        and valid_sha256(intel.get("plugin_sha256"))
        and intel.get("build_source_sha") == data.get("source_sha")
        and intel.get("plugin_size_bytes") == intel_slice.get("size_bytes")
        and intel.get("plugin_sha256") == intel_slice.get("sha256")
        and intel.get("universal_plugin_size_bytes") == universal.get("size_bytes")
        and intel.get("universal_plugin_sha256") == universal.get("sha256")
    )
    add_check(
        checks,
        "macos_intel_build",
        intel_build,
        (
            f"source={intel.get('build_source_sha')}; "
            f"plugin_bytes={intel.get('plugin_size_bytes')}"
        ),
    )
    intel_source = str(intel.get("qualified_source_sha", ""))
    intel_receipt_ok, intel_receipt_detail = (
        successful_receipt(intel_source)
        if valid_source_sha(intel_source)
        else (False, "qualified source SHA is missing or malformed")
    )
    intel_runtime: dict[str, Any] = {}
    if INTEL_RUNTIME_PATH.is_file():
        intel_runtime = read_json(INTEL_RUNTIME_PATH)
    runtime_record_ok = (
        intel_runtime.get("qualified") is True
        and intel_runtime.get("source_sha") == intel_source
        and intel_runtime.get("universal_plugin_size_bytes")
        == universal.get("size_bytes")
        and intel_runtime.get("universal_plugin_sha256") == universal.get("sha256")
        and intel_runtime.get("intel_slice_size_bytes") == intel_slice.get("size_bytes")
        and intel_runtime.get("intel_slice_sha256") == intel_slice.get("sha256")
        and isinstance(intel_runtime.get("receipt"), dict)
        and intel_runtime["receipt"].get("tested_sha") == intel_source
        and intel_runtime["receipt"].get("status") == "success"
        and intel_runtime["receipt"].get("stata_status") == "success"
    )
    add_check(
        checks,
        "macos_intel_runtime",
        intel.get("stata_runtime_qualified") is True
        and valid_source_sha(intel_source)
        and data.get("intel_runtime_qualified") is True
        and intel_receipt_ok
        and runtime_record_ok,
        (
            f"{intel.get('status', 'actual Intel Stata runtime qualification is absent')}; "
            f"runtime_record={'valid' if runtime_record_ok else 'missing/invalid'}; "
            f"{intel_receipt_detail}"
        ),
    )


def validate_other_targets(
    targets: dict[str, dict[str, Any]], checks: list[dict[str, Any]]
) -> None:
    for target, label in (
        ("x86_64-pc-windows-msvc", "Windows x86-64"),
        ("x86_64-unknown-linux-gnu", "Linux x86-64"),
    ):
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


def validate_memory(checks: list[dict[str, Any]]) -> None:
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
    passed = (
        valid_source_sha(data.get("source_sha"))
        and data.get("overall_status") == "success"
        and data.get("stata_status") == "success"
        and data.get("rust_status") == "success"
        and isinstance(memory, dict)
        and int(memory.get("iterations_requested", 0)) >= 1000
        and memory.get("runner_rc") == 0
        and memory.get("growth_gate") is True
    )
    add_check(
        checks,
        "macos_arm_memory_stress",
        passed,
        (
            f"source={data.get('source_sha')}; iterations={memory.get('iterations_requested')}; "
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
    valid = (
        scope.get("schema_version") == 1
        and scope.get("release_kind") == "private_release_candidate"
        and scope.get("candidate_version") == "0.1.0-rc.1"
        and required == ["aarch64-apple-darwin", "x86_64-apple-darwin"]
        and scope.get("deferred_runtime_targets")
        == ["x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"]
        and scope.get("public_distribution_enabled") is False
    )
    add_check(
        checks,
        "release_scope",
        valid,
        (
            f"kind={scope.get('release_kind')}; version={scope.get('candidate_version')}; "
            f"required_targets={required}"
        ),
    )
    public_enabled = scope.get("public_distribution_enabled") is True
    add_check(
        checks,
        "public_distribution",
        public_enabled,
        "public repository and net-install publication are deferred by owner decision",
        release_blocker=False,
        public_release_blocker=True,
    )
    return scope


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# texpdf release-readiness audit",
        "",
        f"macOS ARM64 implementation qualified: **{str(result['implementation_complete_macos_arm64']).lower()}**",
        f"Private macOS universal candidate ready: **{str(result['candidate_ready']).lower()}**",
        f"Public cross-platform v1 ready: **{str(result['public_release_ready']).lower()}**",
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
    lines.extend(["", "## Active private-candidate blockers", ""])
    blockers = result["candidate_blockers"]
    if blockers:
        lines.extend(f"- `{item}`" for item in blockers)
    else:
        lines.append("None.")
    lines.extend(["", "## Deferred public-release blockers", ""])
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
    targets = read_targets(checks)
    validate_arm_target(targets, checks)
    validate_universal(targets, checks)
    validate_other_targets(targets, checks)
    validate_license_status(checks)
    validate_memory(checks)
    scope = validate_scope(checks)

    mac_required = {
        "package_file_texpdf.ado",
        "package_file_texpdf.sthlp",
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
        "candidate_version": scope.get("candidate_version", "0.1.0-rc.1"),
        "release_kind": scope.get("release_kind", "private_release_candidate"),
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
