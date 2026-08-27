#!/usr/bin/env python3
"""Unit tests for exact bundle reconstruction with generated resources."""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
from pathlib import Path
import subprocess
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
PREPARE_MODULE_PATH = TOOLS / "prepare_curated_bundle.py"
PREPARE_SPEC = importlib.util.spec_from_file_location(
    "prepare_curated_bundle", PREPARE_MODULE_PATH
)
if PREPARE_SPEC is None or PREPARE_SPEC.loader is None:
    raise RuntimeError(f"cannot load {PREPARE_MODULE_PATH}")
prepare_module = importlib.util.module_from_spec(PREPARE_SPEC)
sys.modules[PREPARE_SPEC.name] = prepare_module
PREPARE_SPEC.loader.exec_module(prepare_module)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BundleRebuildTests(unittest.TestCase):
    def test_range_builder_requires_every_exact_identity_field(self) -> None:
        bundle = {
            "name": "academic",
            "version": "1",
            "transform_version": "range-v2",
            "source_sha256": "1" * 64,
            "index_sha256": "2" * 64,
            "content_digest": "3" * 64,
            "zip_sha256": "4" * 64,
            "file_count": 10,
            "zip_size_bytes": 20,
            "uncompressed_resource_bytes": 30,
            "resource_policy_sha256": "5" * 64,
        }
        info = {
            "bundle_name": bundle["name"],
            "bundle_version": bundle["version"],
            "transform_version": bundle["transform_version"],
            "source_sha256": bundle["source_sha256"],
            "index_sha256": bundle["index_sha256"],
            "tectonic_bundle_digest": bundle["content_digest"],
            "zip_sha256": bundle["zip_sha256"],
            "file_count": bundle["file_count"],
            "zip_size_bytes": bundle["zip_size_bytes"],
            "uncompressed_resource_bytes": bundle["uncompressed_resource_bytes"],
            "resource_policy_sha256": bundle["resource_policy_sha256"],
        }
        prepare_module.require_exact_identity(info, {"bundle": bundle})
        info["zip_sha256"] = "6" * 64
        with self.assertRaisesRegex(prepare_module.BundleError, "zip_sha256"):
            prepare_module.require_exact_identity(info, {"bundle": bundle})

    def test_generated_bundle_resource_forces_lf_checkout_bytes(self) -> None:
        result = subprocess.run(
            [
                "git",
                "check-attr",
                "eol",
                "--",
                "bundle/resources/language.dat",
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.stdout.strip(),
            "bundle/resources/language.dat: eol: lf",
        )

    def test_committed_resource_trace_is_strict_base64(self) -> None:
        encoded = (REPOSITORY_ROOT / "bundle/resource-trace.txt.gz.b64").read_bytes()
        compressed = base64.b64decode(encoded, validate=True)
        names = gzip.decompress(compressed).decode("utf-8").splitlines()
        self.assertGreater(len(names), 1_000)
        self.assertEqual(names, sorted(set(names)))

    def test_bundle_info_preserves_required_qualification_identity(self) -> None:
        qualification = {
            "bundle": {
                "name": "academic",
                "version": "1",
                "transform_version": "range-v2",
                "source_sha256": "1" * 64,
                "index_sha256": "2" * 64,
                "content_digest": "3" * 64,
                "zip_sha256": "4" * 64,
                "file_count": 10,
                "zip_size_bytes": 20,
            }
        }
        payload = module.bundle_info_payload(qualification)
        self.assertEqual(payload["transform_version"], "range-v2")
        self.assertEqual(payload["source_sha256"], "1" * 64)
        self.assertEqual(payload["index_sha256"], "2" * 64)

    def test_bundle_info_fails_closed_when_identity_is_missing(self) -> None:
        with self.assertRaises(KeyError):
            module.bundle_info_payload({"bundle": {"name": "incomplete"}})

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
