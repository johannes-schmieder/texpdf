#!/usr/bin/env python3
"""Run the source-bound third-party license audit without losing partial evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from typing import Any

CHUNK_SIZE = 1024 * 1024
DEFAULT_TLPDB_URL = (
    "https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2022/"
    "tlnet-final/tlpkg/texlive.tlpdb.xz"
)


def git_output(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], text=True).strip()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_tail(path: Path, lines: int = 30) -> str:
    try:
        values = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(values[-lines:])[-8000:]


def run_command(
    name: str,
    command: list[str],
    output_root: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    stdout_path = output_root / "logs" / f"{name}.stdout.log"
    stderr_path = output_root / "logs" / f"{name}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            completed = subprocess.run(
                command,
                cwd=Path.cwd(),
                env=environment,
                text=True,
                stdout=stdout,
                stderr=stderr,
                check=False,
            )
        return {
            "name": name,
            "command": command,
            "return_code": completed.returncode,
            "stdout_tail": bounded_tail(stdout_path),
            "stderr_tail": bounded_tail(stderr_path),
        }
    except OSError as error:
        return {
            "name": name,
            "command": command,
            "return_code": 127,
            "stdout_tail": "",
            "stderr_tail": str(error),
        }


def download_tlpdb(url: str, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not destination.is_file() or destination.stat().st_size == 0:
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.unlink(missing_ok=True)
            request = urllib.request.Request(
                url, headers={"User-Agent": "texpdf-license-audit/0.1"}
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                with temporary.open("wb") as output:
                    while chunk := response.read(CHUNK_SIZE):
                        output.write(chunk)
            os.replace(temporary, destination)
        return {
            "name": "download_tlpdb",
            "return_code": 0,
            "url": url,
            "path": str(destination),
            "size_bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "error": "",
        }
    except Exception as error:  # network/file failures must still produce status
        destination.with_suffix(destination.suffix + ".part").unlink(missing_ok=True)
        return {
            "name": "download_tlpdb",
            "return_code": 1,
            "url": url,
            "path": str(destination),
            "size_bytes": 0,
            "sha256": "",
            "error": f"{type(error).__name__}: {error}",
        }


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def prepare_native_environment(
    output_root: Path, base_environment: dict[str, str]
) -> tuple[dict[str, str], dict[str, Any]]:
    env_path = output_root / "native-environment.json"
    (output_root / "logs").mkdir(parents=True, exist_ok=True)
    script = r'''
set -euo pipefail
source tools/prepare_native_deps.sh
/usr/bin/python3 - "$TEXPDF_NATIVE_ENV_PATH" <<'PYENV'
from pathlib import Path
import json
import os
import sys
keys = ("VCPKG_ROOT", "VCPKGRS_TRIPLET", "TECTONIC_DEP_BACKEND", "PATH", "RUSTC")
Path(sys.argv[1]).write_text(
    json.dumps({key: os.environ.get(key, "") for key in keys}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PYENV
'''
    environment = dict(base_environment)
    environment["TEXPDF_NATIVE_ENV_PATH"] = str(env_path)
    stage = run_command(
        "prepare_native_dependencies",
        ["/bin/bash", "-c", script],
        output_root,
        environment,
    )
    if stage["return_code"] != 0:
        return base_environment, stage
    values = load_json(env_path)
    if not values:
        stage["return_code"] = 2
        stage["stderr_tail"] = "native dependency preparation produced no environment"
        return base_environment, stage
    merged = dict(base_environment)
    merged.update({str(key): str(value) for key, value in values.items() if value})
    return merged, stage


def summary_status(
    output_root: Path,
    source_sha: str,
    manifest_path: Path,
    tlpdb_stage: dict[str, Any],
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    tex = load_json(output_root / "tex-resources.json")
    cargo = load_json(output_root / "cargo.json")
    dependencies = load_json(output_root / "dependencies.json")
    texts = load_json(output_root / "license-texts.json")
    manifest = load_json(manifest_path)

    tex_summary = tex.get("summary", {}) if isinstance(tex.get("summary"), dict) else {}
    cargo_summary = (
        cargo.get("summary", {}) if isinstance(cargo.get("summary"), dict) else {}
    )
    manifest_count = int(manifest.get("file_count", 0) or 0)
    stage_codes = {stage["name"]: int(stage["return_code"]) for stage in stages}
    stage_codes["download_tlpdb"] = int(tlpdb_stage["return_code"])
    resource_count = int(tex_summary.get("resource_count", 0) or 0)
    resource_count_matches = manifest_count > 0 and resource_count == manifest_count
    undeclared = dependencies.get("undeclared_rust_licenses", [])
    missing_rust = texts.get("missing_rust_notice_files", [])
    missing_native = texts.get("missing_native_notice_files", [])
    release_complete = (
        all(value == 0 for value in stage_codes.values())
        and resource_count_matches
        and int(tex_summary.get("ambiguous", -1)) == 0
        and int(tex_summary.get("unmapped", -1)) == 0
        and int(tex_summary.get("missing_license", -1)) == 0
        and int(cargo_summary.get("missing_license_metadata", -1)) == 0
        and isinstance(undeclared, list)
        and not undeclared
        and isinstance(missing_rust, list)
        and not missing_rust
        and isinstance(missing_native, list)
        and not missing_native
        and texts.get("complete") is True
    )
    return {
        "schema_version": 2,
        "source_sha": source_sha,
        "pipeline_complete": all(value == 0 for value in stage_codes.values()),
        "release_license_complete": release_complete,
        "stage_return_codes": stage_codes,
        "stages": stages + [tlpdb_stage],
        "tex_resources": tex_summary,
        "cargo": cargo_summary,
        "dependency_undeclared_count": len(undeclared) if isinstance(undeclared, list) else -1,
        "missing_rust_notice_files": len(missing_rust) if isinstance(missing_rust, list) else -1,
        "missing_native_notice_files": len(missing_native) if isinstance(missing_native, list) else -1,
        "curated_manifest_file_count": manifest_count,
        "resource_count_matches_manifest": resource_count_matches,
        "tlpdb": {
            "url": tlpdb_stage.get("url"),
            "sha256": tlpdb_stage.get("sha256"),
            "size_bytes": tlpdb_stage.get("size_bytes"),
        },
        "qualification_boundary": (
            "This status records the audit pipeline even when a stage fails. "
            "Public binary publication remains blocked unless "
            "release_license_complete is true."
        ),
    }


def render_markdown(status: dict[str, Any]) -> str:
    tex = status.get("tex_resources", {})
    cargo = status.get("cargo", {})
    lines = [
        "# Third-party license audit status",
        "",
        f"- Source SHA: `{status.get('source_sha')}`",
        f"- Pipeline complete: **{str(status.get('pipeline_complete')).lower()}**",
        f"- Release-license complete: **{str(status.get('release_license_complete')).lower()}**",
        f"- Embedded resources: {tex.get('resource_count', 'unavailable')}",
        f"- Mapped resources: {tex.get('mapped', 'unavailable')}",
        f"- Ambiguous resources: {tex.get('ambiguous', 'unavailable')}",
        f"- Unmapped resources: {tex.get('unmapped', 'unavailable')}",
        f"- Resources missing license metadata: {tex.get('missing_license', 'unavailable')}",
        f"- Cargo packages: {cargo.get('package_count', 'unavailable')}",
        f"- Cargo packages missing metadata: {cargo.get('missing_license_metadata', 'unavailable')}",
        f"- Rust packages without collected notice files: {status.get('missing_rust_notice_files')}",
        f"- Native libraries without collected notice files: {status.get('missing_native_notice_files')}",
        "",
        "## Pipeline stages",
        "",
        "| Stage | Return code | Error tail |",
        "|---|---:|---|",
    ]
    for stage in status.get("stages", []):
        error = str(stage.get("stderr_tail") or stage.get("error") or "")
        error = error.replace("|", "\\|").replace("\n", " ")[-1000:]
        lines.append(
            f"| `{stage.get('name')}` | {stage.get('return_code')} | {error} |"
        )
    lines.extend(
        [
            "",
            "A successful workflow run means the audit produced durable evidence.",
            "Public release remains fail-closed until every blocking count is zero",
            "and `release_license_complete` is true in `STATUS.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root", type=Path, default=Path("licenses/generated")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("bundle/curated-manifest.json")
    )
    parser.add_argument(
        "--tlpdb-url", default=os.environ.get("TLPDB_URL", DEFAULT_TLPDB_URL)
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "TEXPDF_LICENSE_CACHE", "/private/tmp/texpdf-license-cache"
            )
        ),
    )
    args = parser.parse_args()

    root = Path(git_output("rev-parse", "--show-toplevel")).resolve()
    os.chdir(root)
    source_sha = os.environ.get("GITHUB_SHA") or git_output("rev-parse", "HEAD")
    shutil.rmtree(args.output_root, ignore_errors=True)
    args.output_root.mkdir(parents=True, exist_ok=True)

    environment = dict(os.environ)
    rustup = Path(environment.get("RUSTUP_BIN", "/opt/homebrew/bin/rustup"))
    toolchain = environment.get("RUST_TOOLCHAIN", "1.97.1")
    try:
        cargo = subprocess.check_output(
            [str(rustup), "which", "--toolchain", toolchain, "cargo"],
            text=True,
        ).strip()
        rustc = subprocess.check_output(
            [str(rustup), "which", "--toolchain", toolchain, "rustc"],
            text=True,
        ).strip()
        environment["PATH"] = f"{Path(cargo).parent}:/opt/homebrew/bin:/usr/local/bin:{environment.get('PATH', '')}"
        environment["RUSTC"] = rustc
        setup_stage: dict[str, Any] = {
            "name": "prepare_rust_toolchain",
            "return_code": 0,
            "stdout_tail": f"cargo={cargo}\nrustc={rustc}",
            "stderr_tail": "",
        }
    except (OSError, subprocess.CalledProcessError) as error:
        setup_stage = {
            "name": "prepare_rust_toolchain",
            "return_code": 1,
            "stdout_tail": "",
            "stderr_tail": str(error),
        }

    native_environment, native_stage = prepare_native_environment(
        args.output_root, environment
    )
    tlpdb_path = args.cache_dir / "texlive-2022-final.tlpdb.xz"
    tlpdb_stage = download_tlpdb(args.tlpdb_url, tlpdb_path)

    stages = [setup_stage, native_stage]
    commands = [
        (
            "tex_inventory",
            [
                sys.executable,
                "tools/generate_license_inventory.py",
                "--manifest",
                str(args.manifest),
                "--tlpdb",
                str(tlpdb_path),
                "--overrides",
                "bundle/license-overrides.toml",
                "--output",
                str(args.output_root / "tex-resources.json"),
                "--markdown",
                str(args.output_root / "tex-resources.md"),
                "--strict",
            ],
            tlpdb_stage["return_code"] == 0,
        ),
        (
            "cargo_inventory",
            [
                sys.executable,
                "tools/generate_cargo_license_inventory.py",
                "--output",
                str(args.output_root / "cargo.json"),
                "--markdown",
                str(args.output_root / "cargo.md"),
                "--strict",
            ],
            setup_stage["return_code"] == 0,
        ),
        (
            "dependency_inventory",
            [
                sys.executable,
                "tools/generate_dependency_inventory.py",
                "--json",
                str(args.output_root / "dependencies.json"),
                "--markdown",
                str(args.output_root / "dependencies.md"),
                "--require-declared",
            ],
            setup_stage["return_code"] == 0,
        ),
        (
            "collect_license_texts",
            [
                sys.executable,
                "tools/collect_dependency_license_texts.py",
                "--output-root",
                str(args.output_root / "texts"),
                "--manifest",
                str(args.output_root / "license-texts.json"),
                "--vcpkg-root",
                native_environment.get("VCPKG_ROOT", ""),
                "--triplet",
                native_environment.get("VCPKGRS_TRIPLET", ""),
                "--require-native",
            ],
            native_stage["return_code"] == 0,
        ),
    ]
    for name, command, enabled in commands:
        if enabled:
            stages.append(
                run_command(name, command, args.output_root, native_environment)
            )
        else:
            stages.append(
                {
                    "name": name,
                    "command": command,
                    "return_code": 125,
                    "stdout_tail": "",
                    "stderr_tail": "skipped because a prerequisite stage failed",
                }
            )

    status = summary_status(
        args.output_root, source_sha, args.manifest, tlpdb_stage, stages
    )
    write_json(args.output_root / "STATUS.json", status)
    (args.output_root / "STATUS.md").write_text(
        render_markdown(status), encoding="utf-8"
    )
    write_json(
        args.output_root / "license-sources.lock.json", status.get("tlpdb", {})
    )
    print(
        "TEXPDF_LICENSE_AUDIT_STATUS "
        f"pipeline_complete={str(status['pipeline_complete']).lower()} "
        f"release_complete={str(status['release_license_complete']).lower()} "
        f"source={source_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
