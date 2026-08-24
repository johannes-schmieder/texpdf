#!/usr/bin/env python3
"""Generate a deterministic Rust/native dependency inventory for texpdf."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

NATIVE_DEPENDENCIES = [
    {
        "name": "fontconfig",
        "license": "MIT-style Fontconfig license",
        "role": "font discovery/configuration used by the embedded engine",
    },
    {
        "name": "freetype",
        "license": "FTL OR GPL-2.0-or-later",
        "role": "font rasterization",
    },
    {
        "name": "graphite2",
        "license": "MPL-2.0",
        "role": "Graphite smart-font shaping",
    },
    {
        "name": "harfbuzz",
        "license": "MIT",
        "role": "OpenType text shaping",
    },
    {
        "name": "icu",
        "license": "ICU",
        "role": "Unicode and internationalization support",
    },
    {
        "name": "libpng",
        "license": "libpng-2.0",
        "role": "PNG image support",
    },
    {
        "name": "zlib",
        "license": "Zlib",
        "role": "compression support",
    },
]


def cargo_metadata() -> dict[str, Any]:
    result = subprocess.run(
        ["cargo", "metadata", "--locked", "--format-version", "1"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("cargo metadata failed")
    return json.loads(result.stdout)


def rust_inventory(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for package in metadata.get("packages", []):
        packages.append(
            {
                "name": package["name"],
                "version": package["version"],
                "license": package.get("license"),
                "license_file": package.get("license_file"),
                "repository": package.get("repository"),
                "source": package.get("source"),
            }
        )
    return sorted(packages, key=lambda item: (item["name"], item["version"]))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Generated dependency inventory",
        "",
        "This file inventories declared dependency licenses. It does not replace",
        "the corresponding license texts or the separate TeX resource inventory.",
        "",
        "## Rust packages",
        "",
        "| Package | Version | Declared license | Repository |",
        "|---|---:|---|---|",
    ]
    for item in payload["rust_packages"]:
        repository = item.get("repository") or ""
        license_expression = item.get("license") or item.get("license_file") or "UNDECLARED"
        lines.append(
            f"| `{item['name']}` | `{item['version']}` | "
            f"`{license_expression}` | {repository} |"
        )
    lines.extend(
        [
            "",
            "## Native libraries",
            "",
            "| Library | License | Role |",
            "|---|---|---|",
        ]
    )
    for item in payload["native_libraries"]:
        lines.append(f"| `{item['name']}` | `{item['license']}` | {item['role']} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json", type=Path, default=Path("licenses/generated/dependencies.json")
    )
    parser.add_argument(
        "--markdown", type=Path, default=Path("licenses/generated/dependencies.md")
    )
    parser.add_argument("--require-declared", action="store_true")
    args = parser.parse_args()

    try:
        packages = rust_inventory(cargo_metadata())
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"TEXPDF_LICENSE_INVENTORY_ERROR {error}", file=sys.stderr)
        return 2

    undeclared = [
        item["name"]
        for item in packages
        if not item.get("license") and not item.get("license_file")
    ]
    payload = {
        "schema_version": 1,
        "rust_packages": packages,
        "native_libraries": NATIVE_DEPENDENCIES,
        "undeclared_rust_licenses": undeclared,
    }
    write_json(args.json, payload)
    write_markdown(args.markdown, payload)
    print(
        "TEXPDF_DEPENDENCY_INVENTORY_READY "
        f"rust_packages={len(packages)} native_libraries={len(NATIVE_DEPENDENCIES)} "
        f"undeclared={len(undeclared)}"
    )
    if args.require_declared and undeclared:
        print(
            "Rust packages without a declared license/license-file: "
            + ", ".join(undeclared),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
