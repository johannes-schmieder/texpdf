#!/usr/bin/env python3
"""Unit tests for exact bundle reconstruction with generated resources."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPOSITORY_ROOT / "tools"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "rebuild_curated_bundle.py"
SPEC = importlib.util.spec_from_file_location("rebuild_curated_bundle", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BundleRebuildTests(unittest.TestCase):
    def test_generated_resource_is_rebuilt_from_repository_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "bundle/resources/language.dat"
            source.parent.mkdir(parents=True)
            data = b"english hyphen.tex\n=usenglish\n"
            source.write_bytes(data)
            manifest = {
                "resources": [
                    {
                        "name": "language.dat",
                        "generated": True,
                        "source": "bundle/resources/language.dat",
                        "origin": "texpdf-project-generated",
                        "length": len(data),
                        "sha256": sha256(data),
                    }
                ]
            }
            records = module.extract_records(manifest)
            digest = sha256(b"qualified-content")
            expected_zip = root / "expected.zip"
            with zipfile.ZipFile(
                expected_zip,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
                allowZip64=True,
                strict_timestamps=True,
            ) as archive:
                archive.writestr(module.zip_info("SHA256SUM"), f"{digest}\n".encode())
                archive.writestr(module.zip_info("language.dat"), data)
            qualification = {
                "bundle": {
                    "content_digest": digest,
                    "file_count": 2,
                    "zip_size_bytes": expected_zip.stat().st_size,
                    "zip_sha256": module.sha256_file(expected_zip),
                }
            }
            output = root / "rebuilt.zip"
            module.rebuild(records, [], qualification, root / "cache", output, root)
            self.assertEqual(output.read_bytes(), expected_zip.read_bytes())

    def test_generated_resource_hash_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "resource.dat"
            source.write_bytes(b"changed")
            records = module.extract_records(
                {
                    "resources": [
                        {
                            "name": "resource.dat",
                            "generated": True,
                            "source": "resource.dat",
                            "length": 7,
                            "sha256": sha256(b"expected"),
                        }
                    ]
                }
            )
            qualification = {
                "bundle": {
                    "content_digest": "0" * 64,
                    "file_count": 2,
                    "zip_size_bytes": 1,
                    "zip_sha256": "0" * 64,
                }
            }
            with self.assertRaisesRegex(module.RebuildError, "checksum mismatch"):
                module.rebuild(
                    records,
                    [],
                    qualification,
                    root / "cache",
                    root / "output.zip",
                    root,
                )


if __name__ == "__main__":
    unittest.main()
