from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/write_release_index.py"
SOURCE = "a" * 40
PLATFORMS = {
    "macos": ("universal2-apple-darwin", "_texpdf_plugin_macosx.plugin"),
    "linux": ("x86_64-unknown-linux-gnu", "_texpdf_plugin_unix.plugin"),
    "windows": ("x86_64-pc-windows-msvc", "_texpdf_plugin_windows.plugin"),
}


class ReleaseIndexTests(unittest.TestCase):
    def test_writes_source_bound_combined_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets: list[str] = []
            for label, (target, plugin) in PLATFORMS.items():
                archive = root / f"texpdf-{label}.zip"
                archive.write_bytes(f"archive {label}".encode())
                manifest = root / f"{label}.json"
                manifest.write_text(
                    json.dumps(
                        {
                            "package_version": "0.1.0-rc2",
                            "target": target,
                            "installed_plugin": plugin,
                            "public_release_mode": True,
                            "release_license_complete": True,
                            "license_audit_source_sha": SOURCE,
                            "package_zip_sha256": hashlib.sha256(
                                archive.read_bytes()
                            ).hexdigest(),
                            "package_zip_size_bytes": archive.stat().st_size,
                        }
                    ),
                    encoding="utf-8",
                )
                assets.append(f"{label}={archive}={manifest}")
            archive = root / "texpdf-ssc.zip"
            archive.write_bytes(b"ssc")
            manifest = root / "ssc.json"
            manifest.write_text(
                json.dumps(
                    {
                        "package_version": "0.1.0-rc2",
                        "release_kind": "public_release_candidate",
                        "source_sha": SOURCE,
                        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                        "archive_size_bytes": archive.stat().st_size,
                        "submitted_pkg_file": False,
                    }
                ),
                encoding="utf-8",
            )
            assets.append(f"ssc={archive}={manifest}")
            command = [
                sys.executable,
                str(SCRIPT),
                "--source-sha",
                SOURCE,
                "--version",
                "0.1.0-rc2",
                "--release-kind",
                "public_release_candidate",
                *(item for asset in assets for item in ("--asset", asset)),
                "--manifest",
                str(root / "release-manifest.json"),
                "--checksums",
                str(root / "SHA256SUMS"),
            ]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads(
                (root / "release-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["source_sha"], SOURCE)
            self.assertEqual(set(index["artifacts"]), set(PLATFORMS) | {"ssc"})
            self.assertEqual(
                len((root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()),
                4,
            )


if __name__ == "__main__":
    unittest.main()
