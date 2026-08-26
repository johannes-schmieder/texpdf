#!/usr/bin/env python3
"""Write the source-bound Windows build receipt used by release readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--binary-policy", type=Path, required=True)
    parser.add_argument("--hosted-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    package = load(args.package_manifest)
    policy = load(args.binary_policy)
    hosted = load(args.hosted_manifest)
    identities = {
        "plugin_sha256": sha256(args.plugin),
        "helper_sha256": sha256(args.helper),
        "package_sha256": sha256(args.package),
    }
    expected = {
        "plugin_sha256": package.get("plugin_sha256"),
        "helper_sha256": package.get("embedded_helper_sha256"),
        "package_sha256": package.get("package_zip_sha256"),
    }
    if identities != expected:
        raise ValueError(f"Windows artifact mismatch: actual={identities} expected={expected}")
    if hosted.get("source_sha") != args.source_sha:
        raise ValueError("hosted Windows manifest belongs to another source")
    if hosted.get("plugin_sha256") != identities["plugin_sha256"]:
        raise ValueError("hosted Windows manifest does not match the packaged plugin")
    if hosted.get("helper_sha256") != identities["helper_sha256"]:
        raise ValueError("hosted Windows manifest does not match the packaged helper")
    if policy.get("static_msvc_crt") is not True or policy.get("violations") != []:
        raise ValueError("Windows binary policy did not prove static CRT linkage")
    payload = {
        "schema_version": 1,
        "status": "success",
        "source_sha": args.source_sha,
        "target": "x86_64-pc-windows-msvc",
        "rust_tests": hosted.get("rust_tests"),
        "plugin_sha256": identities["plugin_sha256"],
        "plugin_size_bytes": args.plugin.stat().st_size,
        "helper_sha256": identities["helper_sha256"],
        "helper_size_bytes": args.helper.stat().st_size,
        "package_sha256": identities["package_sha256"],
        "package_size_bytes": args.package.stat().st_size,
        "binary_policy": policy,
        "hosted_manifest": hosted,
        "package_manifest": package,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEXPDF_WINDOWS_BUILD_RECEIPT_PASS source={args.source_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
