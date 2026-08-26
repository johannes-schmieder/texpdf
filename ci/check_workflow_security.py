#!/usr/bin/env python3
"""Fail-closed static security policy for public GitHub Actions workflows."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github/workflows"
PINNED_REF = re.compile(r"^[0-9a-f]{40}$")
WRITE_WORKFLOWS = {
    "build-macos-universal.yml",
    "license-audit.yml",
    "publish-artifact-manifest.yml",
    "publish-artifact-summary.yml",
    "publish-target-qualification.yml",
    "qualify-macos-intel.yml",
    "stress-memory-macos.yml",
    "stata-ci.yml",
    "sync-project-state-on-green.yml",
}


def top_level_block(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line == f"{key}:"), None)
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line[0].isspace():
            break
        block.append(line)
    return block


def audit_workflow(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    triggers = "\n".join(top_level_block(text, "on"))
    permissions = "\n".join(top_level_block(text, "permissions"))
    sensitive = "self-hosted" in text or "STATA_BIN" in text or "stata-mp" in text

    if re.search(r"(?m)^\s{2}pull_request_target\s*:", triggers):
        failures.append("pull_request_target is prohibited")
    if sensitive and re.search(r"(?m)^\s{2}pull_request\s*:", triggers):
        failures.append("licensed or self-hosted workflows may not run on pull_request")
    if not permissions:
        failures.append("top-level permissions block is required")
    if re.search(r"(?m)^\s{2}contents:\s+write\s*$", permissions):
        if path.name not in WRITE_WORKFLOWS:
            failures.append("contents: write is not approved for this workflow")
    elif not re.search(r"(?m)^\s{2}contents:\s+read\s*$", permissions):
        failures.append("contents permission must be explicitly read or narrowly approved write")

    write_permissions = re.findall(r"(?m)^\s+(?P<name>[A-Za-z_-]+):\s+write\s*$", text)
    if "contents" in write_permissions and path.name not in WRITE_WORKFLOWS:
        failures.append("contents: write is not approved for this workflow")
    foreign_writes = sorted({name for name in write_permissions if name != "contents"})
    if foreign_writes:
        failures.append(f"unapproved write permissions: {foreign_writes}")

    for match in re.finditer(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", text):
        value = match.group(1).strip("'\"")
        if value.startswith("./"):
            continue
        if "@" not in value:
            failures.append(f"action has no immutable ref: {value}")
            continue
        action, ref = value.rsplit("@", 1)
        if not action or PINNED_REF.fullmatch(ref) is None:
            failures.append(f"action is not pinned to a full commit SHA: {value}")
    return failures


def audit(root: Path = WORKFLOW_ROOT) -> list[str]:
    paths = sorted((*root.glob("*.yml"), *root.glob("*.yaml")))
    if not paths:
        return [f"no workflows found under {root}"]
    failures: list[str] = []
    for path in paths:
        failures.extend(f"{path.name}: {failure}" for failure in audit_workflow(path))
    return failures


def main() -> int:
    failures = audit()
    if failures:
        print("\n".join(f"TEXPDF_WORKFLOW_SECURITY_ERROR {item}" for item in failures), file=sys.stderr)
        return 2
    count = len((*WORKFLOW_ROOT.glob("*.yml"), *WORKFLOW_ROOT.glob("*.yaml")))
    print(f"TEXPDF_WORKFLOW_SECURITY_PASS workflows={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
