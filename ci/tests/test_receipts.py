from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


CI_DIR = Path(__file__).resolve().parents[1]
TESTED_SHA = "a" * 40
RUN_STATA_SPEC = importlib.util.spec_from_file_location(
    "texpdf_run_stata_ci", CI_DIR / "run_stata_ci.py"
)
assert RUN_STATA_SPEC is not None and RUN_STATA_SPEC.loader is not None
RUN_STATA = importlib.util.module_from_spec(RUN_STATA_SPEC)
RUN_STATA_SPEC.loader.exec_module(RUN_STATA)


class ReceiptTests(unittest.TestCase):
    def test_macos_viewer_shim_records_exact_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(RUN_STATA.sys, "platform", "darwin"), mock.patch.dict(
                os.environ, {"PATH": "/usr/bin"}, clear=False
            ):
                RUN_STATA.install_macos_viewer_shim(root)
                opener = root / "viewer-bin/open"
                viewer_log = root / "viewer-invocations.txt"
                self.assertTrue(opener.is_file())
                self.assertTrue(os.access(opener, os.X_OK))
                self.assertEqual(os.environ["TEXPDF_VIEW_LOG"], str(viewer_log))
                self.assertTrue(os.environ["PATH"].startswith(str(opener.parent)))
                subprocess.run(
                    [str(opener), "/tmp/report with spaces.pdf"],
                    check=True,
                    env=os.environ,
                )
                self.assertEqual(
                    viewer_log.read_text(encoding="utf-8"),
                    "/tmp/report with spaces.pdf\n",
                )

    def test_runtime_artifact_directory_can_be_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            destination = Path(temporary) / "receipts" / "stata-18-quick"
            with mock.patch.dict(
                os.environ, {"TEXPDF_STATA_ARTIFACT_DIR": str(destination)}
            ):
                self.assertEqual(
                    RUN_STATA.artifact_directory(root), destination.resolve()
                )

    def test_runtime_artifact_identity_writer_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested" / "artifact.json"
            payload = {"schema_version": 1, "plugin_sha256": "1" * 64}
            RUN_STATA.write_json_atomic(path, payload)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_repository_staging_excludes_marker_for_tracked_canonical_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            destination = Path(temporary) / "staged"
            stata = root / "stata"
            stata.mkdir(parents=True)
            files = {
                Path("stata/texpdf.ado"): b"program define texpdf\nend\n",
                Path("stata/_texpdf_ssc_install.ado"): b"program define marker\nend\n",
                Path("stata/_texpdf_plugin_macosx.plugin"): b"qualified-plugin",
            }
            for relative, data in files.items():
                (root / relative).write_bytes(data)

            with mock.patch.object(
                RUN_STATA,
                "tracked_files",
                return_value=list(files),
            ):
                RUN_STATA.stage_repository(root, destination)

            self.assertTrue((destination / "stata/texpdf.ado").is_file())
            self.assertTrue(
                (destination / "stata/_texpdf_plugin_macosx.plugin").is_file()
            )
            self.assertFalse(
                (destination / "stata/_texpdf_ssc_install.ado").exists()
            )

    def test_repository_staging_preserves_marker_without_canonical_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            destination = Path(temporary) / "staged"
            marker = root / "stata/_texpdf_ssc_install.ado"
            marker.parent.mkdir(parents=True)
            marker.write_text("program define marker\nend\n", encoding="utf-8")

            with mock.patch.object(
                RUN_STATA,
                "tracked_files",
                return_value=[Path("stata/_texpdf_ssc_install.ado")],
            ):
                RUN_STATA.stage_repository(root, destination)

            self.assertTrue(
                (destination / "stata/_texpdf_ssc_install.ado").is_file()
            )

    def test_runtime_artifact_staging_excludes_ssc_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged_root = root / "staged"
            staged_stata = staged_root / "stata"
            staged_stata.mkdir(parents=True)
            (staged_stata / "_texpdf_ssc_install.ado").write_text(
                "program define _texpdf_ssc_install\nend\n",
                encoding="utf-8",
            )
            package = root / "package-source"
            package.mkdir()
            plugin = package / "_texpdf_plugin_macosx.plugin"
            plugin.write_bytes(b"qualified-plugin")
            run_root = root / "run"
            run_root.mkdir()

            with mock.patch.object(RUN_STATA.sys, "platform", "darwin"), mock.patch.dict(
                os.environ,
                {"TEXPDF_STATA_PACKAGE_DIR": str(package)},
                clear=True,
            ):
                identity = RUN_STATA.stage_runtime_artifacts(staged_root, run_root)

            self.assertIsNotNone(identity)
            self.assertEqual(
                (staged_stata / "_texpdf_plugin_macosx.plugin").read_bytes(),
                b"qualified-plugin",
            )
            self.assertFalse((staged_stata / "_texpdf_ssc_install.ado").exists())
            self.assertTrue((run_root / "package/_texpdf_plugin_macosx.plugin").is_file())

    @staticmethod
    def normal_process(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:00:01Z",
            "duration_seconds": 1.0,
            "launch_error": None,
            "timed_out": False,
            "process_rc": 0,
        }
        value.update(overrides)
        return value

    @staticmethod
    def status(stata_rc: int) -> str:
        return (
            "schema_version=1\nprofile=smoke\n"
            f"stata_rc={stata_rc}\n"
            "stata_version=18\nstata_edition=MP\nstata_os=MacOSX\n"
            "stata_machine_type=Mac (Apple Silicon)\nstata_processors=8\n"
            f"tests_passed={int(stata_rc == 0)}\n"
            f"tests_failed={int(stata_rc != 0)}\ncompleted=1\n"
        )

    def build_receipt(
        self,
        *,
        process: dict[str, object],
        status: str | None,
        log: str = "PASS_MARKER\n",
        artifact: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "process.json").write_text(json.dumps(process), encoding="utf-8")
            if status is not None:
                (root / "stata.status").write_text(status, encoding="utf-8")
            if log:
                (root / "stata.log").write_text(log, encoding="utf-8")
            (root / "profiles.json").write_text(
                json.dumps(
                    {
                        "profiles": {
                            "smoke": {
                                "suite": "ci/stata_smoke.do",
                                "required_log_markers": ["PASS_MARKER"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            receipt_path = root / "receipt.json"
            command = [
                    sys.executable,
                    str(CI_DIR / "make_stata_receipt.py"),
                    "--profile-config",
                    str(root / "profiles.json"),
                    "--profile",
                    "smoke",
                    "--process-json",
                    str(root / "process.json"),
                    "--status-file",
                    str(root / "stata.status"),
                    "--run-dir",
                    str(root),
                    "--receipt",
                    str(receipt_path),
                    "--tested-sha",
                    TESTED_SHA,
                    "--stata-executable",
                    "/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp",
                ]
            if artifact is not None:
                artifact_path = root / "artifact.json"
                artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
                command.extend(["--artifact-json", str(artifact_path)])
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(receipt_path.read_text(encoding="utf-8"))

    def test_success(self) -> None:
        receipt = self.build_receipt(
            process=self.normal_process(), status=self.status(0)
        )
        self.assertEqual(receipt["status"], "success")
        self.assertEqual(receipt["stata_status"], "success")
        self.assertEqual(receipt["rust_status"], "not_run")
        self.assertEqual(receipt["tested_sha"], TESTED_SHA)

    def test_stata_error_wins_over_zero_process_rc(self) -> None:
        receipt = self.build_receipt(
            process=self.normal_process(process_rc=0), status=self.status(9)
        )
        self.assertEqual(receipt["failure_kind"], "stata_error")
        self.assertEqual(receipt["stata_rc"], 9)

    def test_artifact_identity_is_preserved(self) -> None:
        artifact = {
            "schema_version": 1,
            "plugin_sha256": "1" * 64,
            "package_zip_sha256": "2" * 64,
        }
        receipt = self.build_receipt(
            process=self.normal_process(), status=self.status(0), artifact=artifact
        )
        self.assertEqual(receipt["artifact"], artifact)

    def test_launch_timeout_crash_and_missing_outputs(self) -> None:
        cases = (
            (self.normal_process(process_rc=None, launch_error="missing"), None, "launch_error"),
            (self.normal_process(process_rc=-15, timed_out=True), None, "timeout"),
            (self.normal_process(process_rc=-9), None, "crash"),
            (self.normal_process(), None, "missing_status"),
        )
        for process, status, expected in cases:
            with self.subTest(expected=expected):
                receipt = self.build_receipt(process=process, status=status)
                self.assertEqual(receipt["failure_kind"], expected)

    def test_missing_marker(self) -> None:
        receipt = self.build_receipt(
            process=self.normal_process(), status=self.status(0), log="OTHER\n"
        )
        self.assertEqual(receipt["failure_kind"], "missing_marker")


class AugmentTests(unittest.TestCase):
    def augment(self, rust_rc: int) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps({"status": "success", "stata_status": "success"}),
                encoding="utf-8",
            )
            status = root / "rust.status"
            status.write_text(
                "schema_version=1\n"
                f"rust_status={'success' if rust_rc == 0 else 'failure'}\n"
                f"rust_rc={rust_rc}\nrust_mode=toolchain-smoke\n"
                "rust_toolchain=stable-aarch64-apple-darwin\n"
                "rustc_version=rustc 1.97.1\ncompleted=1\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(CI_DIR / "augment_ci_receipt.py"),
                    str(receipt),
                    str(status),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(receipt.read_text(encoding="utf-8"))

    def test_rust_success_completes_combined_receipt(self) -> None:
        value = self.augment(0)
        self.assertEqual(value["status"], "success")
        self.assertEqual(value["rust_status"], "success")
        self.assertEqual(value["rust_mode"], "toolchain-smoke")

    def test_rust_failure_changes_combined_status(self) -> None:
        value = self.augment(7)
        self.assertEqual(value["status"], "failure")
        self.assertEqual(value["rust_status"], "failure")
        self.assertEqual(value["failure_kind"], "rust_error")


if __name__ == "__main__":
    unittest.main()
