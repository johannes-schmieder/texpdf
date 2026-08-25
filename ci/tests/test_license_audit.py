from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


CI_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "texpdf_run_license_audit", CI_DIR / "run_license_audit.py"
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class LicenseAuditPortabilityTests(unittest.TestCase):
    def test_default_cache_uses_platform_temp_directory(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                AUDIT.default_license_cache(),
                Path(tempfile.gettempdir()) / "texpdf-license-cache",
            )

    def test_cache_and_rustup_can_be_overridden(self) -> None:
        with mock.patch.dict(
            os.environ, {"TEXPDF_LICENSE_CACHE": "/project/cache/licenses"}
        ):
            self.assertEqual(
                AUDIT.default_license_cache(), Path("/project/cache/licenses")
            )
        self.assertEqual(
            AUDIT.rustup_executable({"RUSTUP_BIN": "/project/tools/rustup"}),
            "/project/tools/rustup",
        )


if __name__ == "__main__":
    unittest.main()
