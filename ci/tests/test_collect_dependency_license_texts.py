#!/usr/bin/env python3
"""Tests for the fail-closed canonical SPDX notice policy."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPOSITORY_ROOT / "tools"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "collect_dependency_license_texts.py"
SPEC = importlib.util.spec_from_file_location(
    "collect_dependency_license_texts", MODULE_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class CanonicalSpdxPolicyTests(unittest.TestCase):
    def test_supported_or_expression_is_deduplicated(self) -> None:
        self.assertEqual(
            module.canonical_spdx_components("MIT OR Apache-2.0 OR MIT"),
            ["Apache-2.0", "MIT"],
        )

    def test_custom_or_compound_expression_fails_closed(self) -> None:
        self.assertEqual(module.canonical_spdx_components("MPL-2.0"), [])
        self.assertEqual(
            module.canonical_spdx_components("MIT AND Apache-2.0"), []
        )


if __name__ == "__main__":
    unittest.main()
