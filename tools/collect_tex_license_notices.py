#!/usr/bin/env python3
"""Build source-bound TeX resource attributions and required notice texts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any
import zipfile


class TexNoticeError(RuntimeError):
    """The embedded-resource notice tree is incomplete or inconsistent."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TexNoticeError(f"JSON document is not an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def collect(
    inventory_path: Path,
    policy_path: Path,
    evidence_path: Path,
    curated_manifest_path: Path,
    bundle_path: Path,
    output_root: Path,
    manifest_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    inventory = load_object(inventory_path)
    policy = load_object(policy_path)
    evidence = load_object(evidence_path)
    curated = load_object(curated_manifest_path)
    if policy.get("schema_version") != 1:
        raise TexNoticeError("TeX notice policy must use schema_version 1")
    expressions = policy.get("expressions")
    if not isinstance(expressions, dict):
        raise TexNoticeError("TeX notice policy has no expressions object")

    inventory_expressions = set(inventory.get("license_expressions", []))
    policy_expressions = set(expressions)
    missing_expressions = sorted(inventory_expressions.difference(policy_expressions))
    if missing_expressions:
        raise TexNoticeError(
            "license expressions without notice policy: " + ", ".join(missing_expressions)
        )

    expected_bundle_sha = str(curated.get("bundle_zip_sha256", ""))
    actual_bundle_sha = sha256_file(bundle_path)
    if not expected_bundle_sha or actual_bundle_sha != expected_bundle_sha:
        raise TexNoticeError(
            f"bundle SHA-256 mismatch: expected {expected_bundle_sha}, "
            f"got {actual_bundle_sha}"
        )

    curated_rows = curated.get("resources")
    inventory_rows = inventory.get("resources")
    if not isinstance(curated_rows, list) or not isinstance(inventory_rows, list):
        raise TexNoticeError("resource inventory or curated manifest has no resources")
    curated_by_name = {str(item["name"]): item for item in curated_rows}
    inventory_by_name = {str(item["resource"]): item for item in inventory_rows}
    if set(curated_by_name) != set(inventory_by_name):
        raise TexNoticeError("curated manifest and license inventory resource sets differ")

    with zipfile.ZipFile(bundle_path) as archive:
        names = {name for name in archive.namelist() if name != "SHA256SUM"}
        if names != set(curated_by_name):
            raise TexNoticeError("bundle and curated manifest resource sets differ")
        attributions = []
        for name in sorted(names):
            data = archive.read(name)
            actual = sha256_bytes(data)
            expected = str(curated_by_name[name].get("sha256", ""))
            if actual != expected:
                raise TexNoticeError(f"embedded resource checksum mismatch for {name}")
            attributions.append(
                {
                    **inventory_by_name[name],
                    "sha256": actual,
                    "size_bytes": len(data),
                }
            )

    shutil.rmtree(output_root, ignore_errors=True)
    output_root.mkdir(parents=True, exist_ok=True)
    copied: dict[str, dict[str, object]] = {}
    for expression in sorted(inventory_expressions):
        sources = expressions.get(expression)
        if not isinstance(sources, list) or not sources or not all(
            isinstance(value, str) and value for value in sources
        ):
            raise TexNoticeError(f"invalid notice policy for {expression}")
        for relative in sources:
            source = (repository_root / relative).resolve()
            try:
                source.relative_to(repository_root.resolve())
            except ValueError as error:
                raise TexNoticeError(f"notice source escapes repository: {source}") from error
            if not source.is_file():
                raise TexNoticeError(f"notice source is missing: {source}")
            destination = output_root / "license-texts" / source.name
            if destination.name in copied:
                if copied[destination.name]["sha256"] != sha256_file(source):
                    raise TexNoticeError(f"colliding notice filenames: {source.name}")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied[destination.name] = {
                "source": relative,
                "file": str(destination),
                "sha256": sha256_file(destination),
                "size_bytes": destination.stat().st_size,
            }

    attribution_path = output_root / "resource-attribution.json"
    write_json(
        attribution_path,
        {
            "schema_version": 1,
            "bundle_zip_sha256": actual_bundle_sha,
            "bundle_content_digest": curated.get("bundle_content_digest"),
            "resource_count": len(attributions),
            "license_expressions": sorted(inventory_expressions),
            "resources": attributions,
            "override_evidence": evidence,
        },
    )
    payload = {
        "schema_version": 1,
        "complete": True,
        "bundle_zip_sha256": actual_bundle_sha,
        "resource_count": len(attributions),
        "license_expression_count": len(inventory_expressions),
        "notice_files": [copied[name] for name in sorted(copied)],
        "resource_attribution": str(attribution_path),
        "policy": str(policy_path),
    }
    write_json(manifest_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inventory", type=Path, default=Path("licenses/generated/tex-resources.json")
    )
    parser.add_argument(
        "--policy", type=Path, default=Path("licenses/texlive/license-text-policy.json")
    )
    parser.add_argument(
        "--evidence", type=Path, default=Path("bundle/license-evidence.json")
    )
    parser.add_argument(
        "--curated-manifest", type=Path, default=Path("bundle/curated-manifest.json")
    )
    parser.add_argument(
        "--bundle", type=Path, default=Path("bundle/generated/texpdf-bundle.zip")
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("licenses/generated/texts/texlive")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("licenses/generated/tex-notices.json")
    )
    args = parser.parse_args()
    try:
        payload = collect(
            args.inventory,
            args.policy,
            args.evidence,
            args.curated_manifest,
            args.bundle,
            args.output_root,
            args.manifest,
            Path.cwd().resolve(),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, TexNoticeError) as error:
        print(f"TEXPDF_TEX_NOTICE_ERROR {error}", file=sys.stderr)
        return 2
    print(
        "TEXPDF_TEX_NOTICES_READY "
        f"resources={payload['resource_count']} "
        f"expressions={payload['license_expression_count']} "
        f"notices={len(payload['notice_files'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
