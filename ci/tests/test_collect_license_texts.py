#!/usr/bin/env python3
"""Regression tests for release notice collection boundaries."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/collect_dependency_license_texts.py"


def load_module():
    tools = str(SCRIPT.parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    specification = importlib.util.spec_from_file_location(
        "texpdf_collect_dependency_license_texts", SCRIPT
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load dependency license collector")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class NoticeBoundaryTests(unittest.TestCase):
    def test_workspace_fallback_does_not_recurse_into_audit_outputs(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "LICENSE").write_text("project license\n", encoding="utf-8")
            generated = root / "licenses/generated/texts/rust/self"
            generated.mkdir(parents=True)
            (generated / "LICENSE").write_text("recursive output\n", encoding="utf-8")
            destination = root / "collected"
            records = module.copy_notices(
                root,
                destination,
                source_label="repository:workspace",
                include_notice_directories=False,
            )
            self.assertEqual([Path(record["file"]).name for record in records], ["LICENSE"])
            self.assertEqual((destination / "LICENSE").read_text(), "project license\n")
            self.assertFalse((destination / "licenses").exists())
            self.assertEqual(records[0]["source"], "repository:workspace/LICENSE")


if __name__ == "__main__":
    unittest.main()
