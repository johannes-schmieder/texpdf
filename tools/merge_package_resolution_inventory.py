#!/usr/bin/env python3
"""Strengthen a TeX resource inventory with package-resolution provenance."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("licenses/generated/tex-resources.json"),
    )
    parser.add_argument(
        "--resolution",
        type=Path,
        default=Path("bundle/package-resolution.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        inventory = load(args.inventory)
        resolution = load(args.resolution)
    except (OSError, json.JSONDecodeError) as error:
        print(f"TEXPDF_PACKAGE_LICENSE_MERGE_ERROR {error}", file=sys.stderr)
        return 2

    embedded = {
        record["resource"]
        for record in inventory.get("resolved_resources", [])
        if isinstance(record, dict) and record.get("resource")
    }
    embedded.update(inventory.get("unresolved_resources", []))
    embedded.update(
        record["resource"]
        for record in inventory.get("ambiguous_resources", [])
        if isinstance(record, dict) and record.get("resource")
    )

    evidence: dict[str, set[str]] = defaultdict(set)
    methods: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in resolution.get("matches", []):
        if not isinstance(record, dict):
            continue
        resource = record.get("resource")
        package = record.get("package")
        if resource in embedded and package:
            evidence[resource].add(package)
            methods[(resource, package)].add(record.get("method") or "match")
    for record in resolution.get("ambiguous_runfiles", []):
        if not isinstance(record, dict):
            continue
        package = record.get("package")
        if not package:
            continue
        for resource in record.get("candidates", []):
            if resource in embedded:
                evidence[resource].add(package)
                methods[(resource, package)].add("ambiguous_candidate_union")

    package_metadata = {
        record["name"]: record
        for record in resolution.get("packages", [])
        if isinstance(record, dict) and record.get("name")
    }
    inventory_packages = {
        record["name"]: record
        for record in inventory.get("packages", [])
        if isinstance(record, dict) and record.get("name")
    }

    existing_resolution = {
        record["resource"]: record
        for record in inventory.get("resolved_resources", [])
        if isinstance(record, dict) and record.get("resource")
    }
    unresolved = set(inventory.get("unresolved_resources", []))
    ambiguous = {
        record["resource"]: record
        for record in inventory.get("ambiguous_resources", [])
        if isinstance(record, dict) and record.get("resource")
    }
    applied: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for resource in sorted(evidence):
        packages = evidence[resource]
        if len(packages) != 1:
            conflicts.append({"resource": resource, "packages": sorted(packages)})
            continue
        package = next(iter(packages))
        current = existing_resolution.get(resource)
        if current is not None and current.get("package") not in {None, package}:
            conflicts.append(
                {
                    "resource": resource,
                    "packages": sorted({package, str(current.get("package"))}),
                    "reason": "generated inventory and package resolver disagree",
                }
            )
            continue
        existing_resolution[resource] = {
            "resource": resource,
            "package": package,
            "mapping_source": "texlive_package_resolution",
            "methods": sorted(methods[(resource, package)]),
        }
        unresolved.discard(resource)
        ambiguous.pop(resource, None)
        applied.append(existing_resolution[resource])

        metadata = package_metadata.get(package, {})
        license_value = metadata.get("license")
        current_package = inventory_packages.setdefault(
            package,
            {
                "name": package,
                "catalogue_version": metadata.get("catalogue_version"),
                "license": license_value,
            },
        )
        if current_package.get("license") in {None, license_value}:
            current_package["license"] = license_value
        elif license_value:
            conflicts.append(
                {
                    "package": package,
                    "licenses": sorted(
                        {str(current_package.get("license")), str(license_value)}
                    ),
                    "reason": "conflicting package license metadata",
                }
            )

    missing_license_packages = sorted(
        package["name"]
        for package in inventory_packages.values()
        if not package.get("license")
    )
    inventory["resolved_resources"] = [
        existing_resolution[name] for name in sorted(existing_resolution)
    ]
    inventory["unresolved_resources"] = sorted(unresolved)
    inventory["ambiguous_resources"] = [ambiguous[name] for name in sorted(ambiguous)]
    inventory["packages"] = [inventory_packages[name] for name in sorted(inventory_packages)]
    inventory["packages_without_license_metadata"] = missing_license_packages
    inventory["package_resolution_merge"] = {
        "source": str(args.resolution),
        "applied_count": len(applied),
        "conflicts": conflicts,
    }
    inventory["license_complete"] = not (
        inventory["unresolved_resources"]
        or inventory["ambiguous_resources"]
        or missing_license_packages
        or conflicts
    )

    output = args.output or args.inventory
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "TEXPDF_PACKAGE_LICENSE_MERGE_READY "
        f"applied={len(applied)} conflicts={len(conflicts)} "
        f"unresolved={len(inventory['unresolved_resources'])} "
        f"ambiguous={len(inventory['ambiguous_resources'])} "
        f"license_complete={str(inventory['license_complete']).lower()}"
    )
    return 0 if inventory["license_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
