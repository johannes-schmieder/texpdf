#!/usr/bin/env python3
"""Generate the canonical human and machine-readable project state.

The repository has several evidence publishers.  This tool is the only place
that combines their outputs into release readiness and STATUS.md.  It never
treats branch position, a build-only artifact, or a failed attempt as runtime
qualification.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
READINESS_PATH = ROOT / "tools/check_release_readiness.py"
OUTPUTS = {
    ROOT / "release/READINESS.json": "json",
    ROOT / "release/READINESS.md": "readiness_markdown",
    ROOT / "STATUS.md": "status_markdown",
}
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class StateError(RuntimeError):
    """Repository evidence is absent or malformed."""


def load_readiness_module():
    specification = importlib.util.spec_from_file_location(
        "texpdf_check_release_readiness", READINESS_PATH
    )
    if specification is None or specification.loader is None:
        raise StateError(f"cannot load {READINESS_PATH}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def read_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StateError(f"cannot read {relative}: {error}") from error
    if not isinstance(value, dict):
        raise StateError(f"{relative} does not contain a JSON object")
    return value


def git_history() -> list[str]:
    process = subprocess.run(
        ["git", "rev-list", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise StateError(f"cannot read git history: {process.stderr.strip()}")
    return [line for line in process.stdout.splitlines() if SOURCE_SHA_RE.fullmatch(line)]


def successful_receipts() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    directory = ROOT / ".ci/stata/results"
    for path in directory.glob("*.json"):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        source = path.stem
        required = {
            "tested_sha": source,
            "status": "success",
            "stata_status": "success",
            "rust_status": "success",
        }
        if (
            SOURCE_SHA_RE.fullmatch(source)
            and isinstance(receipt, dict)
            and all(receipt.get(key) == value for key, value in required.items())
        ):
            records[source] = receipt
    return records


def select_receipt(
    history: list[str],
    receipts: dict[str, dict[str, Any]],
    *,
    repository_engine: bool = False,
) -> dict[str, Any]:
    for source in history:
        receipt = receipts.get(source)
        if receipt is None:
            continue
        if repository_engine and receipt.get("rust_mode") != "repository-engine":
            continue
        return receipt
    label = "repository-engine " if repository_engine else ""
    raise StateError(f"no successful {label}exact-SHA receipt is an ancestor of HEAD")


def yes_no(value: object) -> str:
    return "yes" if value is True else "no"


def mib(value: object) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return "unknown"
    return f"{size / 1024 / 1024:.2f} MiB"


def code(value: object, fallback: str = "not recorded") -> str:
    text = str(value or fallback)
    return f"`{text}`"


def build_state(readiness_result: dict[str, Any]) -> dict[str, Any]:
    scope = read_json("release/scope.json")
    targets_payload = read_json("release/targets.json")
    targets = targets_payload.get("targets", {})
    if not isinstance(targets, dict):
        raise StateError("release/targets.json has no target registry")
    universal = read_json("release/macos-universal.json")
    memory = read_json("release/memory-stress-macos-arm64.json")
    licenses = read_json("licenses/generated/STATUS.json")
    development_licenses = read_json("licenses/development-audit/STATUS.json")
    qualification = read_json("bundle/QUALIFICATION.json")
    development = read_json("bundle/DEVELOPMENT.json")
    receipts = successful_receipts()
    history = git_history()
    latest_green = select_receipt(history, receipts)
    latest_engine = select_receipt(history, receipts, repository_engine=True)

    arm = targets.get("aarch64-apple-darwin", {})
    if not isinstance(arm, dict):
        raise StateError("macOS ARM64 target record is malformed")
    artifact_source = str(arm.get("qualified_source_sha", ""))
    if not SOURCE_SHA_RE.fullmatch(artifact_source):
        raise StateError("macOS ARM64 artifact source SHA is malformed")
    artifact_receipt = receipts.get(artifact_source)
    if artifact_receipt is None:
        raise StateError("macOS ARM64 artifact has no successful exact-SHA receipt")

    return {
        "scope": scope,
        "readiness": readiness_result,
        "latest_green": latest_green,
        "latest_engine": latest_engine,
        "artifact_source": artifact_source,
        "artifact_receipt": artifact_receipt,
        "targets": targets,
        "universal": universal,
        "memory": memory,
        "licenses": licenses,
        "development_licenses": development_licenses,
        "qualification": qualification,
        "development": development,
    }


def render_status(state: dict[str, Any]) -> str:
    scope = state["scope"]
    readiness = state["readiness"]
    latest = state["latest_engine"]
    targets = state["targets"]
    arm = targets.get("aarch64-apple-darwin", {})
    intel = targets.get("x86_64-apple-darwin", {})
    universal = state["universal"]
    licenses = state["licenses"]
    tex = licenses.get("tex_resources", {})
    memory_record = state["memory"]
    memory = memory_record.get("memory", {})
    memory_qualified = memory_record.get("qualified") is True
    required = set(scope.get("required_runtime_targets", []))
    development = state.get("development", {})
    development_bundle = development.get("bundle", {})
    development_evidence = development.get("evidence", {})
    development_licenses = state.get("development_licenses", {})
    development_tex = development_licenses.get("tex_resources", {})

    lines = [
        "# texpdf status",
        "",
        "This file is generated by `tools/sync_project_state.py`. Edit the source",
        "evidence or release scope, then regenerate it; do not hand-edit status claims.",
        "",
        "## Release scope",
        "",
        f"The active target is a **private `{scope.get('candidate_version')}` macOS universal and Linux x86-64 release candidate**.",
        "Windows, public distribution, and final `v0.1.0` publication are",
        "explicitly deferred and are not advertised as supported.",
        "",
        f"Candidate ready: **{str(readiness.get('candidate_ready')).lower()}**",
        "",
        f"Public release ready: **{str(readiness.get('public_release_ready')).lower()}**",
        "",
        "Distribution channels: `main` is active development; an immutable final",
        "`vX.Y.Z` tag and GitHub Release define that stable version; SSC receives",
        "only the exact package from a final release. Release candidates are GitHub",
        "prereleases and are never submitted to SSC. See `RELEASING.md`.",
        "",
        "## Evidence boundaries",
        "",
        "The branch tip is a development position, not qualification evidence. Exact",
        "green source, artifact source, target runtime support, and failed attempts are",
        "tracked independently:",
        "",
        "| Meaning | Authoritative value |",
        "|---|---|",
        f"| Latest exact green source | {code(latest.get('tested_sha'))} |",
        f"| Green profile / Rust mode | {code(latest.get('profile'))} / {code(latest.get('rust_mode'))} |",
        f"| Licensed Stata runtime | {code(latest.get('platform'))}; {code(latest.get('stata_edition'))} {code(latest.get('stata_version'))} |",
        f"| Current ARM64 artifact source | {code(state.get('artifact_source'))} |",
        f"| Current universal build source | {code(universal.get('source_sha'))} |",
        f"| Frozen candidate license-audit source | {code(licenses.get('source_sha'))} |",
        f"| Latest memory-stress attempt | {code(memory_record.get('source_sha'))}; qualified={yes_no(memory_record.get('qualified'))} |",
        "",
        "## Development bundle on `main`",
        "",
        "The frozen private candidate and the current development bundle are different artifacts.",
        "Candidate readiness above applies only to the older qualified bytes and does not",
        "qualify the newer bundle embedded by `main`.",
        "",
        "| Development selection | Value |",
        "|---|---|",
        f"| Name / version | {code(development_bundle.get('name'))} / {code(development_bundle.get('version'))} |",
        f"| ZIP SHA-256 | {code(development_bundle.get('zip_sha256'))} |",
        f"| Content digest | {code(development_bundle.get('content_digest'))} |",
        f"| Selection status | {code(development.get('selection_status'))} |",
        f"| Tested source | {code(development_evidence.get('tested_source_sha'), 'pending')} |",
        f"| Apple Silicon licensed Stata | {code(development_evidence.get('macos_apple_silicon_stata'))} |",
        f"| Linux core corpus | {code(development_evidence.get('linux_core'))} |",
        f"| Development license audit | {code(development_licenses.get('source_sha'))}; complete={yes_no(development_licenses.get('release_license_complete'))} |",
        f"| Development TeX resources | {development_tex.get('mapped', 0)}/{development_tex.get('resource_count', 0)} mapped |",
        f"| Intel macOS / Linux licensed Stata | {code(development_evidence.get('intel_macos_stata'))} / {code(development_evidence.get('linux_stata'))} |",
        "",
        "## Architecture",
        "",
        "The installed Stata plugin is a thin SPI bridge. It verifies and extracts the",
        "target-matching compiler helper embedded in that same plugin, launches it",
        "directly without a shell, enforces a timeout, and validates the versioned result",
        "record plus helper digest. Tectonic and the curated offline TeX bundle live in",
        "the helper process, so a compiler crash does not run inside Stata.",
        "",
        "## Target qualification",
        "",
        "| Target | RC scope | Build qualified | Licensed Stata runtime | Evidence source |",
        "|---|---|---:|---:|---|",
    ]
    for target in (
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
        "x86_64-pc-windows-msvc",
        "x86_64-unknown-linux-gnu",
    ):
        record = targets.get(target, {})
        build = record.get("build_qualified") is True or (
            target == "aarch64-apple-darwin" and record.get("stata_runtime_qualified") is True
        )
        source = record.get("qualified_source_sha") or record.get("build_source_sha")
        lines.append(
            f"| `{target}` | {'required' if target in required else 'deferred'} | "
            f"{yes_no(build)} | {yes_no(record.get('stata_runtime_qualified'))} | {code(source)} |"
        )

    lines.extend(
        [
            "",
            "The current ARM64 plugin is "
            f"{mib(arm.get('plugin_size_bytes'))} ({code(arm.get('plugin_sha256'))}). "
            "The current universal plugin record is "
            f"{mib(universal.get('universal', {}).get('size_bytes'))} "
            f"({code(universal.get('universal', {}).get('sha256'))}).",
            "",
            "## Active private-candidate blockers",
            "",
        ]
    )
    blockers = readiness.get("candidate_blockers", [])
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Frozen candidate license evidence",
            "",
            f"The source-bound audit covers {tex.get('resource_count', 0)} embedded TeX/font resources: "
            f"{tex.get('mapped', 0)} mapped, {tex.get('ambiguous', 0)} ambiguous, "
            f"{tex.get('unmapped', 0)} unmapped, and {tex.get('missing_license', 0)} missing license metadata. "
            f"Missing collected Rust/native notice files: {licenses.get('missing_rust_notice_files', 0)}/"
            f"{licenses.get('missing_native_notice_files', 0)}.",
            "",
            "The separate development audit is source-bound to "
            f"{code(development_licenses.get('source_sha'))} and covers "
            f"{development_tex.get('resource_count', 0)} resources: "
            f"{development_tex.get('mapped', 0)} mapped, "
            f"{development_tex.get('ambiguous', 0)} ambiguous, and "
            f"{development_tex.get('unmapped', 0)} unmapped. It does not alter "
            "the frozen candidate evidence above.",
            "",
            "## Memory evidence",
            "",
            f"The latest preserved attempt requested {memory.get('iterations_requested', 0)} calls. "
            f"Post-warmup Stata RSS growth was {memory.get('post_warmup_growth_kib', 'unknown')} KiB "
            f"against a {memory.get('max_allowed_growth_kib', 'unknown')} KiB gate; "
            f"growth gate passed: {yes_no(memory.get('growth_gate'))}. "
            + (
                "This attempt is a qualified helper-lifecycle result."
                if memory_qualified
                else "This failed attempt is retained as evidence and is not described as qualification."
            ),
            "",
            "## Deferred public-release blockers",
            "",
        ]
    )
    public_blockers = readiness.get("public_release_blockers", [])
    if public_blockers:
        lines.extend(f"- `{blocker}`" for blocker in public_blockers)
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "See `release/READINESS.md` for the fail-closed check details and",
            "`docs/generated/CURRENT_ARTIFACT.md` for exact artifact measurements.",
            "",
        ]
    )
    return "\n".join(lines)


def expected_outputs() -> dict[Path, str]:
    readiness = load_readiness_module()
    previous = Path.cwd()
    os.chdir(ROOT)
    try:
        result = readiness.build_result()
        state = build_state(result)
    finally:
        os.chdir(previous)
    return {
        ROOT / "release/READINESS.json": json.dumps(result, indent=2, sort_keys=True) + "\n",
        ROOT / "release/READINESS.md": readiness.render_markdown(result),
        ROOT / "STATUS.md": render_status(state),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail if generated state is stale"
    )
    parser.add_argument(
        "--require-candidate-ready",
        action="store_true",
        help="also fail while a private-candidate blocker remains",
    )
    args = parser.parse_args()

    outputs = expected_outputs()
    stale: list[str] = []
    for path, content in outputs.items():
        if args.check:
            try:
                current = path.read_text(encoding="utf-8")
            except OSError:
                current = ""
            if current != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8")

    readiness = json.loads(outputs[ROOT / "release/READINESS.json"])
    if stale:
        print(f"TEXPDF_PROJECT_STATE_STALE files={','.join(stale)}", file=sys.stderr)
        return 2
    if args.require_candidate_ready and not readiness["candidate_ready"]:
        print(
            "TEXPDF_CANDIDATE_BLOCKED blockers="
            + ",".join(readiness["candidate_blockers"]),
            file=sys.stderr,
        )
        return 2
    print(
        "TEXPDF_PROJECT_STATE_CURRENT "
        f"candidate_ready={str(readiness['candidate_ready']).lower()} "
        f"public_ready={str(readiness['public_release_ready']).lower()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StateError, RuntimeError) as error:
        print(f"TEXPDF_PROJECT_STATE_ERROR {error}", file=sys.stderr)
        raise SystemExit(2)
