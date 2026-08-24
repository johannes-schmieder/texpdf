#!/usr/bin/env python3
"""Resolve a pinned TeX Live package closure to Tectonic bundle resources."""

from __future__ import annotations

import argparse
from collections import deque
import gzip
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ARCH_SUFFIX_RE = re.compile(r"\.([A-Za-z0-9_]+-[A-Za-z0-9_.-]+)$")


def read_top_level(path: Path) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = raw.split("#", 1)[0].strip()
        if not value:
            continue
        if any(character.isspace() for character in value):
            raise ValueError(f"{path}:{line_number}: package names may not contain whitespace")
        if value not in seen:
            seen.add(value)
            packages.append(value)
    if not packages:
        raise ValueError(f"{path}: no top-level packages")
    return packages


def parse_tlpdb(path: Path) -> dict[str, dict[str, Any]]:
    packages: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    in_runfiles = False

    def finish() -> None:
        nonlocal current
        if current is not None and current.get("name"):
            packages[str(current["name"])] = current
        current = None

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("name "):
            finish()
            current = {
                "name": raw[5:].strip(),
                "depends": [],
                "runfiles": [],
                "license": None,
                "catalogue_version": None,
            }
            in_runfiles = False
            continue
        if current is None:
            continue
        if not raw:
            in_runfiles = False
            continue
        if raw.startswith("runfiles "):
            in_runfiles = True
            continue
        if raw.startswith("docfiles ") or raw.startswith("srcfiles "):
            in_runfiles = False
            continue
        if raw[0].isspace() and in_runfiles:
            value = raw.strip().split(" ", 1)[0]
            if value.startswith("RELOC/"):
                value = "texmf-dist/" + value[6:]
            current["runfiles"].append(value)
            continue
        in_runfiles = False
        if raw.startswith("depend "):
            dependency = raw[7:].strip()
            if dependency and not dependency.startswith("setting_"):
                current["depends"].append(dependency)
        elif raw.startswith("catalogue-license "):
            current["license"] = raw[len("catalogue-license ") :].strip()
        elif raw.startswith("catalogue-version "):
            current["catalogue_version"] = raw[len("catalogue-version ") :].strip()
        elif raw.startswith("license ") and not current.get("license"):
            current["license"] = raw[len("license ") :].strip()
    finish()
    return packages


def normalize_dependency(value: str, packages: dict[str, dict[str, Any]]) -> str | None:
    if value in packages:
        return value
    # Architecture-specific package dependencies are stored as package.ARCH.
    match = ARCH_SUFFIX_RE.search(value)
    if match:
        candidate = value[: match.start()]
        if candidate in packages:
            return candidate
    return None


def dependency_closure(
    top_level: list[str],
    packages: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, str]]]:
    missing = [name for name in top_level if name not in packages]
    if missing:
        raise ValueError("top-level TeX Live packages are missing: " + ", ".join(missing))

    queue = deque(top_level)
    selected: set[str] = set()
    unresolved_dependencies: list[dict[str, str]] = []
    while queue:
        name = queue.popleft()
        if name in selected:
            continue
        selected.add(name)
        for raw_dependency in packages[name].get("depends", []):
            dependency = normalize_dependency(raw_dependency, packages)
            if dependency is None:
                unresolved_dependencies.append(
                    {"package": name, "dependency": raw_dependency}
                )
                continue
            if dependency not in selected:
                queue.append(dependency)
    return sorted(selected), unresolved_dependencies


def read_bundle_names(index_path: Path) -> list[str]:
    names: set[str] = set()
    with gzip.open(index_path, "rt", encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, 1):
            parts = raw.split()
            if len(parts) != 3:
                raise ValueError(f"malformed Tectonic index line {line_number}")
            names.add(parts[0])
    return sorted(names)


def build_name_indexes(names: list[str]) -> tuple[set[str], dict[str, list[str]]]:
    exact = set(names)
    by_basename: dict[str, list[str]] = {}
    for name in names:
        basename = PurePosixPath(name).name
        by_basename.setdefault(basename, []).append(name)
    return exact, {key: sorted(values) for key, values in by_basename.items()}


