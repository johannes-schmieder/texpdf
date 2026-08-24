#!/usr/bin/env python3
"""Apply explicitly reviewed mappings to a generated TeX resource inventory."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def package_record(name: str, license_value: str, source: str) -> dict[str, Any]:
    return {
        "name": name,
        "catalogue_version": None,
        "license": license_value,
        "metadata_source": source,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("licenses/generated/tex-resources.json"),
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=Path("licenses/tex-resource-overrides.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        inventory = load(args.inventory)
        overrides = load(args.overrides)
    except (OSError, json.JSONDecodeError) as error:
        print(f"TEXPDF_TEX_OVERRIDE_ERROR {error}", file=sys.stderr)
        return 2

    if overrides.get("schema_version") != 1:
        print("override schema_version must be 1", file=sys.stderr)
        return 2
    reviewer = str(overrides.get("reviewed_by") or "").strip()
    reviewed_at = str(overrides.get("reviewed_at") or "").strip()
    if overrides.get("mappings") or overrides.get("standalone_resources"):
        if not reviewer or not reviewed_at:
            print("nonempty overrides require reviewed_by and reviewed_at", file=sys.stderr)
            return 2
        try:
            datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except ValueError:
            print("reviewed_at must be an ISO-8601 timestamp", file=sys.stderr)
            return 2

    unresolved = set(inventory.get("unresolved_resources", []))
    ambiguous_records = {
        item["resource"]: item
        for item in inventory.get("ambiguous_resources", [])
        if isinstance(item, dict) and "resource" in item
    }
    available = unresolved | set(ambiguous_records)
    resolved = list(inventory.get("resolved_resources", []))
    packages = {
        item["name"]: item
        for item in inventory.get("packages", [])
        if isinstance(item, dict) and "name" in item
    }
    applied: list[dict[str, Any]] = []

    mappings = overrides.get("mappings") or {}
    if not isinstance(mappings, dict):
        print("mappings must be an object", file=sys.stderr)
        return 2
    for resource, mapping in sorted(mappings.items()):
        if resource not in available:
            print(f"override references a resource that is not unresolved/ambiguous: {resource}", file=sys.stderr)
            return 2
        if not isinstance(mapping, dict):
            print(f"mapping for {resource} must be an object", file=sys.stderr)
            return 2
        package = str(mapping.get("package") or "").strip()
        license_value = str(mapping.get("license") or "").strip()
        rationale = str(mapping.get("rationale") or "").strip()
        if not package or not license_value or not rationale:
            print(
                f"mapping for {resource} requires package, license, and rationale",
                file=sys.stderr,
            )
            return 2
        resolved.append(
            {
                "resource": resource,
                "package": package,
                "mapping_source": "reviewed_override",
                "rationale": rationale,
            }
        )
        packages.setdefault(
            package,
            package_record(package, license_value, "reviewed_override"),
        )
        if packages[package].get("license") not in {None, license_value}:
            print(f"conflicting license metadata for package {package}", file=sys.stderr)
            return 2
        packages[package]["license"] = license_value
        unresolved.discard(resource)
        ambiguous_records.pop(resource, None)
        applied.append({"resource": resource, "kind": "package", "package": package})

    standalone = overrides.get("standalone_resources") or {}
    if not isinstance(standalone, dict):
        print("standalone_resources must be an object", file=sys.stderr)
        return 2
    reviewed_standalone: list[dict[str, Any]] = []
    for resource, mapping in sorted(standalone.items()):
        if resource not in available:
            print(f"standalone override references an unknown resource: {resource}", file=sys.stderr)
            return 2
        if not isinstance(mapping, dict):
            print(f"standalone mapping for {resource} must be an object", file=sys.stderr)
            return 2
        license_value = str(mapping.get("license") or "").strip()
        notice = str(mapping.get("notice_file") or "").strip()
        rationale = str(mapping.get("rationale") or "").strip()
        if not license_value or not notice or not rationale:
            print(
                f"standalone mapping for {resource} requires license, notice_file, and rationale",
                file=sys.stderr,
            )
            return 2
        if not Path(notice).is_file():
            print(f"standalone notice file does not exist: {notice}", file=sys.stderr)
            return 2
        reviewed_standalone.append(
            {
                "resource": resource,
                "license": license_value,
                "notice_file": notice,
                "rationale": rationale,
                "mapping_source": "reviewed_override",
            }
        )
        unresolved.discard(resource)
        ambiguous_records.pop(resource, None)
        applied.append({"resource": resource, "kind": "standalone"})

    missing_license_packages = sorted(
        item["name"] for item in packages.values() if not item.get("license")
    )
    inventory["resolved_resources"] = sorted(
        resolved, key=lambda item: (item.get("resource", ""), item.get("package", ""))
    )
    inventory["unresolved_resources"] = sorted(unresolved)
    inventory["ambiguous_resources"] = [
        ambiguous_records[name] for name in sorted(ambiguous_records)
    ]
    inventory["packages"] = [packages[name] for name in sorted(packages)]
    inventory["packages_without_license_metadata"] = missing_license_packages
    inventory["reviewed_standalone_resources"] = reviewed_standalone
    inventory["applied_overrides"] = applied
    inventory["override_review"] = {
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
        "source": str(args.overrides),
    }
    inventory["license_complete"] = not (
        inventory["unresolved_resources"]
        or inventory["ambiguous_resources"]
        or missing_license_packages
    )

    output = args.output or args.inventory
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "TEXPDF_TEX_OVERRIDES_APPLIED "
        f"applied={len(applied)} unresolved={len(inventory['unresolved_resources'])} "
        f"ambiguous={len(inventory['ambiguous_resources'])} "
        f"license_complete={str(inventory['license_complete']).lower()}"
    )
    return 0 if inventory["license_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
