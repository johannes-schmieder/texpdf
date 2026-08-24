#!/usr/bin/env python3
"""Unit tests for conservative TeX resource ownership resolution."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
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

    def test_override_requires_reason_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overrides.toml"
            path.write_text(
                """[[override]]
pattern = "generated.dat"
package = "project"
license = "mit"
reason = "Project-generated input."
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(module.InventoryError, "requires pattern"):
                module.load_overrides(path)

    def test_override_evidence_is_source_bound(self) -> None:
        overrides = [
            {
                "pattern": "generated.dat",
                "origin": "project-generated",
                "package": "project",
                "license": "mit",
                "reason": "Project-generated input.",
                "evidence": "generated-input",
            }
        ]
        evidence = {
            "generated-input": {
                "license": "mit",
                "source_url": "https://example.test/project/LICENSE",
                "rationale": "The project creates this exact file.",
                "resource_patterns": ["generated.dat"],
                "origins": ["project-generated"],
                "pinned_version": "schema 1",
            }
        }
        module.validate_overrides(overrides, evidence)
        inventory = module.build_inventory(
            [{"name": "generated.dat", "origin": "project-generated"}],
            {},
            overrides,
            evidence,
        )
        record = inventory["resources"][0]
        self.assertEqual(record["status"], "mapped")
        self.assertEqual(record["evidence_id"], "generated-input")
        self.assertEqual(record["evidence"]["license"], "mit")

    def test_override_rejects_unapproved_pattern(self) -> None:
        overrides = [
            {
                "pattern": "different.dat",
                "origin": "",
                "package": "project",
                "license": "mit",
                "reason": "Reviewed.",
                "evidence": "generated-input",
            }
        ]
        evidence = {
            "generated-input": {
                "license": "mit",
                "source_url": "https://example.test/project/LICENSE",
                "rationale": "The project creates one exact file.",
                "resource_patterns": ["generated.dat"],
                "pinned_version": "schema 1",
            }
        }
        with self.assertRaisesRegex(module.InventoryError, "not authorized"):
            module.validate_overrides(overrides, evidence)


if __name__ == "__main__":
    unittest.main()
