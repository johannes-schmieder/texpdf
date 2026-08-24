#!/usr/bin/env python3
"""Generate a deterministic license inventory from Cargo metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


class CargoInventoryError(RuntimeError):
    """A Cargo metadata or license inventory failure."""


def cargo_metadata(cargo: str) -> dict[str, Any]:
    result = subprocess.run(
        [cargo, "metadata", "--format-version", "1", "--locked"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise CargoInventoryError(
            f"cargo metadata failed with {result.returncode}: {result.stderr.strip()}"
        )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CargoInventoryError(f"cargo metadata returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise CargoInventoryError("cargo metadata did not return an object")
    return value


def build_inventory(metadata: dict[str, Any]) -> dict[str, Any]:
    workspace_members = set(metadata.get("workspace_members", []))
    packages = []
    missing = []
    for package in metadata.get("packages", []):
        if not isinstance(package, dict):
            continue
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
        "schema_version": 1,
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
        "# Rust dependency license inventory",
        "",
        f"- Packages: {summary['package_count']}",
        f"- Workspace packages: {summary['workspace_package_count']}",
        f"- Third-party packages: {summary['third_party_package_count']}",
        f"- Packages missing license metadata: {summary['missing_license_metadata']}",
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
        "--output", type=Path, default=Path("licenses/CARGO_LICENSE_INVENTORY.json")
    )
    parser.add_argument(
        "--markdown", type=Path, default=Path("licenses/CARGO_LICENSE_INVENTORY.md")
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    data = build_inventory(cargo_metadata(args.cargo))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(data), encoding="utf-8")
    print(
        "TEXPDF_CARGO_LICENSE_INVENTORY "
        + " ".join(f"{key}={value}" for key, value in data["summary"].items() if key != "license_expressions")
    )
    if args.strict and data["summary"]["missing_license_metadata"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, CargoInventoryError) as error:
        print(f"TEXPDF_CARGO_LICENSE_ERROR {error}", file=sys.stderr)
        raise SystemExit(2)