def match_runfile(
    runfile: str,
    exact: set[str],
    by_basename: dict[str, list[str]],
) -> tuple[str | None, str, list[str]]:
    normalized = str(PurePosixPath(runfile))
    alternatives = [normalized]
    if normalized.startswith("texmf-dist/"):
        alternatives.append(normalized[len("texmf-dist/") :])
    else:
        alternatives.append("texmf-dist/" + normalized)
    for candidate in alternatives:
        if candidate in exact:
            return candidate, "exact", [candidate]

    basename = PurePosixPath(normalized).name
    candidates = by_basename.get(basename, [])
    if len(candidates) == 1:
        return candidates[0], "unique_basename", candidates
    if len(candidates) > 1:
        suffix_matches = [
            candidate
            for candidate in candidates
            if normalized.endswith(candidate) or candidate.endswith(normalized)
        ]
        if len(suffix_matches) == 1:
            return suffix_matches[0], "unique_suffix", candidates
        return None, "ambiguous_basename", candidates
    return None, "unmatched", []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tlpdb", type=Path, required=True)
    parser.add_argument("--bundle-index", type=Path, required=True)
    parser.add_argument(
        "--packages", type=Path, default=Path("bundle/texlive-packages.txt")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("bundle/generated/package-resources.txt")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("bundle/generated/package-resolution.json")
    )
    parser.add_argument("--allow-ambiguous", action="store_true")
    args = parser.parse_args()

    try:
        top_level = read_top_level(args.packages)
        packages = parse_tlpdb(args.tlpdb)
        closure, unresolved_dependencies = dependency_closure(top_level, packages)
        bundle_names = read_bundle_names(args.bundle_index)
    except (OSError, ValueError) as error:
        print(f"TEXPDF_PACKAGE_RESOLUTION_ERROR {error}", file=sys.stderr)
        return 2

    exact, by_basename = build_name_indexes(bundle_names)
    selected_resources: set[str] = set()
    matches: list[dict[str, Any]] = []
    unmatched: list[dict[str, str]] = []
    ambiguous: list[dict[str, Any]] = []
    package_counts: dict[str, int] = {}

    for package_name in closure:
        package = packages[package_name]
        matched_for_package = 0
        for runfile in sorted(set(package.get("runfiles", []))):
            resource, method, candidates = match_runfile(runfile, exact, by_basename)
            if resource is not None:
                selected_resources.add(resource)
                matched_for_package += 1
                matches.append(
                    {
                        "package": package_name,
                        "runfile": runfile,
                        "resource": resource,
                        "method": method,
                    }
                )
            elif method == "ambiguous_basename":
                ambiguous.append(
                    {
                        "package": package_name,
                        "runfile": runfile,
                        "candidates": candidates,
                    }
                )
            else:
                unmatched.append({"package": package_name, "runfile": runfile})
        package_counts[package_name] = matched_for_package

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(f"{name}\n" for name in sorted(selected_resources)),
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "top_level_packages": top_level,
        "dependency_closure": closure,
        "unresolved_dependencies": unresolved_dependencies,
        "bundle_index_file_count": len(bundle_names),
        "selected_resource_count": len(selected_resources),
        "package_match_counts": package_counts,
        "matches": matches,
        "unmatched_runfiles": unmatched,
        "ambiguous_runfiles": ambiguous,
        "packages": [
            {
                "name": name,
                "license": packages[name].get("license"),
                "catalogue_version": packages[name].get("catalogue_version"),
                "matched_resource_count": package_counts[name],
            }
            for name in closure
        ],
    }
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "TEXPDF_PACKAGE_RESOLUTION_READY "
        f"top_level={len(top_level)} closure={len(closure)} "
        f"resources={len(selected_resources)} unmatched={len(unmatched)} "
        f"ambiguous={len(ambiguous)} unresolved_dependencies={len(unresolved_dependencies)}"
    )
    if ambiguous and not args.allow_ambiguous:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
