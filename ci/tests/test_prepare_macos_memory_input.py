#!/usr/bin/env python3
"""Tests for exact universal-package memory qualification input validation."""

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
SCRIPT = REPOSITORY_ROOT / "ci" / "prepare_macos_memory_input.py"
SOURCE_SHA = "1" * 40
HELPER_SHA = "2" * 64
BUNDLE_SHA = "3" * 64


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class MacosMemoryInputTests(unittest.TestCase):
    def prepare_artifact(self, root: Path) -> tuple[Path, Path]:
        universal_dir = root / "dist" / "macos-universal"
        package_dir = universal_dir / "texpdf"
        evidence = root / ".ci" / "stata" / "run"
        package_dir.mkdir(parents=True)
        evidence.mkdir(parents=True)
        plugin = package_dir / "_texpdf_plugin_macosx.plugin"
        plugin.write_bytes(b"universal-plugin")
        plugin_sha = sha256(plugin)
        helper = {"sha256": HELPER_SHA, "size_bytes": 123}
        build = {
            "schema_version": 1,
            "package": "texpdf",
            "package_version": "0.1.0-rc2",
            "target": "universal2-apple-darwin",
            "installed_plugin": plugin.name,
            "plugin_sha256": plugin_sha,
            "plugin_size_bytes": plugin.stat().st_size,
            "embedded_helper_sha256": None,
            "embedded_helper_size_bytes": None,
            "embedded_helper_count": 2,
            "embedded_helpers": {
                "aarch64-apple-darwin": helper,
                "x86_64-apple-darwin": {"sha256": "4" * 64, "size_bytes": 124},
            },
            "bundle_zip_sha256": BUNDLE_SHA,
            "bundle_zip_size_bytes": 456,
            "public_release_mode": True,
            "license_evidence_included": True,
            "release_license_complete": True,
            "license_audit_source_sha": SOURCE_SHA,
        }
        write_json(package_dir / "BUILD_INFO.json", build)
        checked = [plugin.name, "BUILD_INFO.json"]
        (package_dir / "CHECKSUMS.sha256").write_text(
            "".join(f"{sha256(package_dir / name)}  {name}\n" for name in checked),
            encoding="utf-8",
        )
        archive = universal_dir / "texpdf-macos-universal-0.1.0-rc2.zip"
        with zipfile.ZipFile(archive, "w") as output:
            for path in sorted(package_dir.iterdir()):
                output.write(path, path.name)
        package = {
            **build,
            "package_directory": "texpdf",
            "package_zip": archive.name,
            "package_zip_sha256": sha256(archive),
            "package_zip_size_bytes": archive.stat().st_size,
            "installed_files": [*checked, "CHECKSUMS.sha256"],
        }
        write_json(universal_dir / "package-manifest.json", package)
        write_json(
            universal_dir / "manifest.json",
            {
                "schema_version": 1,
                "source_sha": SOURCE_SHA,
                "architectures": ["arm64", "x86_64"],
                "arm_runtime_qualified": True,
                "intel_runtime_qualified": False,
                "exports": ["pginit", "stata_call"],
                "dynamic_dependencies": ["/usr/lib/libSystem.B.dylib"],
                "universal": {
                    "sha256": plugin_sha,
                    "size_bytes": plugin.stat().st_size,
                    "target": "universal2-apple-darwin",
                },
                "slices": {
                    "arm64": {
                        "sha256": "5" * 64,
                        "size_bytes": 10,
                        "target": "aarch64-apple-darwin",
                        "embedded_helper": {
                            **helper,
                            "target": "aarch64-apple-darwin",
                        },
                    },
                    "x86_64": {
                        "sha256": "6" * 64,
                        "size_bytes": 11,
                        "target": "x86_64-apple-darwin",
                        "embedded_helper": {
                            "sha256": "4" * 64,
                            "size_bytes": 124,
                            "target": "x86_64-apple-darwin",
                        },
                    },
                },
            },
        )
        write_json(
            evidence / "bundle-info.json",
            {"schema_version": 1, "zip_sha256": BUNDLE_SHA},
        )
        (evidence / "rust-quick.status").write_text(
            "schema_version=1\nrust_status=success\nrust_mode=repository-engine\ncompleted=1\n",
            encoding="utf-8",
        )
        return universal_dir / "manifest.json", universal_dir / "package-manifest.json"

    def run_script(self, root: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--artifact-root",
                str(root),
                "--output-dir",
                str(output),
                "--expect-source-sha",
                SOURCE_SHA,
                "--expect-package-version",
                "0.1.0-rc2",
                "--universal-run-id",
                "12345",
                "--artifact-name",
                f"texpdf-macos-universal-{SOURCE_SHA}-12345",
                "--artifact-digest",
                "sha256:" + "7" * 64,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_materializes_exact_universal_runtime_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "artifact"
            output = Path(temporary) / "output"
            self.prepare_artifact(root)
            result = self.run_script(root, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            runtime = json.loads(
                (output / "package-manifest.json").read_text(encoding="utf-8")
            )
            provenance = json.loads(
                (output / "memory-input.json").read_text(encoding="utf-8")
            )
            self.assertEqual(runtime["target"], "aarch64-apple-darwin")
            self.assertEqual(runtime["embedded_helper_sha256"], HELPER_SHA)
            self.assertEqual(provenance["universal_run_id"], 12345)
            self.assertEqual(provenance["plugin_sha256"], runtime["plugin_sha256"])

    def test_rejects_helper_mismatch_between_slice_and_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "artifact"
            output = Path(temporary) / "output"
            universal_path, _ = self.prepare_artifact(root)
            universal = json.loads(universal_path.read_text(encoding="utf-8"))
            universal["slices"]["arm64"]["embedded_helper"]["sha256"] = "8" * 64
            write_json(universal_path, universal)
            result = self.run_script(root, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("helper inventory", result.stderr)


if __name__ == "__main__":
    unittest.main()
