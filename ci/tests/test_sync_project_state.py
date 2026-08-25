#!/usr/bin/env python3
"""Tests for canonical project-state selection and rendering."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "texpdf_sync_project_state", ROOT / "tools/sync_project_state.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load sync_project_state.py")
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


class ProjectStateTests(unittest.TestCase):
    def test_receipt_selection_follows_git_history_not_filename_order(self) -> None:
        older = "1" * 40
        newer = "2" * 40
        receipts = {
            older: {"tested_sha": older, "rust_mode": "repository-engine"},
            newer: {"tested_sha": newer, "rust_mode": "repository-engine"},
        }
        self.assertEqual(
            state.select_receipt([newer, older], receipts)["tested_sha"], newer
        )

    def test_repository_engine_selection_skips_non_engine_receipt(self) -> None:
        engine = "1" * 40
        newer = "2" * 40
        receipts = {
            engine: {"tested_sha": engine, "rust_mode": "repository-engine"},
            newer: {"tested_sha": newer, "rust_mode": "stub"},
        }
        selected = state.select_receipt(
            [newer, engine], receipts, repository_engine=True
        )
        self.assertEqual(selected["tested_sha"], engine)

    def test_status_labels_failed_memory_as_attempt_not_qualification(self) -> None:
        sha = "1" * 40
        digest = "2" * 64
        fixture = {
            "scope": {
                "candidate_version": "0.1.0-rc.2",
                "required_runtime_targets": [
                    "aarch64-apple-darwin",
                    "x86_64-apple-darwin",
                    "x86_64-unknown-linux-gnu",
                ],
            },
            "readiness": {
                "candidate_ready": False,
                "public_release_ready": False,
                "candidate_blockers": ["macos_arm_memory_stress"],
                "public_release_blockers": ["public_distribution"],
            },
            "latest_engine": {
                "tested_sha": sha,
                "profile": "quick",
                "rust_mode": "repository-engine",
                "platform": "macOS",
                "stata_edition": "MP",
                "stata_version": "18",
            },
            "artifact_source": sha,
            "targets": {
                "aarch64-apple-darwin": {
                    "qualified_source_sha": sha,
                    "stata_runtime_qualified": True,
                    "plugin_size_bytes": 100,
                    "plugin_sha256": digest,
                },
                "x86_64-apple-darwin": {},
            },
            "universal": {
                "source_sha": sha,
                "universal": {"size_bytes": 200, "sha256": digest},
            },
            "licenses": {"tex_resources": {}},
            "memory": {
                "source_sha": sha,
                "qualified": False,
                "memory": {
                    "iterations_requested": 1000,
                    "post_warmup_growth_kib": 800000,
                    "max_allowed_growth_kib": 524288,
                    "growth_gate": False,
                },
            },
        }
        rendered = state.render_status(fixture)
        self.assertIn("failed attempt", rendered)
        self.assertIn("qualified=no", rendered)
        self.assertNotIn("memory stress qualified", rendered.lower())


if __name__ == "__main__":
    unittest.main()
