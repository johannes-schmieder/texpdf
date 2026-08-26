#!/usr/bin/env python3
"""Collect license/notice texts for one release plugin dependency graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

from cargo_release_graph import (
    CargoGraphError,
    cargo_metadata,
    release_packages_for_roots,
)

DEFAULT_RELEASE_ROOTS = ("texpdf-stata", "texpdf-helper")

NOTICE_PREFIXES = (
    "LICENSE",
    "LICENCE",
    "COPYING",
    "COPYRIGHT",
    "NOTICE",
    "AUTHORS",
)
NOTICE_DIRECTORIES = ("LICENSES", "LICENCES")
NATIVE_PORTS = (
    "fontconfig",
    "freetype",
    "graphite2",
    "harfbuzz",
    "icu",
    "libpng",
    "zlib",
)
CANONICAL_SPDX_TEXTS = {
    "Apache-2.0": Path("licenses/canonical/Apache-2.0.txt"),
    "MIT": Path("licenses/canonical/MIT.txt"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def notice_files(root: Path, *, include_notice_directories: bool = True) -> list[Path]:
    candidates: set[Path] = set()
    for path in root.iterdir():
        if path.is_file():
            upper = path.name.upper()
            if any(upper.startswith(prefix) for prefix in NOTICE_PREFIXES):
                candidates.add(path)
        elif (
            include_notice_directories
            and path.is_dir()
            and path.name.upper() in NOTICE_DIRECTORIES
        ):
            candidates.update(child for child in path.rglob("*") if child.is_file())
    return sorted(candidates, key=lambda path: path.as_posix().casefold())


def safe_component(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in value
    )


def portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def copy_notices(
    source_root: Path,
    destination: Path,
    *,
    source_label: str,
    include_notice_directories: bool = True,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    destination.mkdir(parents=True, exist_ok=True)
    for source in notice_files(
        source_root, include_notice_directories=include_notice_directories
    ):
        relative = source.relative_to(source_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append(
            {
                "source": f"{source_label}/{relative.as_posix()}",
                "file": portable_path(target),
                "sha256": sha256(target),
                "size_bytes": target.stat().st_size,
            }
        )
    return records


def canonical_spdx_components(expression: object) -> list[str]:
    """Accept only simple standard expressions covered by committed texts."""

    if not isinstance(expression, str) or not expression:
        return []
    components = [value.strip() for value in expression.split(" OR ")]
    if not components or any(value not in CANONICAL_SPDX_TEXTS for value in components):
        return []
    return sorted(set(components))


def copy_canonical_spdx_texts(
    expression: object, destination: Path
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for component in canonical_spdx_components(expression):
        source = CANONICAL_SPDX_TEXTS[component]
        if not source.is_file():
            raise OSError(f"canonical SPDX text is missing: {source}")
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / source.name
        shutil.copyfile(source, target)
        records.append(
            {
                "source": f"repository:{source.as_posix()}",
                "file": portable_path(target),
                "sha256": sha256(target),
                "size_bytes": target.stat().st_size,
                "spdx_component": component,
            }
        )
    return records


def collect_rust(
    output_root: Path,
    metadata: dict[str, Any],
    package_names: list[str],
) -> list[dict[str, object]]:
    workspace_root = Path(metadata["workspace_root"])
    records: list[dict[str, object]] = []
    for package in release_packages_for_roots(metadata, package_names):
        manifest = Path(package["manifest_path"])
        package_root = manifest.parent
        destination = output_root / "rust" / safe_component(
            f"{package['name']}-{package['version']}"
        )
        package_label = f"cargo:{package['name']}@{package['version']}"
        notices = copy_notices(package_root, destination, source_label=package_label)
        notice_origin = "package"
        license_file = package.get("license_file")
        if license_file:
            license_path = Path(license_file)
            if not license_path.is_absolute():
                license_path = package_root / license_path
            if license_path.is_file() and all(
                Path(str(record["file"])).name != license_path.name
                for record in notices
            ):
                target = destination / license_path.name
                shutil.copyfile(license_path, target)
                notices.append(
                    {
                        "source": f"{package_label}/{license_path.name}",
                        "file": portable_path(target),
                        "sha256": sha256(target),
                        "size_bytes": target.stat().st_size,
                    }
                )
        if not notices and package.get("source") is None:
            # The repository's lowercase `licenses/` directory contains audit
            # inputs and generated outputs, not the project crate's license
            # payload. Recursing into it here previously copied the collector's
            # own output repeatedly for every workspace crate.
            notices = copy_notices(
                workspace_root,
                destination,
                source_label="repository:workspace",
                include_notice_directories=False,
            )
            notice_origin = "workspace_root"
        if not notices:
            notices = copy_canonical_spdx_texts(package.get("license"), destination)
            if notices:
                notice_origin = "canonical_spdx_text"
        records.append(
            {
                "name": package["name"],
                "version": package["version"],
                "license": package.get("license"),
                "license_file": package.get("license_file"),
                "source": package.get("source"),
                "repository": package.get("repository"),
                "notice_origin": notice_origin if notices else None,
                "notice_files": notices,
            }
        )
    return records


def find_native_copyright(
    vcpkg_root: Path, triplet: str, port: str
) -> Path | None:
    candidates = (
        vcpkg_root / "installed" / triplet / "share" / port / "copyright",
        vcpkg_root / "packages" / f"{port}_{triplet}" / "share" / port / "copyright",
        vcpkg_root / "ports" / port / "copyright",
    )
    return next((path for path in candidates if path.is_file()), None)


def collect_native(
    output_root: Path, vcpkg_root: Path | None, triplet: str | None
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for port in NATIVE_PORTS:
        source = (
            find_native_copyright(vcpkg_root, triplet, port)
            if vcpkg_root is not None and triplet
            else None
        )
        notices: list[dict[str, object]] = []
        if source is not None:
            destination = output_root / "native" / port
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / "copyright"
            shutil.copyfile(source, target)
            notices.append(
                {
                    "source": f"vcpkg:{port}/copyright",
                    "file": portable_path(target),
                    "sha256": sha256(target),
                    "size_bytes": target.stat().st_size,
                }
            )
        records.append(
            {
                "name": port,
                "vcpkg_triplet": triplet,
                "notice_files": notices,
            }
        )
    return records


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
        "--output-root", type=Path, default=Path("licenses/generated/texts")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("licenses/generated/license-texts.json")
    )
    parser.add_argument("--vcpkg-root", type=Path)
    parser.add_argument("--triplet")
    parser.add_argument("--require-native", action="store_true")
    args = parser.parse_args()

    vcpkg_root = args.vcpkg_root
    if vcpkg_root is None and os.environ.get("VCPKG_ROOT"):
        vcpkg_root = Path(os.environ["VCPKG_ROOT"])
    triplet = args.triplet or os.environ.get("VCPKGRS_TRIPLET")

    shutil.rmtree(args.output_root, ignore_errors=True)
    try:
        metadata = cargo_metadata(args.cargo, args.target)
        package_names = args.packages or list(DEFAULT_RELEASE_ROOTS)
        rust = collect_rust(args.output_root, metadata, package_names)
        native = collect_native(args.output_root, vcpkg_root, triplet)
    except (OSError, CargoGraphError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_LICENSE_TEXT_ERROR {error}", file=sys.stderr)
        return 2

    missing_rust_records = [
        {
            "name": record["name"],
            "version": record["version"],
            "license": record["license"],
            "repository": record["repository"],
            "source": record["source"],
        }
        for record in rust
        if not record["notice_files"]
    ]
    missing_rust = [
        f"{record['name']}@{record['version']}" for record in missing_rust_records
    ]
    missing_native = [
        record["name"] for record in native if not record["notice_files"]
    ]
    payload = {
        "schema_version": 4,
        "release_roots": package_names,
        "release_target": args.target,
        "rust_packages": rust,
        "native_libraries": native,
        "missing_rust_notice_files": missing_rust,
        "missing_rust_notice_records": missing_rust_records,
        "missing_native_notice_files": missing_native,
        "complete": not missing_rust and not missing_native,
        "canonical_spdx_policy": {
            "allowed_expressions": sorted(CANONICAL_SPDX_TEXTS),
            "rule": (
                "When a published crate declares only MIT, Apache-2.0, or an OR "
                "combination of those identifiers but ships no notice file, the "
                "release includes committed canonical SPDX texts and retains the "
                "crate name, version, declared expression, source, and repository "
                "in this manifest. Other expressions remain fail-closed."
            ),
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "TEXPDF_LICENSE_TEXTS_READY "
        f"rust={len(rust)} native={len(native)} "
        f"missing_rust={len(missing_rust)} missing_native={len(missing_native)} "
        f"target={args.target} roots={','.join(package_names)}"
    )
    if missing_rust or (args.require_native and missing_native):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
