#!/usr/bin/env python3
"""Unit tests for deterministic development and public release packaging."""

from __future__ import annotations

import hashlib
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
    "tex-notices.json",
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
        helper = root / "helper.bin"
        helper.write_bytes(b"helper fixture")
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
        include_license_evidence: bool = False,
        helper_manifest: Path | None = None,
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
        if helper_manifest is None:
            command.extend(["--embedded-helper", str(root / "helper.bin")])
        else:
            command.extend(["--embedded-helper-manifest", str(helper_manifest)])
        if public:
            command.append("--public-release")
        if include_license_evidence:
            command.append("--include-license-evidence")
        return subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    def prepare_complete_license_audit(self, root: Path) -> None:
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
            "tex_notice_complete": True,
            "tex_notice_file_count": 1,
        }
        for name in GENERATED_LICENSE_FILES:
            if name == "STATUS.json":
                write_json(generated / name, status)
            else:
                write(generated / name)
        write(generated / "texts/rust/example/LICENSE", "Example license\n")
        write(generated / "texts/texlive/NOTICE", "TeX notice\n")

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
            self.assertEqual(build["embedded_helper_size_bytes"], 14)
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
            self.assertIn("license-evidence packaging requires", result.stderr)

    def test_public_release_packages_inventory_and_texts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin, bundle_info = self.prepare_project(root)
            self.prepare_complete_license_audit(root)

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
            self.assertNotIn("f LICENSES/STATUS.json", package_text)
            self.assertEqual(build["net_install_license_file_count"], 0)
            with zipfile.ZipFile(root / "dist/package.zip") as archive:
                names = set(archive.namelist())
            self.assertIn("LICENSES/STATUS.json", names)
            self.assertIn("LICENSES/texts/rust/example/LICENSE", names)
            self.assertIn("LICENSES/texts/texlive/NOTICE", names)

    def test_private_candidate_can_include_complete_license_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin, bundle_info = self.prepare_project(root)
            self.prepare_complete_license_audit(root)
            result = self.command(
                root,
                plugin,
                bundle_info,
                include_license_evidence=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            build = json.loads(
                (root / "dist/package/BUILD_INFO.json").read_text(encoding="utf-8")
            )
            self.assertFalse(build["public_release_mode"])
            self.assertTrue(build["license_evidence_included"])
            self.assertGreater(build["packaged_license_file_count"], 10)
            self.assertEqual(build["net_install_license_file_count"], 0)

    def test_universal_manifest_binds_both_embedded_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin, bundle_info = self.prepare_project(root)
            manifest = root / "universal.json"
            write_json(
                manifest,
                {
                    "schema_version": 1,
                    "universal": {
                        "sha256": hashlib.sha256(plugin.read_bytes()).hexdigest(),
                        "size_bytes": plugin.stat().st_size,
                    },
                    "slices": {
                        "arm64": {
                            "embedded_helper": {
                                "target": "aarch64-apple-darwin",
                                "sha256": "4" * 64,
                                "size_bytes": 101,
                            }
                        },
                        "x86_64": {
                            "embedded_helper": {
                                "target": "x86_64-apple-darwin",
                                "sha256": "5" * 64,
                                "size_bytes": 202,
                            }
                        },
                    },
                },
            )
            result = self.command(
                root,
                plugin,
                bundle_info,
                helper_manifest=manifest,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            build = json.loads(
                (root / "dist/package/BUILD_INFO.json").read_text(encoding="utf-8")
            )
            self.assertEqual(build["embedded_helper_count"], 2)
            self.assertIsNone(build["embedded_helper_sha256"])
            self.assertEqual(
                set(build["embedded_helpers"]),
                {"aarch64-apple-darwin", "x86_64-apple-darwin"},
            )


if __name__ == "__main__":
    unittest.main()
