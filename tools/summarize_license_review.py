#!/usr/bin/env python3
"""Extract compact human-review queues from generated license inventories."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} is not a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tex_review(inventory: dict[str, Any]) -> dict[str, Any]:
    failures = [
        item
        for item in inventory.get("resources", [])
        if isinstance(item, dict) and item.get("status") != "mapped"
    ]
    by_status = Counter(str(item.get("status", "unknown")) for item in failures)
    candidate_pairs: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for item in failures:
        candidates = tuple(str(value) for value in item.get("candidate_packages", []))
        candidate_pairs[candidates].append(str(item.get("resource", "")))
    groups = [
        {
            "candidate_packages": list(candidates),
            "resource_count": len(resources),
            "resources": sorted(resources),
        }
        for candidates, resources in sorted(
            candidate_pairs.items(),
            key=lambda value: (-len(value[1]), value[0]),
        )
    ]
    return {
        "schema_version": 1,
        "summary": {
            "review_resource_count": len(failures),
            "by_status": dict(sorted(by_status.items())),
            "candidate_group_count": len(groups),
        },
        "candidate_groups": groups,
        "resources": sorted(
            failures,
            key=lambda item: (str(item.get("status")), str(item.get("resource"))),
        ),
    }


def rust_review(inventory: dict[str, Any]) -> dict[str, Any]:
    records = inventory.get("missing_rust_notice_records", [])
    if not isinstance(records, list):
        records = []
    license_counts = Counter(str(item.get("license") or "UNKNOWN") for item in records if isinstance(item, dict))
    repository_counts = Counter(str(item.get("repository") or "UNKNOWN") for item in records if isinstance(item, dict))
    return {
        "schema_version": 1,
        "summary": {
            "missing_package_count": len(records),
            "by_license_expression": dict(sorted(license_counts.items())),
            "by_repository": dict(sorted(repository_counts.items())),
        },
        "packages": sorted(
            (item for item in records if isinstance(item, dict)),
            key=lambda item: (str(item.get("name")), str(item.get("version"))),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tex-inventory",
        type=Path,
        default=Path("licenses/generated/tex-resources.json"),
    )
    parser.add_argument(
        "--rust-text-inventory",
        type=Path,
        default=Path("licenses/generated/license-texts.json"),
    )
    parser.add_argument(
        "--tex-output",
        type=Path,
        default=Path("licenses/generated/tex-review.json"),
    )
    parser.add_argument(
        "--rust-output",
        type=Path,
        default=Path("licenses/generated/rust-notice-review.json"),
    )
    args = parser.parse_args()

    try:
        tex = tex_review(load(args.tex_inventory))
        rust = rust_review(load(args.rust_text_inventory))
    except RuntimeError as error:
        print(f"TEXPDF_LICENSE_REVIEW_ERROR {error}", file=sys.stderr)
        return 2
    write_json(args.tex_output, tex)
    write_json(args.rust_output, rust)
    print(
        "TEXPDF_LICENSE_REVIEW_READY "
        f"tex={tex['summary']['review_resource_count']} "
        f"rust={rust['summary']['missing_package_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
