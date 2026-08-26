from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/assemble_ssc_package.py"
SOURCE = "a" * 40
PLATFORMS = {
    "macos": ("universal2-apple-darwin", "_texpdf_plugin_macosx.plugin"),
    "linux": ("x86_64-unknown-linux-gnu", "_texpdf_plugin_unix.plugin"),
    "windows": ("x86_64-pc-windows-msvc", "_texpdf_plugin_windows.plugin"),
}


class AssembleSscTests(unittest.TestCase):
    def package(self, root: Path, name: str, target: str, plugin: str) -> Path:
        package = root / name
        package.mkdir()
        for shared in (
            "texpdf.ado",
            "texpdf.sthlp",
            "texpdf_run.ado",
            "stata.toc",
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
        ):
            (package / shared).write_text(f"shared {shared}\n", encoding="utf-8")
        plugin_bytes = f"plugin {name}\n".encode()
        (package / plugin).write_bytes(plugin_bytes)
        (package / "LICENSES/texts/example/LICENSE").parent.mkdir(parents=True)
        (package / "LICENSES/texts/example/LICENSE").write_text(
            "license text\n", encoding="utf-8"
        )
        build = {
            "package_version": "0.1.0-rc2",
            "target": target,
            "installed_plugin": plugin,
            "public_release_mode": True,
            "release_license_complete": True,
            "license_audit_source_sha": SOURCE,
            "plugin_sha256": hashlib.sha256(plugin_bytes).hexdigest(),
            "plugin_size_bytes": len(plugin_bytes),
            "embedded_helpers": {target: {"sha256": "b" * 64, "size_bytes": 10}},
            "bundle_zip_sha256": "c" * 64,
        }
        (package / "BUILD_INFO.json").write_text(
            json.dumps(build), encoding="utf-8"
        )
        return package

    def test_combines_all_plugins_and_compresses_licenses_without_pkg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packages = {
                name: self.package(root, name, target, plugin)
                for name, (target, plugin) in PLATFORMS.items()
            }
            command = [
                sys.executable,
                str(SCRIPT),
                *(item for name, path in packages.items() for item in (f"--{name}", str(path))),
                "--source-sha",
                SOURCE,
                "--package-version",
                "0.1.0-rc2",
                "--release-kind",
                "public_release_candidate",
                "--output-dir",
                str(root / "ssc"),
                "--zip",
                str(root / "ssc.zip"),
                "--manifest",
                str(root / "manifest.json"),
            ]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(root / "ssc.zip") as archive:
                names = set(archive.namelist())
            self.assertTrue({value[1] for value in PLATFORMS.values()} <= names)
            self.assertIn("texpdf_licenses.zip", names)
            self.assertFalse(any(name.endswith(".pkg") for name in names))
            self.assertFalse(any(name.startswith("LICENSES/") for name in names))
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["submitted_pkg_file"])
            self.assertEqual(set(manifest["platforms"]), set(PLATFORMS))


if __name__ == "__main__":
    unittest.main()
