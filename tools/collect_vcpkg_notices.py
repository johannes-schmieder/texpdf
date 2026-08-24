#!/usr/bin/env python3
"""Collect canonical vcpkg copyright notices for installed static ports."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


class NoticeError(RuntimeError):
    """A vcpkg inventory or notice collection failure."""


def run_list(vcpkg: Path, triplet: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [str(vcpkg), "list", "--x-json"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise NoticeError(
            f"vcpkg list failed with {result.returncode}: {result.stderr.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise NoticeError(f"vcpkg list returned invalid JSON: {error}") from error

    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = payload.get("results") or payload.get("packages") or []
        if not isinstance(values, list):
            # Some vcpkg versions return a mapping from package spec to metadata.
            values = [
                {"package_name": key, **(value if isinstance(value, dict) else {})}
                for key, value in payload.items()
                if key not in {"results", "packages"}
            ]
    else:
        values = []

    for item in values:
        if not isinstance(item, dict):
            continue
        name = item.get("package_name") or item.get("name") or item.get("port_name")
        item_triplet = item.get("triplet") or item.get("architecture")
        if not isinstance(name, str) or not name:
            continue
        if item_triplet and str(item_triplet) != triplet:
            continue
        rows.append(
            {
                "name": name.split(":", 1)[0],
                "version": item.get("version") or item.get("version_string") or "",
                "triplet": triplet,
                "raw": item,
            }
        )
    deduplicated = {row["name"]: row for row in rows}
    if not deduplicated:
        raise NoticeError(f"no installed packages found for triplet {triplet}")
    return [deduplicated[name] for name in sorted(deduplicated)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vcpkg-root", type=Path, required=True)
    parser.add_argument("--triplet", required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("licenses/native/vcpkg")
    )
    parser.add_argument(
        "--inventory", type=Path, default=Path("licenses/NATIVE_LICENSE_INVENTORY.json")
    )
    parser.add_argument("--revision", default="")
    args = parser.parse_args()

    vcpkg = args.vcpkg_root / ("vcpkg.exe" if sys.platform == "win32" else "vcpkg")
    if not vcpkg.is_file():
        print(f"TEXPDF_NATIVE_NOTICE_ERROR missing vcpkg executable: {vcpkg}", file=sys.stderr)
        return 2

    try:
        packages = run_list(vcpkg, args.triplet)
        if args.output_dir.exists():
            shutil.rmtree(args.output_dir)
        args.output_dir.mkdir(parents=True)
        missing = []
        records = []
        for package in packages:
            source = (
                args.vcpkg_root
                / "installed"
                / args.triplet
                / "share"
                / package["name"]
                / "copyright"
            )
            if not source.is_file():
                missing.append(package["name"])
                continue
            destination = args.output_dir / f"{package['name']}.txt"
            shutil.copyfile(source, destination)
            records.append(
                {
                    "name": package["name"],
                    "version": package["version"],
                    "triplet": args.triplet,
                    "notice_file": destination.as_posix(),
                    "notice_sha256": sha256(destination),
                }
            )
        payload = {
            "schema_version": 1,
            "vcpkg_revision": args.revision,
            "triplet": args.triplet,
            "installed_package_count": len(packages),
            "notice_count": len(records),
            "missing_notice_count": len(missing),
            "missing_notice_packages": missing,
            "packages": records,
        }
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "TEXPDF_NATIVE_NOTICES "
            f"packages={len(packages)} notices={len(records)} missing={len(missing)}"
        )
        if missing:
            return 2
        return 0
    except (OSError, NoticeError) as error:
        print(f"TEXPDF_NATIVE_NOTICE_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
