#!/usr/bin/env python3
"""Tests for synchronized Stata and release metadata."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "texpdf_check_release_metadata", ROOT / "ci/check_release_metadata.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load check_release_metadata.py")
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


class ReleaseMetadataTests(unittest.TestCase):
    def make_tree(self, root: Path, changelog: str | None = None) -> None:
        (root / "stata").mkdir()
        (root / "stata/texpdf.ado").write_text(
            "*! version 0.2.0 14oct2026\n"
            "program define texpdf\n"
            'display as text "texpdf 0.2.0; engine Tectonic"\n',
            encoding="utf-8",
        )
        (root / "stata/texpdf.sthlp").write_text(
            "{smcl}\n{* *! version 0.2.0 14oct2026}{...}\n",
            encoding="utf-8",
        )
        (root / "stata/texpdf.pkg").write_text(
            "v 3\nd texpdf\nd Distribution-Date: 20261014\n",
            encoding="utf-8",
        )
        (root / "CHANGELOG.md").write_text(
            changelog or "# Changelog\n\n## Unreleased\n",
            encoding="utf-8",
        )
        (root / "Cargo.toml").write_text(
            '[workspace]\n\n[workspace.package]\nversion = "0.2.0"\n',
            encoding="utf-8",
        )

    def test_development_metadata_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            self.assertEqual(metadata.check(root), [])

    def test_help_and_package_mismatches_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            (root / "stata/texpdf.sthlp").write_text(
                "{* *! version 0.2.1 14oct2026}{...}\n", encoding="utf-8"
            )
            errors = metadata.check(root)
            self.assertTrue(any("ado/help metadata mismatch" in item for item in errors))

    def test_final_tag_requires_matching_dated_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(
                root,
                "# Changelog\n\n## Unreleased\n\n## 0.2.0 - 2026-10-14\n",
            )
            self.assertEqual(metadata.check(root, "v0.2.0"), [])

    def test_rc_tag_uses_undotted_rc_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            self.assertEqual(metadata.check(root, "v0.2.0-rc2"), [])
            self.assertTrue(metadata.check(root, "v0.2.0-rc.2"))


if __name__ == "__main__":
    unittest.main()
