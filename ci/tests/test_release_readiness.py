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
UNIVERSAL_HELPER_SHA = "a" * 64


class ReleaseReadinessRecordTests(unittest.TestCase):
    def test_required_targets_must_match_frozen_candidate(self) -> None:
        candidate = "1" * 40
        newer = "2" * 40
        scope = {
            "candidate_source_sha": candidate,
            "required_runtime_targets": ["arm", "linux", "windows"],
        }
        targets = {
            "arm": {"qualified_source_sha": newer},
            "linux": {"qualified_source_sha": candidate},
            "windows": {"qualified_source_sha": candidate},
        }
        checks: list[dict[str, object]] = []
        readiness.validate_required_source_coherence(scope, targets, checks)
        self.assertFalse(checks[-1]["passed"])

    def test_required_targets_accept_exact_frozen_candidate(self) -> None:
        candidate = "1" * 40
        scope = {
            "candidate_source_sha": candidate,
            "required_runtime_targets": ["arm", "linux", "windows"],
        }
        targets = {
            target: {"qualified_source_sha": candidate}
            for target in scope["required_runtime_targets"]
        }
        checks: list[dict[str, object]] = []
        readiness.validate_required_source_coherence(scope, targets, checks)
        self.assertTrue(checks[-1]["passed"])

    def test_license_coherence_allows_only_generated_evidence_commits(self) -> None:
        self.assertTrue(readiness.evidence_only_path("licenses/generated/STATUS.json"))
        self.assertTrue(readiness.evidence_only_path(".ci/stata/results/source.json"))
        self.assertTrue(readiness.evidence_only_path("release/targets.json"))
        self.assertFalse(readiness.evidence_only_path("tools/prepare_native_deps.sh"))

    def test_windows_runtime_equivalence_rejects_runtime_source_changes(self) -> None:
        self.assertTrue(readiness.windows_runtime_equivalence_path("CHANGELOG.md"))
        self.assertTrue(
            readiness.windows_runtime_equivalence_path("tools/package_release.py")
        )
        self.assertTrue(
            readiness.windows_runtime_equivalence_path("release/targets.json")
        )
        self.assertFalse(readiness.windows_runtime_equivalence_path("Cargo.lock"))
        self.assertFalse(
            readiness.windows_runtime_equivalence_path("crates/texpdf-core/src/lib.rs")
        )
        self.assertFalse(
            readiness.windows_runtime_equivalence_path("stata/texpdf_run.ado")
        )

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
                        "universal_plugin_sha256": UNIVERSAL_SHA,
                        "universal_plugin_size_bytes": 401,
                        "embedded_helper_sha256": HELPER_SHA,
                        "embedded_helper_size_bytes": 150,
                        "qualified_source_sha": SOURCE_SHA,
                        "receipt": f".ci/stata/results/{SOURCE_SHA}.json",
                        "stata_edition": "MP",
                        "stata_runtime_qualified": True,
                        "stata_version": "18",
                        "candidate_package_sha256": PACKAGE_SHA,
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
                        "candidate_package_sha256": PACKAGE_SHA,
                        "status": "Intel runtime untested by project policy",
                    },
                    "x86_64-pc-windows-msvc": {
                        "stata_runtime_qualified": False,
                        "status": "Windows pending",
                    },
                    "x86_64-unknown-linux-gnu": {
                        "artifact": "_texpdf_plugin_unix.plugin",
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
                            "sha256": UNIVERSAL_HELPER_SHA,
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
                    "version": "0.1.0-rc.2",
                    "zip_size_bytes": 300,
                    "zip_sha256": PACKAGE_SHA,
                    "license_evidence_included": True,
                    "license_audit_source_sha": SOURCE_SHA,
                    "public_release": False,
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
                "plugin": {"sha256": UNIVERSAL_SHA, "size_bytes": 401},
                "helper": {"sha256": UNIVERSAL_HELPER_SHA, "size_bytes": 150},
                "universal_package": {
                    "source_sha": SOURCE_SHA,
                    "universal_run_id": 12345,
                    "artifact_digest": "a" * 64,
                    "package_zip_sha256": PACKAGE_SHA,
                    "plugin_sha256": UNIVERSAL_SHA,
                    "arm_helper_sha256": UNIVERSAL_HELPER_SHA,
                    "bundle_zip_sha256": BUNDLE_SHA,
                },
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
                readiness.validate_linux_target(targets, checks, "0.1.0-rc.2")
                readiness.validate_other_targets(targets, checks)
                readiness.validate_license_status(checks)
                readiness.validate_memory(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertTrue(by_key["target_registry"]["passed"])
        self.assertTrue(by_key["macos_arm_runtime"]["passed"])
        self.assertTrue(by_key["macos_universal_build"]["passed"])
        self.assertTrue(by_key["macos_intel_compatibility_slice"]["passed"])
        self.assertNotIn("macos_intel_runtime", by_key)
        self.assertTrue(by_key["macos_candidate_package"]["passed"])
        self.assertTrue(by_key["third_party_license_complete"]["passed"])
        self.assertTrue(by_key["macos_arm_memory_stress"]["passed"])
        self.assertFalse(by_key["x86_64-pc-windows-msvc_runtime"]["passed"])
        self.assertFalse(by_key["linux_x86_64_runtime"]["passed"])

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

    def test_publication_state_requires_public_hardened_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scope = {"candidate_source_sha": SOURCE_SHA}
            write_json(
                root / "release/publication.json",
                {
                    "schema_version": 1,
                    "repository": "johannes-schmieder/texpdf",
                    "repository_visibility": "public",
                    "history_audit": {
                        "scanner": "gitleaks",
                        "scanner_version": "8.30.1",
                        "tip_sha": SOURCE_SHA,
                        "commits_scanned": 614,
                        "secrets_found": 0,
                        "history_rewritten": False,
                    },
                    "settings": {
                        "default_workflow_permissions": "read",
                        "can_approve_pull_request_reviews": False,
                        "sha_pinning_required": True,
                        "private_vulnerability_reporting": True,
                        "branch_protection": {
                            "allow_force_pushes": False,
                            "allow_deletions": False,
                        },
                    },
                    "historical_rc1": {
                        "tag_preserved": True,
                        "assets_preserved": True,
                        "superseded_label": True,
                    },
                },
            )
            with working_directory(root):
                checks: list[dict[str, object]] = []
                readiness.validate_publication_state(scope, checks)
            self.assertTrue(checks[0]["passed"])

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

    def test_memory_record_rejects_native_plugin_instead_of_universal_package(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            path = root / "release/memory-stress-macos-arm64.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["plugin"]["sha256"] = PLUGIN_SHA
            record["universal_package"]["plugin_sha256"] = PLUGIN_SHA
            write_json(path, record)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_memory(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertFalse(by_key["macos_arm_memory_stress"]["passed"])

    def test_candidate_requires_unqualified_intel_compatibility_slice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_universal(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertTrue(by_key["macos_intel_compatibility_slice"]["passed"])
        self.assertTrue(by_key["macos_candidate_package"]["passed"])

    def test_intel_runtime_claim_invalidates_compatibility_only_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            targets_path = root / "release/targets.json"
            registry = json.loads(targets_path.read_text(encoding="utf-8"))
            intel = registry["targets"]["x86_64-apple-darwin"]
            intel["qualified_source_sha"] = SOURCE_SHA
            intel["stata_runtime_qualified"] = True
            write_json(targets_path, registry)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_universal(targets, checks)

        by_key = {row["key"]: row for row in checks}
        self.assertFalse(by_key["macos_intel_compatibility_slice"]["passed"])
        self.assertFalse(by_key["macos_candidate_package"]["passed"])

    def test_linux_candidate_requires_exact_build_package_and_three_runtimes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            package = {
                "package_version": "0.1.0-rc.2",
                "target": "x86_64-unknown-linux-gnu",
                "installed_plugin": "_texpdf_plugin_unix.plugin",
                "package_zip_sha256": PACKAGE_SHA,
                "package_zip_size_bytes": 300,
                "plugin_sha256": PLUGIN_SHA,
                "plugin_size_bytes": 200,
                "embedded_helper_sha256": HELPER_SHA,
                "embedded_helper_size_bytes": 150,
                "bundle_zip_sha256": BUNDLE_SHA,
                "bundle_zip_size_bytes": 100,
                "license_evidence_included": True,
                "release_license_complete": True,
                "license_audit_source_sha": SOURCE_SHA,
                "public_release_mode": False,
            }

            def receipt(version: str, profile: str) -> dict[str, object]:
                return {
                    "tested_sha": SOURCE_SHA,
                    "status": "success",
                    "stata_status": "success",
                    "stata_version": version,
                    "profile": profile,
                    "platform": "Unix; PC (64-bit x86-64)",
                    "required_log_markers": [{"marker": "PASS", "present": True}],
                    "artifact": {
                        "plugin_sha256": PLUGIN_SHA,
                        "package_zip_sha256": PACKAGE_SHA,
                        "bundle_zip_sha256": BUNDLE_SHA,
                    },
                }

            write_json(
                root / "release/linux-x86_64.json",
                {
                    "schema_version": 1,
                    "qualified": True,
                    "source_sha": SOURCE_SHA,
                    "target": "x86_64-unknown-linux-gnu",
                    "build_receipt": {
                        "status": "success",
                        "source_sha": SOURCE_SHA,
                        "rust_tests": "success",
                        "cargo_target_seed": "fresh-empty-run-directory",
                        "plugin_sha256": PLUGIN_SHA,
                        "helper_sha256": HELPER_SHA,
                        "package_sha256": PACKAGE_SHA,
                        "binary_policy": {
                            "maximum_allowed_glibc": "2.28",
                            "violations": [],
                        },
                    },
                    "package": package,
                    "runtimes": {
                        "stata_18_quick": receipt("18", "quick"),
                        "stata_18_stress1000": receipt("18", "stress1000"),
                        "stata_19_quick": receipt("19", "quick"),
                    },
                },
            )
            targets_path = root / "release/targets.json"
            registry = json.loads(targets_path.read_text(encoding="utf-8"))
            registry["targets"]["x86_64-unknown-linux-gnu"].update(
                {
                    "build_qualified": True,
                    "build_source_sha": SOURCE_SHA,
                    "qualified_source_sha": SOURCE_SHA,
                    "stata_runtime_qualified": True,
                    "plugin_sha256": PLUGIN_SHA,
                    "embedded_helper_sha256": HELPER_SHA,
                    "candidate_package_sha256": PACKAGE_SHA,
                    "minimum_glibc": "2.28",
                    "tested_stata_versions": ["18", "19"],
                    "receipt": "release/linux-x86_64.json",
                }
            )
            write_json(targets_path, registry)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_linux_target(targets, checks, "0.1.0-rc.2")

        by_key = {row["key"]: row for row in checks}
        self.assertTrue(by_key["linux_x86_64_runtime"]["passed"])

    def test_windows_candidate_requires_static_crt_and_exact_stata19_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_records(root)
            package = {
                "package_version": "0.1.0-rc2",
                "target": "x86_64-pc-windows-msvc",
                "installed_plugin": "_texpdf_plugin_windows.plugin",
                "package_zip_sha256": PACKAGE_SHA,
                "plugin_sha256": PLUGIN_SHA,
                "embedded_helper_sha256": HELPER_SHA,
                "bundle_zip_sha256": BUNDLE_SHA,
                "license_evidence_included": True,
                "release_license_complete": True,
                "license_audit_source_sha": SOURCE_SHA,
                "public_release_mode": False,
            }

            def receipt(profile: str) -> dict[str, object]:
                markers = (
                    ["TEXPDF STRESS 1000 PASS"]
                    if profile == "stress1000"
                    else [
                        "TEXPDF REALISTIC CORPUS PASS",
                        "TEXPDF HELP EXAMPLES PASS",
                        "TEXPDF FULL ENGINE STATA PASS",
                    ]
                )
                return {
                    "tested_sha": SOURCE_SHA,
                    "status": "success",
                    "stata_status": "success",
                    "stata_version": "19.0",
                    "stata_edition": "MP",
                    "profile": profile,
                    "platform": "Windows; PC (64-bit x86-64)",
                    "required_log_markers": [
                        {"marker": marker, "present": True} for marker in markers
                    ],
                    "artifact": {
                        "plugin_sha256": PLUGIN_SHA,
                        "package_zip_sha256": PACKAGE_SHA,
                        "bundle_zip_sha256": BUNDLE_SHA,
                    },
                }

            write_json(
                root / "release/windows-x86_64.json",
                {
                    "schema_version": 1,
                    "qualified": True,
                    "source_sha": SOURCE_SHA,
                    "target": "x86_64-pc-windows-msvc",
                    "build_receipt": {
                        "status": "success",
                        "source_sha": SOURCE_SHA,
                        "rust_tests": "success",
                        "plugin_sha256": PLUGIN_SHA,
                        "helper_sha256": HELPER_SHA,
                        "package_sha256": PACKAGE_SHA,
                        "binary_policy": {
                            "static_msvc_crt": True,
                            "violations": [],
                        },
                    },
                    "package": package,
                    "runtimes": {
                        "stata_19_quick": receipt("quick"),
                        "stata_19_stress1000": receipt("stress1000"),
                    },
                },
            )
            targets_path = root / "release/targets.json"
            registry = json.loads(targets_path.read_text(encoding="utf-8"))
            registry["targets"]["x86_64-pc-windows-msvc"].update(
                {
                    "artifact": "_texpdf_plugin_windows.plugin",
                    "build_qualified": True,
                    "build_source_sha": SOURCE_SHA,
                    "qualified_source_sha": SOURCE_SHA,
                    "stata_runtime_qualified": True,
                    "plugin_sha256": PLUGIN_SHA,
                    "embedded_helper_sha256": HELPER_SHA,
                    "candidate_package_sha256": PACKAGE_SHA,
                    "tested_stata_versions": ["19"],
                    "receipt": "release/windows-x86_64.json",
                }
            )
            write_json(targets_path, registry)
            with working_directory(root):
                checks: list[dict[str, object]] = []
                targets = readiness.read_targets(checks)
                readiness.validate_windows_target(targets, checks, "0.1.0-rc2")

        by_key = {row["key"]: row for row in checks}
        self.assertTrue(by_key["windows_x86_64_runtime"]["passed"])


if __name__ == "__main__":
    unittest.main()
