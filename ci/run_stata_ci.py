#!/usr/bin/env python3
"""Stage tracked source, run one licensed-Stata profile, and emit a receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile


DEFAULT_STATA = Path("/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp")
CANONICAL_PLUGIN_FILENAMES = (
    "_texpdf_plugin_macosx.plugin",
    "_texpdf_plugin_unix.plugin",
    "_texpdf_plugin_windows.plugin",
)


def command_output(command: list[str], cwd: Path) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def repo_root() -> Path:
    return Path(
        command_output(["git", "rev-parse", "--show-toplevel"], Path.cwd())
    ).resolve()


def artifact_directory(root: Path) -> Path:
    configured = os.environ.get("TEXPDF_STATA_ARTIFACT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return root / ".ci" / "stata" / "run"


def tracked_files(root: Path) -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=root)
    files: list[Path] = []
    for name in raw.split(b"\0"):
        if not name:
            continue
        relative = Path(os.fsdecode(name))
        source = (root / relative).resolve()
        if source.is_file() and source.is_relative_to(root):
            files.append(relative)
    return files


def exclude_ssc_marker_from_canonical_staging(stata_directory: Path) -> None:
    if any((stata_directory / name).is_file() for name in CANONICAL_PLUGIN_FILENAMES):
        (stata_directory / "_texpdf_ssc_install.ado").unlink(missing_ok=True)


def stage_repository(root: Path, destination: Path) -> None:
    for relative in tracked_files(root):
        source = root / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    exclude_ssc_marker_from_canonical_staging(destination / "stata")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def host_plugin_filename() -> str:
    if sys.platform == "darwin":
        return "_texpdf_plugin_macosx.plugin"
    if sys.platform == "win32":
        return "_texpdf_plugin_windows.plugin"
    if sys.platform.startswith("linux"):
        return "_texpdf_plugin_unix.plugin"
    raise RuntimeError(f"unsupported Stata CI platform: {sys.platform}")


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def stage_runtime_artifacts(staged_root: Path, run_root: Path) -> dict[str, object] | None:
    package_text = os.environ.get("TEXPDF_STATA_PACKAGE_DIR")
    plugin_text = os.environ.get("TEXPDF_STATA_PLUGIN")
    manifest_text = os.environ.get("TEXPDF_STATA_PACKAGE_MANIFEST")
    if not any((package_text, plugin_text, manifest_text)):
        return None

    package_source = Path(package_text).expanduser().resolve() if package_text else None
    if package_source is not None and not package_source.is_dir():
        raise FileNotFoundError(f"Stata package directory is missing: {package_source}")

    manifest: dict[str, object] = {}
    if manifest_text:
        manifest_path = Path(manifest_text).expanduser().resolve()
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("TEXPDF_STATA_PACKAGE_MANIFEST must contain a JSON object")
        manifest = value
    installed_plugin = manifest.get("installed_plugin", host_plugin_filename())
    if not isinstance(installed_plugin, str) or installed_plugin != host_plugin_filename():
        raise ValueError(
            "package manifest plugin does not match this Stata operating system: "
            f"{installed_plugin}"
        )

    plugin_source = Path(plugin_text).expanduser().resolve() if plugin_text else None
    if plugin_source is None and package_source is not None:
        plugin_source = package_source / installed_plugin
    if plugin_source is None or not plugin_source.is_file():
        raise FileNotFoundError(f"Stata plugin is missing: {plugin_source}")

    staged_plugin = staged_root / "stata" / installed_plugin
    staged_plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plugin_source, staged_plugin)

    # The tracked source tree contains the SSC-only installation marker so it
    # can be assembled into the combined submission.  A qualified canonical
    # plugin, however, represents a GitHub package, whose package builder
    # deliberately excludes that marker.  Mirror the installed GitHub layout
    # in the staged adopath so the source marker cannot masquerade as a second
    # SSC installation during the initial plugin smoke test.
    exclude_ssc_marker_from_canonical_staging(staged_plugin.parent)

    staged_package: Path | None = None
    if package_source is not None:
        staged_package = run_root / "package"
        shutil.copytree(package_source, staged_package)
        os.environ["TEXPDF_STATA_PACKAGE_DIR"] = str(staged_package)

    identity: dict[str, object] = {
        "schema_version": 1,
        "installed_plugin": installed_plugin,
        "plugin_sha256": sha256_file(staged_plugin),
        "plugin_size_bytes": staged_plugin.stat().st_size,
        "package_directory": "isolated-qualified-package" if staged_package else None,
        "package_version": manifest.get("package_version"),
        "package_zip_sha256": manifest.get("package_zip_sha256"),
        "package_zip_size_bytes": manifest.get("package_zip_size_bytes"),
        "bundle_zip_sha256": manifest.get("bundle_zip_sha256"),
        "embedded_helper_sha256": manifest.get("embedded_helper_sha256"),
        "embedded_helper_size_bytes": manifest.get("embedded_helper_size_bytes"),
        "license_evidence_included": manifest.get("license_evidence_included"),
        "target": manifest.get("target"),
    }
    expected_plugin = manifest.get("plugin_sha256")
    if expected_plugin is not None and expected_plugin != identity["plugin_sha256"]:
        raise ValueError("package manifest does not match the staged Stata plugin")
    return identity


def clear_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def bundle_version(stata_executable: Path) -> str:
    info_plist = stata_executable.parents[1] / "Info.plist"
    try:
        with info_plist.open("rb") as handle:
            value = plistlib.load(handle).get("CFBundleShortVersionString")
    except (OSError, plistlib.InvalidFileException):
        return "unknown"
    return str(value) if value is not None else "unknown"


def seed_stata_plus(config: dict[str, object], run_root: Path) -> None:
    source_root = Path(
        os.environ.get(
            "STATA_PLUS_SOURCE", "~/Library/Application Support/Stata/ado/plus"
        )
    ).expanduser().resolve()
    destination_root = (run_root / "stata-plus").resolve()
    entries = config.get("stata_plus_files", [])
    if not isinstance(entries, list):
        raise ValueError("stata_plus_files must be a list")
    for raw_name in entries:
        if not isinstance(raw_name, str):
            raise ValueError("stata_plus_files entries must be strings")
        relative = Path(raw_name)
        source = (source_root / relative).resolve()
        destination = (destination_root / relative).resolve()
        if not source.is_relative_to(source_root) or not destination.is_relative_to(
            destination_root
        ):
            raise ValueError(f"unsafe Stata PLUS dependency path: {raw_name}")
        if not source.is_file():
            raise FileNotFoundError(f"required Stata dependency is missing: {raw_name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def install_macos_viewer_shim(run_root: Path) -> None:
    viewer_log = run_root / "viewer-invocations.txt"
    os.environ["TEXPDF_VIEW_LOG"] = str(viewer_log)
    if sys.platform != "darwin":
        return
    shim_directory = run_root / "viewer-bin"
    shim_directory.mkdir()
    opener = shim_directory / "open"
    opener.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "printf '%s\\n' \"$@\" >> \"$TEXPDF_VIEW_LOG\"\n",
        encoding="utf-8",
    )
    opener.chmod(0o755)
    os.environ["PATH"] = str(shim_directory) + os.pathsep + os.environ.get("PATH", "")


def copy_evidence(run_root: Path, artifact_dir: Path) -> None:
    for source in sorted(run_root.iterdir()):
        # Stata's process stdout can contain the startup/license banner.  The
        # explicit text log begins after startup and is the safe artifact.
        if not source.is_file():
            continue
        if source.name == "process.stdout.log":
            continue
        if source.suffix == ".log" and source.name != "stata.log":
            continue
        shutil.copy2(source, artifact_dir / source.name)


def tail(path: Path, lines: int = 100) -> str:
    try:
        values = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(values[-lines:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", nargs="?", default="smoke")
    args = parser.parse_args()

    root = repo_root()
    config_path = root / "ci" / "stata_profiles.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    profiles = config.get("profiles", {})
    if args.profile not in profiles:
        choices = ", ".join(sorted(profiles))
        parser.error(f"unknown profile {args.profile!r}; choose one of: {choices}")
    profile = profiles[args.profile]

    artifact_dir = artifact_directory(root)
    clear_directory(artifact_dir)
    parent = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="texpdf-stata-ci-", dir=parent)
    )
    staged_root = run_root / "repo"
    staged_root.mkdir()
    stage_repository(root, staged_root)
    artifact_identity = stage_runtime_artifacts(staged_root, run_root)
    for directory in (
        "stata-plus",
        "stata-personal",
        "stata-oldplace",
        "stata-site",
        "output",
    ):
        (run_root / directory).mkdir()
    seed_stata_plus(config, run_root)
    install_macos_viewer_shim(run_root)

    tested_sha = os.environ.get("GITHUB_SHA") or command_output(
        ["git", "rev-parse", "HEAD"], root
    )
    stata_executable = Path(
        os.environ.get("STATA_BIN", str(DEFAULT_STATA))
    ).expanduser().resolve()
    status_file = run_root / "stata.status"
    stata_log = run_root / "stata.log"
    process_json = run_root / "process.json"
    process_log = run_root / "process.stdout.log"
    artifact_json = run_root / "artifact.json"
    if artifact_identity is not None:
        write_json_atomic(artifact_json, artifact_identity)
    timeout_seconds = int(profile["timeout_seconds"])
    raw_arguments = profile.get("arguments", [])
    if not isinstance(raw_arguments, list):
        raise ValueError("profile arguments must be a list")
    replacements = {"repo_root": str(staged_root), "run_root": str(run_root)}
    suite_arguments = [str(value).format(**replacements) for value in raw_arguments]

    stata_flags = ["/q", "/e"] if sys.platform == "win32" else ["-q", "-b"]
    stata_command = [
        str(stata_executable),
        *stata_flags,
        "do",
        str(staged_root / "ci" / "stata_ci.do"),
        str(staged_root / str(profile["suite"])),
        str(status_file),
        str(stata_log),
        args.profile,
        str(staged_root),
        str(run_root),
        *suite_arguments,
    ]
    supervisor = [
        sys.executable,
        str(staged_root / "ci" / "supervise_stata.py"),
        "--timeout-seconds",
        str(timeout_seconds),
        "--process-json",
        str(process_json),
        "--stdout-log",
        str(process_log),
        "--cwd",
        str(run_root),
        "--",
        *stata_command,
    ]
    supervisor_rc = subprocess.run(supervisor, check=False).returncode
    if supervisor_rc != 0 and not process_json.exists():
        process_json.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "started_at": None,
                    "completed_at": None,
                    "duration_seconds": None,
                    "process_rc": supervisor_rc,
                    "timed_out": False,
                    "launch_error": (
                        f"Stata supervisor exited with code {supervisor_rc}"
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    copy_evidence(run_root, artifact_dir)
    receipt_path = artifact_dir / "receipt.json"
    make_receipt = [
        sys.executable,
        str(staged_root / "ci" / "make_stata_receipt.py"),
        "--profile-config",
        str(staged_root / "ci" / "stata_profiles.json"),
        "--profile",
        args.profile,
        "--process-json",
        str(process_json),
        "--status-file",
        str(status_file),
        "--run-dir",
        str(run_root),
        "--receipt",
        str(receipt_path),
        "--tested-sha",
        tested_sha,
        "--repository",
        os.environ.get("GITHUB_REPOSITORY", "local/texpdf"),
        "--ref",
        os.environ.get("GITHUB_REF", "local"),
        "--run-id",
        os.environ.get("GITHUB_RUN_ID", "local"),
        "--run-attempt",
        os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "--runner-name",
        os.environ.get("RUNNER_NAME", "local-mac"),
        "--stata-executable",
        str(stata_executable),
        "--stata-bundle-version",
        bundle_version(stata_executable),
    ]
    if artifact_json.is_file():
        make_receipt.extend(["--artifact-json", str(artifact_json)])
    receipt_rc = subprocess.run(make_receipt, check=False).returncode
    copy_evidence(run_root, artifact_dir)

    if os.environ.get("STATA_CI_KEEP_TEMP") == "1":
        print(f"STATA_CI_TEMP={run_root}")
    else:
        shutil.rmtree(run_root)

    if receipt_rc != 0:
        return receipt_rc
    checker = [
        sys.executable,
        str(root / "ci" / "check_stata_receipt.py"),
        str(receipt_path),
        "--expect-tested-sha",
        tested_sha,
        "--expect-profile",
        args.profile,
        "--require-success",
    ]
    checker_result = subprocess.run(checker, check=False)
    if checker_result.returncode != 0:
        log_tail = tail(artifact_dir / "stata.log")
        if log_tail:
            print("--- CI log tail ---", file=sys.stderr)
            print(log_tail, file=sys.stderr)
    return checker_result.returncode


if __name__ == "__main__":
    sys.exit(main())
