#!/usr/bin/env python3
"""Verify that the selected Rust graph has no runtime network client stack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

FORBIDDEN_NETWORK_PACKAGES = {
    "attohttpc",
    "curl",
    "curl-sys",
    "hyper",
    "hyper-rustls",
    "hyper-tls",
    "isahc",
    "native-tls",
    "openssl",
    "openssl-sys",
    "reqwest",
    "rustls",
    "rustls-native-certs",
    "surf",
    "ureq",
    "webpki-roots",
}


def metadata() -> dict[str, Any]:
    result = subprocess.run(
        [
            "cargo",
            "metadata",
            "--locked",
            "--format-version",
            "1",
            "--filter-platform",
            subprocess.check_output(["rustc", "-vV"], text=True)
            .split("host: ", 1)[1]
            .splitlines()[0],
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("cargo metadata failed")
    return json.loads(result.stdout)


def selected_package_names(payload: dict[str, Any]) -> set[str]:
    package_by_id = {
        package["id"]: package["name"] for package in payload.get("packages", [])
    }
    resolve = payload.get("resolve") or {}
    selected_ids = {node["id"] for node in resolve.get("nodes", [])}
    return {package_by_id[package_id] for package_id in selected_ids if package_id in package_by_id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path(".ci/stata/run/cargo-runtime-policy.json")
    )
    args = parser.parse_args()

    try:
        payload = metadata()
    except (OSError, RuntimeError, json.JSONDecodeError, IndexError) as error:
        print(f"TEXPDF_CARGO_POLICY_ERROR {error}", file=sys.stderr)
        return 2
    selected = selected_package_names(payload)
    violations = sorted(selected & FORBIDDEN_NETWORK_PACKAGES)
    record = {
        "schema_version": 1,
        "selected_package_count": len(selected),
        "forbidden_network_packages": sorted(FORBIDDEN_NETWORK_PACKAGES),
        "violations": violations,
        "policy": (
            "The compiled texpdf graph may not contain a general-purpose HTTP/TLS "
            "client stack. Runtime resources are supplied only by the embedded bundle."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "TEXPDF_CARGO_RUNTIME_POLICY "
        f"selected={len(selected)} violations={len(violations)}"
    )
    if violations:
        print(
            "selected Rust graph contains forbidden network packages: "
            + ", ".join(violations),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
