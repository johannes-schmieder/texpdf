#!/usr/bin/env python3
"""Map every embedded TeX resource to TeX Live license metadata.

The generated inventory is conservative: ambiguous basename matches and
resources without a package/license mapping remain explicit review failures.
Reviewed non-TeX-Live resources can be mapped in bundle/license-overrides.toml.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import lzma
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FILE_SECTIONS = {"runfiles", "docfiles", "srcfiles", "binfiles"}
NAME_KEYS = ("name", "path", "logical_name", "resource", "filename")
ORIGIN_KEYS = ("origin", "source", "archive")


class InventoryError(RuntimeError):
    """A deterministic inventory construction failure."""


@dataclass
class Package:
    name: str
    license: str = ""
    shortdesc: str = ""
    files: list[str] = field(default_factory=list)


def normalize(name: str) -> str:
    value = name.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    for prefix in ("RELOC/", "texmf-dist/"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value


def resource_name(entry: dict[str, Any], fallback: str | None = None) -> str | None:
    for key in NAME_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return normalize(value)
    return normalize(fallback) if fallback else None


def resource_origin(entry: dict[str, Any]) -> str:
    for key in ORIGIN_KEYS:
        value = entry.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for subkey in ("name", "kind", "archive"):
                subvalue = value.get(subkey)
                if isinstance(subvalue, str):
                    return subvalue
    return "unknown"


def rows_from(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, list):
        iterable = [(None, item) for item in value]
    elif isinstance(value, dict):
        iterable = list(value.items())
    else:
        return rows
    for fallback, item in iterable:
        if not isinstance(item, dict):
            continue
        name = resource_name(item, str(fallback) if fallback is not None else None)
        if name and not name.endswith("/"):
            rows.append({"name": name, "origin": resource_origin(item)})
    return rows


def manifest_resources(manifest: dict[str, Any]) -> list[dict[str, str]]:
    for key in ("selected", "selected_resources", "resources", "files", "entries"):
        rows = rows_from(manifest.get(key))
        if rows:
            break
    else:
        candidates: list[list[dict[str, str]]] = []

        def visit(value: Any) -> None:
            rows = rows_from(value)
            if rows:
                candidates.append(rows)
            if isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(manifest)
        if not candidates:
            raise InventoryError("cannot locate resource records in curated manifest")
        rows = max(candidates, key=len)

    by_name: dict[str, dict[str, str]] = {}
    for row in rows:
        name = row["name"]
        if name not in by_name or by_name[name]["origin"] == "unknown":
            by_name[name] = row
    resources = [by_name[name] for name in sorted(by_name)]
    expected = manifest.get("file_count") or manifest.get("selected_file_count")
    if expected is not None and int(expected) != len(resources):
        raise InventoryError(
            f"manifest reports {expected} files but {len(resources)} resource records were found"
        )
    return resources


def read_tlpdb(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix == ".xz":
        raw = lzma.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def parse_tlpdb(path: Path) -> dict[str, Package]:
    packages: dict[str, Package] = {}
    current: Package | None = None
    section = ""
    for raw in read_tlpdb(path).splitlines():
        if not raw.strip():
            if current is not None:
                packages[current.name] = current
            current = None
            section = ""
            continue
        if raw.startswith("name "):
            if current is not None:
                packages[current.name] = current
            current = Package(raw[5:].strip())
            section = ""
            continue
        if current is None:
            continue
        if raw[0].isspace():
            if section in FILE_SECTIONS:
                current.files.append(normalize(raw.strip().split()[0]))
            continue
        key, _, value = raw.partition(" ")
        if key in FILE_SECTIONS:
            section = key
        else:
            section = ""
            if key == "catalogue-license":
                current.license = value.strip().lower()
            elif key == "shortdesc":
                current.shortdesc = value.strip()
    if current is not None:
        packages[current.name] = current
    if not packages:
        raise InventoryError(f"no package records parsed from {path}")
    return packages


def load_overrides(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    import tomllib

    values = tomllib.loads(path.read_text(encoding="utf-8")).get("override", [])
    if not isinstance(values, list):
        raise InventoryError("license overrides must use [[override]] tables")
    result = []
    for number, item in enumerate(values, 1):
        if not isinstance(item, dict):
            raise InventoryError(f"override {number} is not a table")
        required = (item.get("pattern"), item.get("package"), item.get("license"))
        if not all(isinstance(value, str) and value for value in required):
            raise InventoryError(f"override {number} requires pattern, package, and license")
        result.append(
            {
                "pattern": str(item["pattern"]),
                "origin": str(item.get("origin", "")),
                "package": str(item["package"]),
                "license": str(item["license"]).lower(),
                "reason": str(item.get("reason", "")),
            }
        )
    return result


def matching_override(
    name: str, origin: str, overrides: list[dict[str, str]]
) -> dict[str, str] | None:
    matches = [
        item
        for item in overrides
        if (not item["origin"] or item["origin"] == origin)
        and fnmatch.fnmatchcase(name, item["pattern"])
    ]
    if len(matches) > 1:
        raise InventoryError(f"multiple overrides match {name}: {matches}")
    return matches[0] if matches else None


def build_inventory(
    resources: list[dict[str, str]],
    packages: dict[str, Package],
    overrides: list[dict[str, str]],
) -> dict[str, Any]:
    exact: dict[str, set[str]] = defaultdict(set)
    basenames: dict[str, set[str]] = defaultdict(set)
    for package in packages.values():
        for name in package.files:
            exact[name].add(package.name)
            basenames[Path(name).name].add(package.name)

    counts: dict[str, int] = defaultdict(int)
    usage: dict[str, set[str]] = defaultdict(set)
    resource_rows = []

    for resource in resources:
        name = resource["name"]
        origin = resource["origin"]
        override = matching_override(name, origin, overrides)
        note = ""
        if override is not None:
            package_names = [override["package"]]
            licenses = [override["license"]]
            method = "override"
            note = override["reason"]
        else:
            candidates = set(exact.get(name, set()))
            method = "exact"
            if not candidates:
                candidates = set(basenames.get(Path(name).name, set()))
                method = "basename"
            package_names = sorted(candidates)
            licenses = sorted(
                {packages[value].license for value in package_names if packages[value].license}
            )
            if not package_names:
                method = "unmapped"
            elif len(package_names) > 1:
                method += "-ambiguous"

        if not package_names:
            status = "unmapped"
        elif not licenses:
            status = "missing-license"
        elif "ambiguous" in method:
            status = "ambiguous"
        else:
            status = "mapped"
        counts[status] += 1
        counts[method] += 1
        for package_name in package_names:
            usage[package_name].add(name)
        resource_rows.append(
            {
                "name": name,
                "origin": origin,
                "status": status,
                "method": method,
                "packages": package_names,
                "licenses": licenses,
                "note": note,
            }
        )

    package_rows = {}
    for name in sorted(usage):
        package = packages.get(name)
        if package is None:
            license_values = sorted(
                {
                    row["licenses"][0]
                    for row in resource_rows
                    if name in row["packages"] and row["licenses"]
                }
            )
            package_rows[name] = {
                "license": ",".join(license_values),
                "shortdesc": "explicit reviewed override",
                "resource_count": len(usage[name]),
            }
        else:
            package_rows[name] = {
                "license": package.license,
                "shortdesc": package.shortdesc,
                "resource_count": len(usage[name]),
            }

    return {
        "schema_version": 1,
        "summary": {
            "resource_count": len(resources),
            "package_count": len(package_rows),
            "mapped": counts["mapped"],
            "ambiguous": counts["ambiguous"],
            "unmapped": counts["unmapped"],
            "missing_license": counts["missing-license"],
            "exact": counts["exact"],
            "basename": counts["basename"],
            "override": counts["override"],
        },
        "packages": package_rows,
        "resources": resource_rows,
    }


def render_markdown(data: dict[str, Any], metadata_source: str) -> str:
    summary = data["summary"]
    lines = [
        "# Embedded TeX resource license inventory",
        "",
        f"Metadata source: `{metadata_source}`",
        "",
        "## Coverage",
        "",
        f"- Embedded resources: {summary['resource_count']}",
        f"- Referenced packages/components: {summary['package_count']}",
        f"- Unambiguous mappings: {summary['mapped']}",
        f"- Ambiguous conservative mappings: {summary['ambiguous']}",
        f"- Unmapped resources: {summary['unmapped']}",
        f"- Mappings without a license code: {summary['missing_license']}",
        "",
        "## Packages and components",
        "",
        "| Component | License code | Embedded resources |",
        "|---|---|---:|",
    ]
    for name, package in data["packages"].items():
        lines.append(
            f"| `{name}` | `{package['license'] or 'UNKNOWN'}` | {package['resource_count']} |"
        )
    review = [row for row in data["resources"] if row["status"] != "mapped"]
    lines.extend(["", "## Items requiring review", ""])
    if not review:
        lines.append("No unmapped, ambiguous, or missing-license resources remain.")
    else:
        lines.extend(
            [
                "| Resource | Origin | Status | Candidate component(s) | License code(s) |",
                "|---|---|---|---|---|",
            ]
        )
        for row in review:
            packages = ", ".join(f"`{value}`" for value in row["packages"]) or "—"
            licenses = ", ".join(f"`{value}`" for value in row["licenses"]) or "—"
            lines.append(
                f"| `{row['name']}` | `{row['origin']}` | `{row['status']}` | {packages} | {licenses} |"
            )
    lines.extend(
        [
            "",
            "This inventory records package/component metadata. Public release also requires the corresponding license texts and notices in the installation package.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tlpdb", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    data = build_inventory(
        manifest_resources(manifest),
        parse_tlpdb(args.tlpdb),
        load_overrides(args.overrides),
    )
    data["metadata_source"] = str(args.tlpdb)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(data, str(args.tlpdb)), encoding="utf-8")
    print(
        "TEXPDF_LICENSE_INVENTORY "
        + " ".join(f"{key}={value}" for key, value in data["summary"].items())
    )
    if args.strict and any(
        data["summary"][key] for key in ("unmapped", "ambiguous", "missing_license")
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
