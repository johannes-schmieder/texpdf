#!/usr/bin/env python3
"""Map the embedded TeX resources to TeX Live packages and license metadata.

The tool fails closed. It accepts either a generated curated manifest or the
actual deterministic ZIP as the source of embedded logical names. TeX Live's
`texlive.tlpdb` is supplied explicitly so releases can pin the historic 2022
metadata matching the v33 source bundle.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any
import zipfile

LICENSE_KEYS = ("catalogue-license", "license")
SECTION_RE = re.compile(r"^[a-z][a-z0-9-]*\s")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return str(PurePosixPath(path))


def extract_manifest_names(payload: Any) -> set[str]:
    names: set[str] = set()

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, str):
            if key in {"name", "path", "logical_name", "resource", "target"}:
                names.add(normalize_path(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    names.add(normalize_path(item))
                else:
                    visit(item, key)
        elif isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, child_key)

    visit(payload)
    return {name for name in names if name and name != "."}


def embedded_resources(manifest: Path | None, bundle_zip: Path | None) -> tuple[set[str], str]:
    if manifest is not None and manifest.is_file():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        names = extract_manifest_names(payload)
        if names:
            return names, f"manifest:{manifest}"
    if bundle_zip is not None and bundle_zip.is_file():
        with zipfile.ZipFile(bundle_zip) as archive:
            names = {
                normalize_path(name)
                for name in archive.namelist()
                if not name.endswith("/") and name != "SHA256SUM"
            }
        return names, f"zip:{bundle_zip}"
    raise FileNotFoundError("no usable curated manifest or bundle ZIP")


def parse_tlpdb(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    packages: dict[str, dict[str, Any]] = {}
    path_to_packages: dict[str, set[str]] = defaultdict(set)
    current: dict[str, Any] | None = None
    current_file_section = False

    def finish() -> None:
        nonlocal current
        if current is None or not current.get("name"):
            current = None
            return
        name = str(current["name"])
        packages[name] = current
        for resource in current.get("files", []):
            path_to_packages[normalize_path(resource)].add(name)
        current = None

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("name "):
            finish()
            current = {"name": raw[5:].strip(), "files": [], "license": None}
            current_file_section = False
            continue
        if current is None:
            continue
        if not raw:
            current_file_section = False
            continue
        if raw.startswith("runfiles ") or raw.startswith("docfiles ") or raw.startswith("srcfiles "):
            current_file_section = True
            continue
        if raw[0].isspace() and current_file_section:
            value = raw.strip().split(" ", 1)[0]
            if value and not value.startswith("RELOC/"):
                current["files"].append(value)
            elif value.startswith("RELOC/"):
                current["files"].append("texmf-dist/" + value[6:])
            continue
        current_file_section = False
        for key in LICENSE_KEYS:
            prefix = key + " "
            if raw.startswith(prefix):
                current["license"] = raw[len(prefix) :].strip()
                break
        if raw.startswith("catalogue-version "):
            current["catalogue_version"] = raw[len("catalogue-version ") :].strip()
    finish()
    return packages, path_to_packages


def build_basename_index(path_to_packages: dict[str, set[str]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for path, packages in path_to_packages.items():
        index[PurePosixPath(path).name].update(packages)
    return index


def package_candidates(
    resource: str,
    exact: dict[str, set[str]],
    basename: dict[str, set[str]],
) -> set[str]:
    normalized = normalize_path(resource)
    candidates = set(exact.get(normalized, set()))
    if normalized.startswith("texmf-dist/"):
        candidates.update(exact.get(normalized[len("texmf-dist/") :], set()))
    else:
        candidates.update(exact.get("texmf-dist/" + normalized, set()))
    if candidates:
        return candidates
    return set(basename.get(PurePosixPath(normalized).name, set()))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tlpdb", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("bundle/generated/curated-manifest.json"))
    parser.add_argument("--bundle-zip", type=Path, default=Path("bundle/generated/texpdf-bundle.zip"))
    parser.add_argument("--output", type=Path, default=Path("licenses/generated/tex-resources.json"))
    parser.add_argument("--bundle-sha256")
    args = parser.parse_args()

    try:
        resources, resource_source = embedded_resources(args.manifest, args.bundle_zip)
        packages, exact_index = parse_tlpdb(args.tlpdb)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"TEXPDF_TEX_LICENSE_ERROR {error}", file=sys.stderr)
        return 2

    basename_index = build_basename_index(exact_index)
    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    ambiguous: list[dict[str, Any]] = []
    package_names: set[str] = set()

    for resource in sorted(resources):
        candidates = package_candidates(resource, exact_index, basename_index)
        if len(candidates) == 1:
            package = next(iter(candidates))
            package_names.add(package)
            resolved.append({"resource": resource, "package": package})
        elif not candidates:
            unresolved.append(resource)
        else:
            ambiguous.append({"resource": resource, "packages": sorted(candidates)})

    package_inventory = []
    missing_license_packages = []
    for name in sorted(package_names):
        package = packages[name]
        license_value = package.get("license")
        if not license_value:
            missing_license_packages.append(name)
        package_inventory.append(
            {
                "name": name,
                "catalogue_version": package.get("catalogue_version"),
                "license": license_value,
            }
        )

    bundle_digest = args.bundle_sha256
    if not bundle_digest and args.bundle_zip.is_file():
        bundle_digest = sha256(args.bundle_zip)
    license_complete = not unresolved and not ambiguous and not missing_license_packages
    payload = {
        "schema_version": 1,
        "resource_source": resource_source,
        "tlpdb_sha256": sha256(args.tlpdb),
        "bundle_zip_sha256": bundle_digest,
        "resource_count": len(resources),
        "resolved_resources": resolved,
        "unresolved_resources": unresolved,
        "ambiguous_resources": ambiguous,
        "packages": package_inventory,
        "packages_without_license_metadata": missing_license_packages,
        "license_complete": license_complete,
    }
    write_json(args.output, payload)
    print(
        "TEXPDF_TEX_LICENSE_INVENTORY_READY "
        f"resources={len(resources)} resolved={len(resolved)} "
        f"unresolved={len(unresolved)} ambiguous={len(ambiguous)} "
        f"packages={len(package_inventory)} license_complete={str(license_complete).lower()}"
    )
    return 0 if license_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
