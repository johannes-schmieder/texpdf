#!/usr/bin/env python3
"""Generate a deterministic license inventory for one release plugin graph."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from cargo_release_graph import (
    CargoGraphError,
    cargo_metadata,
    release_packages_for_roots,
)

DEFAULT_RELEASE_ROOTS = ("texpdf-stata", "texpdf-helper")


class CargoInventoryError(RuntimeError):
    """A Cargo metadata or license inventory failure."""


def build_inventory(
    metadata: dict[str, Any],
    selected_packages: list[dict[str, Any]],
    package_names: list[str],
    target: str,
) -> dict[str, Any]:
    workspace_members = set(metadata.get("workspace_members", []))
    packages = []
    missing = []
    for package in selected_packages:
        package_id = str(package.get("id", ""))
        license_expression = package.get("license")
        license_file = package.get("license_file")
        row = {
            "name": package.get("name"),
            "version": package.get("version"),
            "license": license_expression,
            "license_file": license_file,
            "repository": package.get("repository"),
            "homepage": package.get("homepage"),
            "source": package.get("source"),
            "workspace_member": package_id in workspace_members,
        }
        if not license_expression and not license_file:
            missing.append(f"{row['name']} {row['version']}")
        packages.append(row)
    packages.sort(key=lambda item: (str(item["name"]), str(item["version"])))
    expressions = sorted(
        {str(item["license"]) for item in packages if item.get("license")}
    )
    return {
        "schema_version": 3,
        "release_roots": package_names,
        "release_target": target,
        "summary": {
            "package_count": len(packages),
            "workspace_package_count": sum(
                1 for item in packages if item["workspace_member"]
            ),
            "third_party_package_count": sum(
                1 for item in packages if not item["workspace_member"]
            ),
            "missing_license_metadata": len(missing),
            "license_expressions": expressions,
        },
        "missing_license_packages": missing,
        "packages": packages,
    }


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# Rust release dependency license inventory",
        "",
        f"- Release roots: `{', '.join(data['release_roots'])}`",
        f"- Release target: `{data['release_target']}`",
        f"- Packages: {summary['package_count']}",
        f"- Workspace packages: {summary['workspace_package_count']}",
        f"- Third-party packages: {summary['third_party_package_count']}",
        f"- Packages missing license metadata: {summary['missing_license_metadata']}",
        "",
        "The graph includes normal and build dependencies reachable from the",
        "release plugin plus embedded helper and excludes dev/test-only and",
        "unrelated workspace crates.",
        "",
        "| Crate | Version | License | Source |",
        "|---|---:|---|---|",
    ]
    for package in data["packages"]:
        license_value = package.get("license") or (
            f"license file: {package.get('license_file')}"
            if package.get("license_file")
            else "UNKNOWN"
        )
        source = package.get("repository") or package.get("source") or "workspace"
        lines.append(
            f"| `{package['name']}` | `{package['version']}` | `{license_value}` | {source} |"
        )
    if data["missing_license_packages"]:
        lines.extend(["", "## Missing license metadata", ""])
        lines.extend(f"- `{value}`" for value in data["missing_license_packages"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument(
        "--package",
        action="append",
        dest="packages",
        help="release root to audit; repeat for multiple installed binaries",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("TEXPDF_LICENSE_TARGET", "aarch64-apple-darwin"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("licenses/CARGO_LICENSE_INVENTORY.json")
    )
    parser.add_argument(
        "--markdown", type=Path, default=Path("licenses/CARGO_LICENSE_INVENTORY.md")
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    try:
        metadata = cargo_metadata(args.cargo, args.target)
        package_names = args.packages or list(DEFAULT_RELEASE_ROOTS)
        data = build_inventory(
            metadata,
            release_packages_for_roots(metadata, package_names),
            package_names,
            args.target,
        )
    except (OSError, CargoGraphError, CargoInventoryError) as error:
        print(f"TEXPDF_CARGO_LICENSE_ERROR {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(data), encoding="utf-8")
    print(
        "TEXPDF_CARGO_LICENSE_INVENTORY "
        + " ".join(
            f"{key}={value}"
            for key, value in data["summary"].items()
            if key != "license_expressions"
        )
        + f" target={args.target} roots={','.join(package_names)}"
    )
    if args.strict and data["summary"]["missing_license_metadata"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
