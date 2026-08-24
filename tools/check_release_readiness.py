#!/usr/bin/env python3
"""Audit texpdf implementation and public-release readiness."""

from __future__ import annotations

import argparse
import hashlib
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
REQUIRED_PLATFORM_RECORDS = {
    "macos_arm64": Path("bundle/QUALIFICATION.json"),
    "macos_intel": Path("platform/macos-universal.json"),
    "linux_x86_64": Path("platform/linux-x86_64.json"),
    "windows_x86_64": Path("platform/windows-x86_64.json"),
}


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
) -> None:
    checks.append(
        {
            "key": key,
            "passed": bool(passed),
            "detail": detail,
            "release_blocker": bool(release_blocker and not passed),
        }
    )


def validate_qualification(path: Path, checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.is_file():
        add_check(checks, "macos_arm_qualification", False, f"missing {path}")
        return None
    data = read_json(path)
    source_sha = str(data.get("qualified_source_sha", ""))
    bundle = data.get("bundle", {})
    plugin = data.get("plugin", {})
    package = data.get("package", {})
    ci = data.get("ci", {})
    valid = (
        SOURCE_SHA_RE.fullmatch(source_sha) is not None
        and ci.get("overall_status") == "success"
        and ci.get("stata_status") == "success"
        and ci.get("rust_status") == "success"
        and int(bundle.get("file_count", 0)) == 477
        and int(bundle.get("zip_size_bytes", 0)) > 0
        and SHA256_RE.fullmatch(str(bundle.get("zip_sha256", ""))) is not None
        and int(plugin.get("size_bytes", 0)) > 0
        and SHA256_RE.fullmatch(str(plugin.get("sha256", ""))) is not None
        and package.get("net_install_tested") is True
    )
    add_check(
        checks,
        "macos_arm_qualification",
        valid,
        f"qualified source {source_sha or 'missing'}; CI={ci.get('overall_status')}",
    )
    return data


def validate_license_inventory(checks: list[dict[str, Any]]) -> None:
    inventory_path = Path("bundle/LICENSE_INVENTORY.json")
    if not inventory_path.is_file():
        add_check(checks, "license_mapping", False, "license inventory has not been generated")
        return
    inventory = read_json(inventory_path)
    summary = inventory.get("summary", {})
    complete = (
        int(summary.get("resource_count", 0)) == 477
        and int(summary.get("unmapped", -1)) == 0
        and int(summary.get("ambiguous", -1)) == 0
        and int(summary.get("missing_license", -1)) == 0
        and Path("bundle/LICENSE_MAPPING_COMPLETE").is_file()
    )
    add_check(
        checks,
        "license_mapping",
        complete,
        (
            f"resources={summary.get('resource_count')}; "
            f"unmapped={summary.get('unmapped')}; ambiguous={summary.get('ambiguous')}; "
            f"missing_license={summary.get('missing_license')}"
        ),
    )
    notices_complete = Path("bundle/LICENSE_TEXTS_COMPLETE").is_file()
    add_check(
        checks,
        "license_texts_and_notices",
        notices_complete,
        "required embedded-component license texts/notices are complete"
        if notices_complete
        else "license mapping may exist, but required release license texts/notices are not yet certified complete",
    )


def validate_memory(checks: list[dict[str, Any]]) -> None:
    path = Path("platform/macos-arm64-memory.json")
    if not path.is_file():
        add_check(
            checks,
            "macos_memory_stress",
            False,
            "no permanent 1000-call memory qualification record",
        )
        return
    data = read_json(path)
    passed = (
        int(data.get("iterations_requested", 0)) >= 1000
        and data.get("runner_rc") == 0
        and data.get("growth_gate") is True
    )
    add_check(
        checks,
        "macos_memory_stress",
        passed,
        (
            f"iterations={data.get('iterations_requested')}; "
            f"peak_stata_rss_kib={data.get('peak_stata_rss_kib')}; "
            f"post_warmup_growth_kib={data.get('post_warmup_growth_kib')}"
        ),
    )


def validate_platforms(checks: list[dict[str, Any]]) -> None:
    universal = REQUIRED_PLATFORM_RECORDS["macos_intel"]
    if universal.is_file():
        data = read_json(universal)
        architectures = set(data.get("architectures", []))
        build_ok = {"arm64", "x86_64"}.issubset(architectures)
        arm_runtime = data.get("arm_runtime_qualified") is True
        intel_runtime = data.get("intel_runtime_qualified") is True
        add_check(
            checks,
            "macos_universal_build",
            build_ok and arm_runtime,
            f"architectures={sorted(architectures)}; arm_runtime={arm_runtime}",
            release_blocker=False,
        )
        add_check(
            checks,
            "macos_intel_runtime",
            intel_runtime,
            "actual Intel Stata runtime qualification",
        )
    else:
        add_check(checks, "macos_universal_build", False, f"missing {universal}", release_blocker=False)
        add_check(checks, "macos_intel_runtime", False, f"missing {universal}")

    for key, label in (("linux_x86_64", "Linux x86-64"), ("windows_x86_64", "Windows x86-64")):
        path = REQUIRED_PLATFORM_RECORDS[key]
        if not path.is_file():
            add_check(checks, f"{key}_build", False, f"missing {path}", release_blocker=False)
            add_check(checks, f"{key}_runtime", False, f"no licensed {label} Stata qualification")
            continue
        data = read_json(path)
        build_ok = (
            int(data.get("plugin_size_bytes", 0)) > 0
            and SHA256_RE.fullmatch(str(data.get("plugin_sha256", ""))) is not None
            and data.get("rust_tests") == "success"
        )
        runtime_ok = data.get("stata_runtime_qualified") is True
        add_check(checks, f"{key}_build", build_ok, f"compiler/core build for {label}", release_blocker=False)
        add_check(checks, f"{key}_runtime", runtime_ok, f"actual licensed {label} Stata runtime qualification")


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# texpdf release-readiness audit",
        "",
        f"Implementation complete on qualified macOS ARM64 target: **{str(result['implementation_complete_macos_arm64']).lower()}**",
        f"Public cross-platform v1 ready: **{str(result['public_release_ready']).lower()}**",
        "",
        "| Check | Result | Release blocker | Detail |",
        "|---|---|---|---|",
    ]
    for check in result["checks"]:
        lines.append(
            f"| `{check['key']}` | {'PASS' if check['passed'] else 'FAIL'} | "
            f"{'yes' if check['release_blocker'] else 'no'} | {check['detail']} |"
        )
    lines.extend(["", "## Active public-release blockers", ""])
    blockers = result["release_blockers"]
    if blockers:
        lines.extend(f"- `{item}`" for item in blockers)
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=Path("RELEASE_READINESS.json"))
    parser.add_argument("--markdown", type=Path, default=Path("RELEASE_READINESS.md"))
    parser.add_argument("--require-public-release-ready", action="store_true")
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    for file_name in REQUIRED_PACKAGE_FILES:
        add_check(
            checks,
            f"package_file_{Path(file_name).name}",
            Path(file_name).is_file(),
            file_name,
        )
    add_check(checks, "cargo_lock", Path("Cargo.lock").is_file(), "Cargo.lock is committed")
    validate_qualification(Path("bundle/QUALIFICATION.json"), checks)
    validate_license_inventory(checks)
    validate_memory(checks)
    validate_platforms(checks)

    mac_required = {
        "package_file_texpdf.ado",
        "package_file_texpdf.sthlp",
        "package_file_texpdf.pkg",
        "package_file_stata.toc",
        "cargo_lock",
        "macos_arm_qualification",
    }
    by_key = {check["key"]: check for check in checks}
    implementation_complete = all(by_key.get(key, {}).get("passed") for key in mac_required)
    blockers = [check["key"] for check in checks if check["release_blocker"]]
    result = {
        "schema_version": 1,
        "implementation_complete_macos_arm64": implementation_complete,
        "public_release_ready": not blockers,
        "release_blockers": blockers,
        "checks": checks,
    }
    args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(result), encoding="utf-8")
    print(
        "TEXPDF_RELEASE_AUDIT "
        f"macos_arm_complete={str(implementation_complete).lower()} "
        f"public_release_ready={str(not blockers).lower()} blockers={','.join(blockers)}"
    )
    if args.require_public_release_ready and blockers:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as error:
        print(f"TEXPDF_RELEASE_AUDIT_ERROR {error}", file=sys.stderr)
        raise SystemExit(2)
