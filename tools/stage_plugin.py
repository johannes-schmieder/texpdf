#!/usr/bin/env python3
"""Stage the Cargo cdylib under Stata's `.plugin` filename."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def native_library_name() -> str:
    if sys.platform == "darwin":
        return "libtexpdf_stata.dylib"
    if sys.platform.startswith("linux"):
        return "libtexpdf_stata.so"
    if os.name == "nt":
        return "texpdf_stata.dll"
    raise RuntimeError(f"unsupported native platform: {sys.platform}")


def installed_plugin_name() -> str:
    if sys.platform == "darwin":
        return "_texpdf_plugin_macosx.plugin"
    if sys.platform.startswith("linux"):
        return "_texpdf_plugin_unix.plugin"
    if os.name == "nt":
        return "_texpdf_plugin_windows.plugin"
    raise RuntimeError(f"unsupported native platform: {sys.platform}")


def verify_symbols(path: Path) -> list[str]:
    if sys.platform == "darwin":
        command = ["/usr/bin/nm", "-gU", str(path)]
    elif sys.platform.startswith("linux"):
        command = ["nm", "-D", "--defined-only", str(path)]
    else:
        return ["pginit", "stata_call"]

    result = subprocess.run(command, check=True, text=True, capture_output=True)
    output = result.stdout
    missing = [name for name in ("pginit", "stata_call") if name not in output]
    if missing:
        raise RuntimeError(f"native library is missing exports: {', '.join(missing)}")
    return ["pginit", "stata_call"]


def dynamic_dependencies(path: Path) -> tuple[list[str], list[str], str | None]:
    if sys.platform != "darwin":
        return [], [], None
    result = subprocess.run(
        ["/usr/bin/otool", "-L", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    dependencies: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        value = line.strip().split(" (compatibility version", 1)[0]
        if value:
            dependencies.append(value)

    install_id: str | None = None
    runtime_dependencies: list[str] = []
    for value in dependencies:
        if Path(value).name == native_library_name() and install_id is None:
            install_id = value
        else:
            runtime_dependencies.append(value)

    external = [
        value
        for value in runtime_dependencies
        if not value.startswith("/usr/lib/")
        and not value.startswith("/System/Library/")
    ]
    return runtime_dependencies, external, install_id


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("debug", "release"), default="release")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path(os.environ.get("CARGO_TARGET_DIR", "target")),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--manifest", type=Path, default=Path(".ci/stata/run/plugin-manifest.json")
    )
    args = parser.parse_args()
    if args.output is None:
        args.output = Path("stata") / installed_plugin_name()

    source = args.target_dir / args.profile / native_library_name()
    if not source.is_file():
        print(f"TEXPDF_PLUGIN_STAGE_ERROR missing native library: {source}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, args.output)
    try:
        exports = verify_symbols(args.output)
        dependencies, external_dependencies, install_id = dynamic_dependencies(args.output)
        if external_dependencies:
            raise RuntimeError(
                "plugin has non-system dynamic dependencies: "
                + ", ".join(external_dependencies)
            )
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        args.output.unlink(missing_ok=True)
        print(f"TEXPDF_PLUGIN_STAGE_ERROR {exc}", file=sys.stderr)
        return 2

    payload = {
        "schema_version": 1,
        "source": str(source),
        "output": str(args.output),
        "installed_plugin": args.output.name,
        "size_bytes": args.output.stat().st_size,
        "sha256": sha256_file(args.output),
        "platform": sys.platform,
        "exports": exports,
        "install_id": install_id,
        "dynamic_dependencies": dependencies,
        "external_dynamic_dependencies": external_dependencies,
    }
    write_json_atomic(args.manifest, payload)
    print(
        "TEXPDF_PLUGIN_READY "
        f"path={args.output} size_bytes={payload['size_bytes']} sha256={payload['sha256']} "
        f"dynamic_dependencies={len(dependencies)} external_dynamic_dependencies=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
