#!/usr/bin/env python3
"""Inspect a built plugin for standalone-linking and platform-policy violations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

FORBIDDEN_PATH_FRAGMENTS = (
    "/opt/homebrew/",
    "/usr/local/Cellar/",
    "/private/tmp/texpdf-",
    "\\vcpkg\\installed\\",
    "/vcpkg/installed/",
)
FORBIDDEN_DYNAMIC_LIBRARY_NAMES = (
    "fontconfig",
    "freetype",
    "graphite",
    "harfbuzz",
    "icu",
    "libpng",
    "zlib",
)
GLIBC_RE = re.compile(r"GLIBC_([0-9]+)\.([0-9]+)")


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr}"
        )
    return result.stdout


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def inspect_macos(path: Path, minimum_macos: str | None) -> dict[str, Any]:
    file_output = run(["/usr/bin/file", str(path)]).strip()
    dependencies = run(["/usr/bin/otool", "-L", str(path)])
    load_commands = run(["/usr/bin/otool", "-l", str(path)])
    architectures = run(["/usr/bin/lipo", "-archs", str(path)]).split()
    exports = run(["/usr/bin/nm", "-gU", str(path)])

    violations: list[str] = []
    for fragment in FORBIDDEN_PATH_FRAGMENTS:
        if fragment in dependencies or fragment in load_commands:
            violations.append(f"binary contains forbidden build path: {fragment}")
    dependency_lines = [line.strip() for line in dependencies.splitlines()[1:] if line.strip()]
    for line in dependency_lines:
        lowered = line.lower()
        if any(name in lowered for name in FORBIDDEN_DYNAMIC_LIBRARY_NAMES):
            violations.append(f"native engine dependency was not linked standalone: {line}")
    if "pginit" not in exports:
        violations.append("pginit export is missing")
    if "stata_call" not in exports:
        violations.append("stata_call export is missing")

    minimum_versions = re.findall(r"\bminos\s+([0-9]+(?:\.[0-9]+){1,2})", load_commands)
    if not minimum_versions:
        minimum_versions = re.findall(
            r"\bversion\s+([0-9]+(?:\.[0-9]+){1,2})", load_commands
        )
    if minimum_macos:
        intended = version_tuple(minimum_macos)
        for actual in minimum_versions:
            if version_tuple(actual) > intended:
                violations.append(
                    f"Mach-O minimum OS {actual} exceeds intended {minimum_macos}"
                )

    return {
        "platform": "macos",
        "file": file_output,
        "architectures": architectures,
        "dynamic_dependencies": dependency_lines,
        "minimum_os_versions": minimum_versions,
        "intended_minimum_macos": minimum_macos,
        "violations": sorted(set(violations)),
    }


def inspect_linux(path: Path, maximum_glibc: str | None) -> dict[str, Any]:
    file_output = run(["file", str(path)]).strip()
    dynamic = run(["readelf", "-d", str(path)])
    symbols = run(["objdump", "-T", str(path)])
    ldd = run(["ldd", str(path)])
    exports = run(["nm", "-D", "--defined-only", str(path)])

    violations: list[str] = []
    for fragment in FORBIDDEN_PATH_FRAGMENTS:
        if fragment in dynamic or fragment in ldd:
            violations.append(f"binary contains forbidden build path: {fragment}")
    for line in ldd.splitlines():
        lowered = line.lower()
        if any(name in lowered for name in FORBIDDEN_DYNAMIC_LIBRARY_NAMES):
            violations.append(f"native engine dependency was not linked standalone: {line.strip()}")
    if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
        violations.append("ELF contains RPATH or RUNPATH")
    if "pginit" not in exports:
        violations.append("pginit export is missing")
    if "stata_call" not in exports:
        violations.append("stata_call export is missing")

    glibc_versions = sorted(
        {match.group(0).removeprefix("GLIBC_") for match in GLIBC_RE.finditer(symbols)},
        key=version_tuple,
    )
    if maximum_glibc and glibc_versions:
        maximum_seen = max(glibc_versions, key=version_tuple)
        if version_tuple(maximum_seen) > version_tuple(maximum_glibc):
            violations.append(
                f"maximum required GLIBC {maximum_seen} exceeds policy {maximum_glibc}"
            )

    return {
        "platform": "linux",
        "file": file_output,
        "dynamic_section": dynamic.splitlines(),
        "ldd": ldd.splitlines(),
        "required_glibc_versions": glibc_versions,
        "maximum_allowed_glibc": maximum_glibc,
        "violations": sorted(set(violations)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin", type=Path)
    parser.add_argument("--platform", choices=("macos", "linux"), required=True)
    parser.add_argument("--minimum-macos")
    parser.add_argument("--maximum-glibc")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.plugin.is_file():
        print(f"TEXPDF_BINARY_POLICY_ERROR missing plugin: {args.plugin}", file=sys.stderr)
        return 2
    try:
        if args.platform == "macos":
            payload = inspect_macos(args.plugin, args.minimum_macos)
        else:
            payload = inspect_linux(args.plugin, args.maximum_glibc)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"TEXPDF_BINARY_POLICY_ERROR {error}", file=sys.stderr)
        return 2

    payload["schema_version"] = 1
    payload["plugin"] = str(args.plugin)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    violations = payload["violations"]
    print(
        "TEXPDF_BINARY_POLICY "
        f"platform={args.platform} violations={len(violations)}"
    )
    for violation in violations:
        print(f"TEXPDF_BINARY_POLICY_VIOLATION {violation}", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
