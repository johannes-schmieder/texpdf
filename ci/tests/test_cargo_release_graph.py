#!/usr/bin/env python3
"""Unit tests for release-only Cargo dependency graph selection."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPOSITORY_ROOT / "tools/cargo_release_graph.py"
SPEC = importlib.util.spec_from_file_location("cargo_release_graph", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
graph = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(graph)


class CargoReleaseGraphTests(unittest.TestCase):
    def metadata(self) -> dict:
        return {
            "workspace_members": ["root"],
            "packages": [
                {"id": "root", "name": "texpdf-stata", "version": "0.1.0"},
                {"id": "normal", "name": "normal", "version": "1.0.0"},
                {"id": "build", "name": "build", "version": "1.0.0"},
                {"id": "dev", "name": "dev", "version": "1.0.0"},
                {"id": "nested", "name": "nested", "version": "1.0.0"},
            ],
            "resolve": {
                "nodes": [
                    {
                        "id": "root",
                        "deps": [
                            {
                                "pkg": "normal",
                                "dep_kinds": [{"kind": None, "target": None}],
                            },
                            {
                                "pkg": "build",
                                "dep_kinds": [{"kind": "build", "target": None}],
                            },
                            {
                                "pkg": "dev",
                                "dep_kinds": [{"kind": "dev", "target": None}],
                            },
                        ],
                    },
                    {
                        "id": "normal",
                        "deps": [{"pkg": "nested", "dep_kinds": []}],
                    },
                    {"id": "build", "deps": []},
                    {"id": "dev", "deps": []},
                    {"id": "nested", "deps": []},
                ]
            },
        }

    def test_normal_and_build_closure_excludes_dev_dependencies(self) -> None:
        selected = graph.release_package_ids(self.metadata(), "texpdf-stata")
        self.assertEqual(selected, {"root", "normal", "build", "nested"})

    def test_release_packages_are_sorted_and_complete(self) -> None:
        selected = graph.release_packages(self.metadata(), "texpdf-stata")
        self.assertEqual(
            [item["name"] for item in selected],
            ["build", "nested", "normal", "texpdf-stata"],
        )

    def test_release_root_must_be_unique_workspace_member(self) -> None:
        metadata = self.metadata()
        metadata["workspace_members"] = []
        with self.assertRaises(graph.CargoGraphError):
            graph.release_package_ids(metadata, "texpdf-stata")


if __name__ == "__main__":
    unittest.main()
