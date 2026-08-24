#!/usr/bin/env python3
"""Unit tests for deterministic development and public release packaging."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "tools/package_release.py"
GENERATED_LICENSE_FILES = (
    "STATUS.json",
    "STATUS.md",
    "tex-resources.json",
    "tex-resources.md",
    "cargo.json",
    "cargo.md",
    "dependencies.json",
    "dependencies.md",
    "license-texts.json",
    "license-sources.lock.json",
)


def write(path: Path, content: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object]) -> None:
    write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


class PackageReleaseTests(unittest.TestCase):
    def prepare_project(self, root: Path) -> tuple[Path, Path]:
        write(root / "stata/texpdf.ado")
        write(root / "stata/texpdf.sthlp")
        write(
            root / "stata/texpdf.pkg",
            "v 3\nf texpdf.ado\nf texpdf.sthlp\nf _texpdf_plugin.plugin\n"
            "f LICENSE\nf THIRD_PARTY_NOTICES.md\nf BUILD_INFO.json\n"
            "f CHECKSUMS.sha256\n",
        )
        write(root / "stata/stata.toc")
        write(root / "LICENSE", "MIT fixture\n")
        write(root / "licenses/THIRD_PARTY_NOTICES.md", "Notice index\n")
        plugin = root / "plugin.bin"
        plugin.write_bytes(b"plugin fixture")
        bundle_info = root / "bundle-info.json"
        write_json(
            bundle_info,
            {
                "schema_version": 1,
                "bundle_name": "test-bundle",
                "bundle_version": "1",
                "tectonic_bundle_digest": "1" * 64,
                "zip_sha256": "2" * 64,
                "zip_size_bytes": 100,
                "file_count": 10,
            },
        )
        return plugin, bundle_info

    def command(
        self,
        root: Path,
        plugin: Path,
        bundle_info: Path,
        public: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            "--plugin",
            str(plugin),
            "--bundle-info",
            str(bundle_info),
            "--output-dir",
            "dist/package",
            "--zip",
            "dist/package.zip",
            "--manifest",
            "dist/manifest.json",
            "--target",
            "test-target",
        ]
        if public:
            command.append("--public-release")
        return subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_development_package_includes_notice_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin, bundle_info = self.prepare_project(root)
            result = self.command(root, plugin, bundle_info)
            self.assertEqual(result.returncode, 0, result.stderr)
            build = json.loads(
                (root / "dist/package/BUILD_INFO.json").read_text(encoding="utf-8")
            )
            self.assertFalse(build["public_release_mode"])
            self.assertFalse(build["release_license_complete"])
            self.assertTrue((root / "dist/package/THIRD_PARTY_NOTICES.md").is_file())
            with zipfile.ZipFile(root / "dist/package.zip") as archive:
                self.assertIn("THIRD_PARTY_NOTICES.md", archive.namelist())
                self.assertNotIn("LICENSES/STATUS.json", archive.namelist())

    def test_public_release_fails_without_complete_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin, bundle_info = self.prepare_project(root)
            result = self.command(root, plugin, bundle_info, public=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("public-release mode requires", result.stderr)

    def test_public_release_packages_inventory_and_texts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin, bundle_info = self.prepare_project(root)
            generated = root / "licenses/generated"
            status = {
                "source_sha": "3" * 40,
                "release_license_complete": True,
                "return_codes": {
                    "tex_inventory": 0,
                    "cargo_inventory": 0,
                    "dependency_inventory": 0,
                    "notice_collection": 0,
                },
                "tex_resources": {
                    "resource_count": 10,
                    "mapped": 10,
                    "ambiguous": 0,
                    "unmapped": 0,
                    "missing_license": 0,
                },
                "dependency_undeclared_count": 0,
                "missing_rust_notice_files": 0,
                "missing_native_notice_files": 0,
            }
            for name in GENERATED_LICENSE_FILES:
                if name == "STATUS.json":
                    write_json(generated / name, status)
                else:
                    write(generated / name)
            write(generated / "texts/rust/example/LICENSE", "Example license\n")

            result = self.command(root, plugin, bundle_info, public=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            build = json.loads(
                (root / "dist/package/BUILD_INFO.json").read_text(encoding="utf-8")
            )
            self.assertTrue(build["public_release_mode"])
            self.assertTrue(build["release_license_complete"])
            self.assertGreater(build["packaged_license_file_count"], 10)
            package_text = (root / "dist/package/texpdf.pkg").read_text(
                encoding="utf-8"
            )
            self.assertIn("f LICENSES/STATUS.json", package_text)
            self.assertIn("f LICENSES/texts/rust/example/LICENSE", package_text)
            with zipfile.ZipFile(root / "dist/package.zip") as archive:
                names = set(archive.namelist())
            self.assertIn("LICENSES/STATUS.json", names)
            self.assertIn("LICENSES/texts/rust/example/LICENSE", names)


if __name__ == "__main__":
    unittest.main()
