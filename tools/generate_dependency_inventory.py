#!/usr/bin/env python3
"""Generate the Rust/native inventory for one texpdf release plugin graph."""

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


def rust_inventory(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package in packages:
        rows.append(
            {
                "name": package["name"],
                "version": package["version"],
                "license": package.get("license"),
                "license_file": package.get("license_file"),
                "repository": package.get("repository"),
                "source": package.get("source"),
            }
        )
    return sorted(rows, key=lambda item: (item["name"], item["version"]))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Generated release dependency inventory",
        "",
        f"Release roots: `{', '.join(payload['release_roots'])}`  ",
        f"Release target: `{payload['release_target']}`",
        "",
        "This inventory follows the normal/build dependency closure of the",
        "released plugin and embedded helper. It excludes dev/test-only and",
        "unrelated workspace crates.",
        "It does not replace corresponding license texts or the TeX resource audit.",
        "",
        "## Rust packages",
        "",
        "| Package | Version | Declared license | Repository |",
        "|---|---:|---|---|",
    ]
    for item in payload["rust_packages"]:
        repository = item.get("repository") or ""
        license_expression = (
            item.get("license") or item.get("license_file") or "UNDECLARED"
        )
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
        lines.append(
            f"| `{item['name']}` | `{item['license']}` | {item['role']} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


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
        "--json", type=Path, default=Path("licenses/generated/dependencies.json")
    )
    parser.add_argument(
        "--markdown", type=Path, default=Path("licenses/generated/dependencies.md")
    )
    parser.add_argument("--require-declared", action="store_true")
    args = parser.parse_args()

    try:
        metadata = cargo_metadata(args.cargo, args.target)
        package_names = args.packages or list(DEFAULT_RELEASE_ROOTS)
        packages = rust_inventory(
            release_packages_for_roots(metadata, package_names)
        )
    except (OSError, CargoGraphError, json.JSONDecodeError) as error:
        print(f"TEXPDF_LICENSE_INVENTORY_ERROR {error}", file=sys.stderr)
        return 2

    undeclared = [
        f"{item['name']}@{item['version']}"
        for item in packages
        if not item.get("license") and not item.get("license_file")
    ]
    payload = {
        "schema_version": 3,
        "release_roots": package_names,
        "release_target": args.target,
        "rust_packages": packages,
        "native_libraries": NATIVE_DEPENDENCIES,
        "undeclared_rust_licenses": undeclared,
    }
    write_json(args.json, payload)
    write_markdown(args.markdown, payload)
    print(
        "TEXPDF_DEPENDENCY_INVENTORY_READY "
        f"rust_packages={len(packages)} native_libraries={len(NATIVE_DEPENDENCIES)} "
        f"undeclared={len(undeclared)} target={args.target} "
        f"roots={','.join(package_names)}"
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
