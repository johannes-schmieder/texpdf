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
import sys
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


def resource_name(item: Any) -> str:
    if isinstance(item, str):
        return normalize(item)
    if not isinstance(item, dict):
        return ""
    for key in NAME_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            return normalize(value)
    return ""


def resource_origin(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ORIGIN_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def load_resources(manifest: dict[str, Any]) -> list[dict[str, str]]:
    candidates: Any = manifest.get("resources")
    if candidates is None:
        candidates = manifest.get("files")
    if candidates is None:
        candidates = manifest.get("entries")
    if not isinstance(candidates, list):
        raise InventoryError("curated manifest has no resources/files/entries list")
    resources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in candidates:
        name = resource_name(item)
        if not name or name == "SHA256SUM" or name in seen:
            continue
        seen.add(name)
        resources.append({"name": name, "origin": resource_origin(item)})
    if not resources:
        raise InventoryError("curated manifest contains no logical resources")
    return sorted(resources, key=lambda item: item["name"])


def read_tlpdb(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".xz" or data.startswith(b"\xfd7zXZ\x00"):
        data = lzma.decompress(data)
    return data.decode("utf-8", errors="replace")


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


def parse_simple_override_toml(text: str) -> dict[str, list[dict[str, str]]]:
    """Parse the deliberately narrow override-file TOML subset.

    The connected Stata runner uses the Xcode Python 3.9 interpreter, which has
    no standard-library ``tomllib``. Pulling an unpinned parser dependency into
    a release audit would weaken reproducibility, so the fallback accepts only
    repeated ``[[override]]`` tables and JSON-compatible quoted string values.
    Anything broader fails explicitly rather than being interpreted loosely.
    """

    tables: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[override]]":
            current = {}
            tables.append(current)
            continue
        if line.startswith("["):
            raise InventoryError(
                f"unsupported override TOML table on line {line_number}: {raw!r}"
            )
        if current is None:
            raise InventoryError(
                f"override value before [[override]] on line {line_number}"
            )
        key, separator, encoded = line.partition("=")
        key = key.strip()
        encoded = encoded.strip()
        if not separator or not key:
            raise InventoryError(f"malformed override line {line_number}: {raw!r}")
        if key in current:
            raise InventoryError(
                f"duplicate override key {key!r} on line {line_number}"
            )
        try:
            value = json.loads(encoded)
        except json.JSONDecodeError as error:
            raise InventoryError(
                f"override line {line_number} requires a quoted string value"
            ) from error
        if not isinstance(value, str):
            raise InventoryError(
                f"override line {line_number} value must be a string"
            )
        current[key] = value
    return {"override": tables}


def load_overrides(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        parsed: dict[str, Any] = parse_simple_override_toml(text)
    else:
        parsed = tomllib.loads(text)

    values = parsed.get("override", [])
    if not isinstance(values, list):
        raise InventoryError("license overrides must use [[override]] tables")
    result = []
    for number, item in enumerate(values, 1):
        if not isinstance(item, dict):
            raise InventoryError(f"override {number} is not a table")
        required = (item.get("pattern"), item.get("package"), item.get("license"))
        if not all(isinstance(value, str) and value for value in required):
            raise InventoryError(
                f"override {number} requires pattern, package, and license"
            )
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


def development_package(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("-dev") or "-dev-" in lowered


def prefer_stable_candidate(candidates: set[str]) -> tuple[set[str], str | None]:
    """Resolve stable-package versus development-mirror duplication.

    TeX Live 2022 contains development mirrors such as ``latex-base-dev`` and
    ``latex-graphics-dev`` whose runfiles duplicate the stable release package.
    When exactly one candidate is non-development and every alternative is a
    development package, selecting the stable package is deterministic and does
    not discard a competing stable ownership claim.
    """

    if len(candidates) <= 1:
        return candidates, None
    stable = {name for name in candidates if not development_package(name)}
    development = candidates.difference(stable)
    if len(stable) == 1 and development and all(
        development_package(name) for name in development
    ):
        return stable, "unique_stable_candidate_over_development_mirrors"
    return candidates, None


def build_inventory(
    resources: list[dict[str, str]],
    packages: dict[str, Package],
    overrides: list[dict[str, str]],
) -> dict[str, Any]:
    exact: dict[str, set[str]] = defaultdict(set)
    basename: dict[str, set[str]] = defaultdict(set)
    for package in packages.values():
        for item in package.files:
            exact[item].add(package.name)
            basename[Path(item).name].add(package.name)

    records: list[dict[str, Any]] = []
    counts = {"mapped": 0, "ambiguous": 0, "unmapped": 0, "missing_license": 0}
    packages_used: set[str] = set()
    license_expressions: set[str] = set()

    for resource in resources:
        name = resource["name"]
        origin = resource["origin"]
        override = matching_override(name, origin, overrides)
        candidates: set[str]
        method: str
        if override is not None:
            candidates = {override["package"]}
            method = "reviewed_override"
        elif name in exact:
            candidates = set(exact[name])
            method = "exact_path"
        else:
            candidates = set(basename.get(Path(name).name, set()))
            method = "unique_basename"

        original_candidates = set(candidates)
        selection_reason: str | None = None
        if override is None:
            candidates, selection_reason = prefer_stable_candidate(candidates)

        record: dict[str, Any] = {
            "resource": name,
            "origin": origin,
            "method": method,
            "candidate_packages": sorted(original_candidates),
        }
        if selection_reason is not None:
            record["selection_reason"] = selection_reason
            record["selected_candidates"] = sorted(candidates)
        if override is not None:
            record.update(
                {
                    "status": "mapped",
                    "package": override["package"],
                    "license": override["license"],
                    "override_reason": override["reason"],
                }
            )
        elif len(candidates) == 1:
            package_name = next(iter(candidates))
            package = packages[package_name]
            record.update(
                {
                    "status": "mapped" if package.license else "missing_license",
                    "package": package_name,
                    "license": package.license,
                    "shortdesc": package.shortdesc,
                }
            )
        elif len(candidates) > 1:
            record["status"] = "ambiguous"
        else:
            record["status"] = "unmapped"

        status = record["status"]
        counts[status] += 1
        if status in {"mapped", "missing_license"}:
            packages_used.add(record["package"])
            if record.get("license"):
                license_expressions.add(record["license"])
        records.append(record)

    return {
        "schema_version": 2,
        "summary": {
            "resource_count": len(resources),
            **counts,
            "package_count": len(packages_used),
            "license_expression_count": len(license_expressions),
        },
        "packages_used": sorted(packages_used),
        "license_expressions": sorted(license_expressions),
        "resources": records,
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    lines = [
        "# Embedded TeX resource license inventory",
        "",
        "This inventory is generated from the exact curated resource manifest and",
        "a pinned TeX Live package database. Ambiguous and unmapped resources are",
        "release blockers until reviewed.",
        "",
        "## Summary",
        "",
        f"- Resources: {summary['resource_count']}",
        f"- Mapped: {summary['mapped']}",
        f"- Ambiguous: {summary['ambiguous']}",
        f"- Unmapped: {summary['unmapped']}",
        f"- Mapped without license metadata: {summary['missing_license']}",
        f"- Packages represented: {summary['package_count']}",
        "",
        "## Review failures",
        "",
        "| Resource | Status | Candidates |",
        "|---|---|---|",
    ]
    failures = [
        item for item in inventory["resources"] if item["status"] != "mapped"
    ]
    if failures:
        for item in failures:
            candidates = ", ".join(item.get("candidate_packages", [])) or "—"
            lines.append(
                f"| `{item['resource']}` | `{item['status']}` | {candidates} |"
            )
    else:
        lines.append("| — | All resources mapped | — |")
    lines.extend(["", "## License expressions", ""])
    lines.extend(f"- `{value}`" for value in inventory["license_expressions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tlpdb", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("licenses/generated/tex-resources.json")
    )
    parser.add_argument(
        "--markdown", type=Path, default=Path("licenses/generated/tex-resources.md")
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        inventory = build_inventory(
            load_resources(manifest),
            parse_tlpdb(args.tlpdb),
            load_overrides(args.overrides),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, InventoryError) as error:
        print(f"TEXPDF_LICENSE_INVENTORY_ERROR {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(render_markdown(inventory), encoding="utf-8")
    summary = inventory["summary"]
    print(
        "TEXPDF_LICENSE_INVENTORY "
        f"resources={summary['resource_count']} mapped={summary['mapped']} "
        f"ambiguous={summary['ambiguous']} unmapped={summary['unmapped']} "
        f"missing_license={summary['missing_license']}"
    )
    failures = (
        summary["ambiguous"] + summary["unmapped"] + summary["missing_license"]
    )
    if args.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
