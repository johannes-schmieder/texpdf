#!/usr/bin/env python3
"""Unit tests for the fail-closed release-readiness record readers."""

from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    path = REPOSITORY_ROOT / relative_path
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


readiness = load_module(
    "texpdf_check_release_readiness",
    "tools/check_release_readiness.py",
)


@contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


SOURCE_SHA = "1" * 40
PLUGIN_SHA = "2" * 64
BUNDLE_SHA = "3" * 64
UNIVERSAL_SHA = "4" * 64
INTEL_SHA = "5" * 64
HELPER_SHA = "6" * 64
LOG_SHA = "7" * 64
PACKAGE_SHA = "8" * 64
INTEL_HELPER_SHA = "9" * 64


class ReleaseReadinessRecordTests(unittest.TestCase):
    def prepare_records(self, root: Path) -> None:
        write_json(
            root / ".ci/stata/results" / f"{SOURCE_SHA}.json",
            {
                "tested_sha": SOURCE_SHA,
                "profile": "quick",
                "status": "success",
                "stata_status": "success",
                "rust_status": "success",
                "rust_mode": "repository-engine",
            },
        )
        write_json(
            root / "release/targets.json",
            {
                "schema_version": 1,
                "targets": {
                    "aarch64-apple-darwin": {
                        "artifact": "_texpdf_plugin.plugin",
                        "build_qualified": True,
                        "build_source_sha": SOURCE_SHA,
                        "bundle_zip_sha256": BUNDLE_SHA,
                        "bundle_zip_size_bytes": 100,
                        "plugin_sha256": PLUGIN_SHA,
                        "plugin_size_bytes": 200,
                        "embedded_helper_sha256": HELPER_SHA,
                        "embedded_helper_size_bytes": 150,
                        "qualified_source_sha": SOURCE_SHA,
                        "receipt": f".ci/stata/results/{SOURCE_SHA}.json",
                        "stata_edition": "MP",
                        "stata_runtime_qualified": True,
                        "stata_version": "18",
                    },
                    "x86_64-apple-darwin": {
                        "build_qualified": True,
                        "build_source_sha": SOURCE_SHA,
                        "plugin_sha256": INTEL_SHA,
                        "plugin_size_bytes": 201,
                        "embedded_helper_sha256": INTEL_HELPER_SHA,
                        "embedded_helper_size_bytes": 151,
                        "universal_plugin_sha256": UNIVERSAL_SHA,
                        "universal_plugin_size_bytes": 401,
                        "qualified_source_sha": "",
                        "stata_runtime_qualified": False,
                        "status": "Intel runtime pending",
                    },
                    "x86_64-pc-windows-msvc": {
                        "stata_runtime_qualified": False,
                        "status": "Windows pending",
                    },
                    "x86_64-unknown-linux-gnu": {
                        "stata_runtime_qualified": False,
                        "status": "Linux pending",
                    },
                },
            },
        )
        write_json(
            root / "release/macos-universal.json",
            {
                "source_sha": SOURCE_SHA,
                "architectures": ["arm64", "x86_64"],
                "arm_runtime_qualified": True,
                "intel_runtime_qualified": False,
                "slices": {
                    "arm64": {
                        "size_bytes": 200,
                        "sha256": PLUGIN_SHA,
                        "embedded_helper": {
                            "size_bytes": 150,
                            "sha256": HELPER_SHA,
                        },
                    },
                    "x86_64": {
                        "size_bytes": 201,
                        "sha256": INTEL_SHA,
                        "embedded_helper": {
                            "size_bytes": 151,
                            "sha256": INTEL_HELPER_SHA,
                        },
                    },
                },
                "universal": {"size_bytes": 401, "sha256": UNIVERSAL_SHA},
                "candidate_package": {
                    "version": "0.1.0-rc.1",
                    "zip_size_bytes": 300,
                    "zip_sha256": PACKAGE_SHA,
                    "license_evidence_included": True,
                    "public_release": False,
                    "arm_and_intel_runtime_tested": False,
                },
            },
        )
        write_json(
            root / "release/memory-stress-macos-arm64.json",
            {
                "schema_version": 3,
                "source_sha": SOURCE_SHA,
                "qualified": True,
                "overall_status": "success",
                "stata_status": "success",
                "rust_status": "success",
                "rust_mode": "repository-engine",
                "plugin": {"sha256": PLUGIN_SHA, "size_bytes": 200},
                "helper": {"sha256": HELPER_SHA, "size_bytes": 150},
                "memory": {
                    "iterations_requested": 1000,
                    "runner_rc": 0,
                    "growth_gate": True,
                    "successful_compile_count": 1000,
                    "injected_failure_count": 42,
                    "expected_injected_failure_count": 42,
                    "post_error_recovery": True,
                    "helper_sample_count": 100,
                    "max_concurrent_helpers": 1,
                    "retained_helper_pids": [],
                    "stata_log_sha256": LOG_SHA,
                    "max_allowed_growth_kib": 65536,
                    "peak_stata_rss_kib": 250000,
                    "post_warmup_growth_kib": 1000,
                    "post_warmup_growth_ratio": 1.01,
                },
            },
        )
        write_json(
            root / "licenses/generated/STATUS.json",
            {
                "source_sha": SOURCE_SHA,
                "release_license_complete": True,
                "return_codes": {
                    "tex_inventory": 0,
                    "cargo_inventory": 0,
                    "dependency_inventory": 0,
                    "notice_collection": 0,
                },
                "tex_resources": {
                    "resource_count": 557,
                    "mapped": 557,
                    "ambiguous": 0,
                    "unmapped": 0,
                    "missing_license": 0,
                },
                "dependency_undeclared_count": 0,
                "missing_rust_notice_files": 0,
                "missing_native_notice_files": 0,
            },
        )

    def test_current_record_schemas_are_parsed_conservatively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_arm_target(targets, checks)
                readiness.validate_universal(targets, checks)
                readiness.validate_other_targets(targets, checks)
                readiness.validate_license_status(checks)
                readiness.validate_memory(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertTrue(by_key["target_registry"]["passed"])
        self.assertTrue(by_key["macos_arm_runtime"]["passed"])
        self.assertTrue(by_key["macos_universal_build"]["passed"])
        self.assertTrue(by_key["macos_intel_build"]["passed"])
        self.assertFalse(by_key["macos_intel_runtime"]["passed"])
        self.assertFalse(by_key["private_candidate_package"]["passed"])
        self.assertTrue(by_key["third_party_license_complete"]["passed"])
        self.assertTrue(by_key["macos_arm_memory_stress"]["passed"])
        self.assertFalse(by_key["x86_64-pc-windows-msvc_runtime"]["passed"])
        self.assertFalse(by_key["x86_64-unknown-linux-gnu_runtime"]["passed"])

    def test_license_status_fails_closed_on_one_unmapped_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            status_path = root / "licenses/generated/STATUS.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["release_license_complete"] = False
            status["tex_resources"]["mapped"] = 556
            status["tex_resources"]["unmapped"] = 1
            write_json(status_path, status)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                readiness.validate_license_status(checks)

        self.assertEqual(checks[0]["key"], "third_party_license_complete")
        self.assertFalse(checks[0]["passed"])
        self.assertTrue(checks[0]["release_blocker"])

    def test_runtime_target_requires_matching_exact_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            (root / ".ci/stata/results" / f"{SOURCE_SHA}.json").unlink()
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_arm_target(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertFalse(by_key["macos_arm_runtime"]["passed"])
        self.assertIn("missing exact receipt", str(by_key["macos_arm_runtime"]["detail"]))

    def test_memory_record_fails_closed_on_retained_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            path = root / "release/memory-stress-macos-arm64.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["memory"]["retained_helper_pids"] = [1234]
            write_json(path, record)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_memory(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertFalse(by_key["macos_arm_memory_stress"]["passed"])

    def test_private_candidate_requires_one_package_tested_in_both_runtimes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            targets_path = root / "release/targets.json"
            registry = json.loads(targets_path.read_text(encoding="utf-8"))
            arm = registry["targets"]["aarch64-apple-darwin"]
            intel = registry["targets"]["x86_64-apple-darwin"]
            arm["candidate_package_sha256"] = PACKAGE_SHA
            intel.update(
                {
                    "candidate_package_sha256": PACKAGE_SHA,
                    "qualified_source_sha": SOURCE_SHA,
                    "stata_runtime_qualified": True,
                }
            )
            write_json(targets_path, registry)

            universal_path = root / "release/macos-universal.json"
            universal = json.loads(universal_path.read_text(encoding="utf-8"))
            universal["intel_runtime_qualified"] = True
            universal["candidate_package"]["arm_and_intel_runtime_tested"] = True
            write_json(universal_path, universal)
            write_json(
                root / "release/macos-intel-runtime.json",
                {
                    "qualified": True,
                    "source_sha": SOURCE_SHA,
                    "universal_plugin_size_bytes": 401,
                    "universal_plugin_sha256": UNIVERSAL_SHA,
                    "intel_slice_size_bytes": 201,
                    "intel_slice_sha256": INTEL_SHA,
                    "intel_helper_size_bytes": 151,
                    "intel_helper_sha256": INTEL_HELPER_SHA,
                    "receipt": {
                        "tested_sha": SOURCE_SHA,
                        "status": "success",
                        "stata_status": "success",
                    },
                },
            )
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_universal(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertTrue(by_key["macos_intel_runtime"]["passed"])
        self.assertTrue(by_key["private_candidate_package"]["passed"])


if __name__ == "__main__":
    unittest.main()
