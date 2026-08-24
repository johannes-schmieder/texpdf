#!/usr/bin/env python3
"""Select the Cargo packages that participate in one release plugin build."""

from __future__ import annotations

import json
import subprocess
from typing import Any


class CargoGraphError(RuntimeError):
    """Cargo metadata could not describe the requested release graph."""


def cargo_metadata(cargo: str, target: str) -> dict[str, Any]:
    command = [
        cargo,
        "metadata",
        "--format-version",
        "1",
        "--locked",
        "--filter-platform",
        target,
    ]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise CargoGraphError(
            f"cargo metadata failed with {result.returncode}: {result.stderr.strip()}"
        )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CargoGraphError(f"cargo metadata returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise CargoGraphError("cargo metadata did not return an object")
    return value


def root_package_id(metadata: dict[str, Any], package_name: str) -> str:
    workspace_members = set(metadata.get("workspace_members", []))
    candidates = [
        str(package.get("id"))
        for package in metadata.get("packages", [])
        if isinstance(package, dict)
        and package.get("name") == package_name
        and package.get("id") in workspace_members
    ]
    if len(candidates) != 1:
        raise CargoGraphError(
            f"expected one workspace package named {package_name!r}, found {len(candidates)}"
        )
    return candidates[0]


def dependency_is_release_relevant(dependency: dict[str, Any]) -> bool:
    kinds = dependency.get("dep_kinds")
    if not isinstance(kinds, list) or not kinds:
        return True
    return any(
        isinstance(item, dict) and item.get("kind") != "dev" for item in kinds
    )


def release_package_ids(
    metadata: dict[str, Any], package_name: str
) -> set[str]:
    resolve = metadata.get("resolve")
    if not isinstance(resolve, dict):
        raise CargoGraphError("cargo metadata has no resolve graph")
    nodes = {
        str(node.get("id")): node
        for node in resolve.get("nodes", [])
        if isinstance(node, dict) and node.get("id")
    }
    root = root_package_id(metadata, package_name)
    if root not in nodes:
        raise CargoGraphError(f"release root {root!r} is absent from resolve graph")

    selected: set[str] = set()
    stack = [root]
    while stack:
        package_id = stack.pop()
        if package_id in selected:
            continue
        selected.add(package_id)
        node = nodes.get(package_id)
        if node is None:
            raise CargoGraphError(
                f"resolved dependency {package_id!r} has no metadata node"
            )
        dependencies = node.get("deps", [])
        if not isinstance(dependencies, list):
            raise CargoGraphError(f"resolve node {package_id!r} has invalid deps")
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue
            dependency_id = dependency.get("pkg")
            if dependency_id and dependency_is_release_relevant(dependency):
                stack.append(str(dependency_id))
    return selected


def release_packages(
    metadata: dict[str, Any], package_name: str
) -> list[dict[str, Any]]:
    selected = release_package_ids(metadata, package_name)
    packages = [
        package
        for package in metadata.get("packages", [])
        if isinstance(package, dict) and str(package.get("id")) in selected
    ]
    found = {str(package.get("id")) for package in packages}
    missing = selected.difference(found)
    if missing:
        raise CargoGraphError(
            "selected package IDs missing from metadata: " + ", ".join(sorted(missing))
        )
    return sorted(
        packages,
        key=lambda item: (str(item.get("name")), str(item.get("version"))),
    )
