#!/usr/bin/env python3
"""Unit tests for conservative TeX resource ownership resolution."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPOSITORY_ROOT / "tools"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "generate_license_inventory.py"
SPEC = importlib.util.spec_from_file_location("generate_license_inventory", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class TexLicenseInventoryTests(unittest.TestCase):
    def test_unique_stable_candidate_beats_dev_mirror(self) -> None:
        packages = {
            "latex": module.Package(
                name="latex",
                license="lppl1.3c",
                files=["article.cls"],
            ),
            "latex-base-dev": module.Package(
                name="latex-base-dev",
                license="lppl1.3c",
                files=["article.cls"],
            ),
        }
        inventory = module.build_inventory(
            [{"name": "article.cls", "origin": ""}], packages, []
        )
        record = inventory["resources"][0]
        self.assertEqual(record["status"], "mapped")
        self.assertEqual(record["package"], "latex")
        self.assertEqual(
            record["selection_reason"],
            "unique_stable_candidate_over_development_mirrors",
        )
        self.assertEqual(
            record["candidate_packages"], ["latex", "latex-base-dev"]
        )

    def test_two_stable_candidates_remain_ambiguous(self) -> None:
        packages = {
            "stable-a": module.Package(
                name="stable-a", license="mit", files=["shared.sty"]
            ),
            "stable-b": module.Package(
                name="stable-b", license="mit", files=["shared.sty"]
            ),
        }
        inventory = module.build_inventory(
            [{"name": "shared.sty", "origin": ""}], packages, []
        )
        self.assertEqual(inventory["resources"][0]["status"], "ambiguous")

    def test_dev_only_candidates_remain_ambiguous(self) -> None:
        candidates = {"latex-base-dev", "latex-lab-dev"}
        selected, reason = module.prefer_stable_candidate(candidates)
        self.assertEqual(selected, candidates)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
