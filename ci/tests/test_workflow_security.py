from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check_workflow_security.py"
SPEC = importlib.util.spec_from_file_location("workflow_security", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowSecurityTests(unittest.TestCase):
    def write(self, root: Path, name: str, text: str) -> Path:
        path = root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_repository_workflows_pass(self) -> None:
        self.assertEqual(MODULE.audit(), [])

    def test_rejects_pull_request_and_mutable_action_on_self_hosted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write(
                Path(temporary),
                "unsafe.yml",
                """name: Unsafe
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v6
""",
            )
            failures = MODULE.audit_workflow(path)
            self.assertTrue(any("pull_request" in item for item in failures))
            self.assertTrue(any("full commit SHA" in item for item in failures))

    def test_rejects_unapproved_write_permission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write(
                Path(temporary),
                "unapproved.yml",
                """name: Unapproved
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  unsafe:
    permissions:
      contents: write
""",
            )
            self.assertIn(
                "contents: write is not approved for this workflow",
                MODULE.audit_workflow(path),
            )


if __name__ == "__main__":
    unittest.main()
