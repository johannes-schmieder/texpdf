#!/usr/bin/env python3
"""Tests for source-bound embedded-resource notice collection."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPOSITORY_ROOT / "tools/collect_tex_license_notices.py"
SPEC = importlib.util.spec_from_file_location("collect_tex_license_notices", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class TexNoticeCollectionTests(unittest.TestCase):
    def test_collects_notice_and_binds_exact_resource_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = b"resource bytes"
            bundle = root / "bundle.zip"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("SHA256SUM", b"digest\n")
                archive.writestr("example.dat", data)
            digest = hashlib.sha256(data).hexdigest()
            notice = root / "licenses/NOTICE.txt"
            notice.parent.mkdir(parents=True)
            notice.write_text("Complete notice\n", encoding="utf-8")
            inventory = root / "inventory.json"
            write_json(
                inventory,
                {
                    "license_expressions": ["mit"],
                    "resources": [
                        {
                            "resource": "example.dat",
                            "status": "mapped",
                            "package": "example",
                            "license": "mit",
                        }
                    ],
                },
            )
            policy = root / "policy.json"
            write_json(
                policy,
                {
                    "schema_version": 1,
                    "expressions": {"mit": ["licenses/NOTICE.txt"]},
                },
            )
            evidence = root / "evidence.json"
            write_json(evidence, {"schema_version": 1, "evidence": {}})
            curated = root / "curated.json"
            write_json(
                curated,
                {
                    "bundle_zip_sha256": module.sha256_file(bundle),
                    "bundle_content_digest": "content",
                    "resources": [{"name": "example.dat", "sha256": digest}],
                },
            )
            output = root / "output"
            result = module.collect(
                inventory,
                policy,
                evidence,
                curated,
                bundle,
                output,
                root / "tex-notices.json",
                root,
            )
            self.assertTrue(result["complete"])
            attribution = json.loads(
                (output / "resource-attribution.json").read_text(encoding="utf-8")
            )
            self.assertEqual(attribution["resources"][0]["sha256"], digest)

    def test_unknown_expression_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory = root / "inventory.json"
            write_json(inventory, {"license_expressions": ["custom"], "resources": []})
            policy = root / "policy.json"
            write_json(policy, {"schema_version": 1, "expressions": {}})
            for name in ("evidence.json", "curated.json"):
                write_json(root / name, {})
            (root / "bundle.zip").write_bytes(b"not reached")
            with self.assertRaisesRegex(module.TexNoticeError, "without notice policy"):
                module.collect(
                    inventory,
                    policy,
                    root / "evidence.json",
                    root / "curated.json",
                    root / "bundle.zip",
                    root / "output",
                    root / "manifest.json",
                    root,
                )


if __name__ == "__main__":
    unittest.main()
