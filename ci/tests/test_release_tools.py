#!/usr/bin/env python3
"""Unit tests for release and license tooling that do not require Stata."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    path = REPOSITORY_ROOT / relative_path
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


tex_inventory = load_module(
    "texpdf_generate_tex_resource_inventory",
    "tools/generate_tex_resource_inventory.py",
)


class TexResourceInventoryTests(unittest.TestCase):
    def test_parse_tlpdb_indexes_runtime_and_reloc_paths(self) -> None:
        content = """\
name package-one
catalogue-license lppl1.3c
catalogue-version 1.2
runfiles size=2
 texmf-dist/tex/latex/package-one/one.sty
 RELOC/fonts/tfm/public/package-one/one.tfm

name package-two
catalogue-license ofl
runfiles size=1
 texmf-dist/fonts/opentype/public/package-two/two.otf
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "texlive.tlpdb"
            path.write_text(content, encoding="utf-8")
            packages, index = tex_inventory.parse_tlpdb(path)

        self.assertEqual(packages["package-one"]["license"], "lppl1.3c")
        self.assertEqual(packages["package-one"]["catalogue_version"], "1.2")
        self.assertEqual(
            index["texmf-dist/tex/latex/package-one/one.sty"],
            {"package-one"},
        )
        self.assertEqual(
            index["texmf-dist/fonts/tfm/public/package-one/one.tfm"],
            {"package-one"},
        )

    def test_exact_path_wins_before_basename_fallback(self) -> None:
        exact = {
            "texmf-dist/tex/latex/alpha/shared.sty": {"alpha"},
            "texmf-dist/tex/latex/beta/shared.sty": {"beta"},
        }
        basename = tex_inventory.build_basename_index(exact)
        candidates = tex_inventory.package_candidates(
            "texmf-dist/tex/latex/alpha/shared.sty",
            exact,
            basename,
        )
        self.assertEqual(candidates, {"alpha"})
        self.assertEqual(
            tex_inventory.package_candidates("shared.sty", exact, basename),
            {"alpha", "beta"},
        )

    def test_manifest_name_extraction_is_bounded_to_path_fields(self) -> None:
        payload = {
            "resources": [
                {"logical_name": "article.cls", "reason": "observed"},
                {"path": "fonts/cmr10.tfm", "license": "not-a-resource"},
            ],
            "metadata": {"description": "should not be interpreted as a path"},
        }
        self.assertEqual(
            tex_inventory.extract_manifest_names(payload),
            {"article.cls", "fonts/cmr10.tfm"},
        )

    def test_zip_resource_fallback_excludes_digest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "bundle.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("SHA256SUM", "0" * 64)
                archive.writestr("article.cls", "content")
                archive.writestr("fonts/cmr10.tfm", b"metrics")
            names, source = tex_inventory.embedded_resources(None, archive_path)
        self.assertEqual(names, {"article.cls", "fonts/cmr10.tfm"})
        self.assertTrue(source.startswith("zip:"))


class GeneratedJsonTests(unittest.TestCase):
    def test_inventory_json_is_stably_sorted(self) -> None:
        payload = {
            "schema_version": 1,
            "unresolved_resources": ["b", "a"],
            "license_complete": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "inventory.json"
            tex_inventory.write_json(path, payload)
            parsed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(parsed, payload)


class WorkflowCompatibilityTests(unittest.TestCase):
    def test_artifact_manifest_avoids_python_310_union_annotations(self) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/publish-artifact-manifest.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Path | None", workflow)

    def test_memory_publisher_preserves_frozen_candidate_evidence(self) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/stress-memory-macos.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("latest-memory-stress-macos-arm64.json", workflow)
        self.assertIn('scope["candidate_source_sha"]', workflow)
        self.assertIn("if is_candidate and record[\"qualified\"]", workflow)


if __name__ == "__main__":
    unittest.main()
