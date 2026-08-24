#!/usr/bin/env python3
"""Fail when generated release/status documentation is stale."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, str(root / "tools/sync_project_state.py"), "--check"],
        cwd=root,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
