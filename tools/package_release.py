#!/usr/bin/env python3
"""Assemble a deterministic Stata installation tree and ZIP for texpdf."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def copy_atomic(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--bundle-info", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target", default="aarch64-apple-darwin")
    args = parser.parse_args()

    try:
        bundle_info = json.loads(args.bundle_info.read_text(encoding="utf-8"))
        if bundle_info.get("schema_version") != 1:
            raise ValueError("unsupported bundle-info schema")

        shutil.rmtree(args.output_dir, ignore_errors=True)
        args.output_dir.mkdir(parents=True)
        sources = {
            "texpdf.ado": Path("stata/texpdf.ado"),
            "texpdf.sthlp": Path("stata/texpdf.sthlp"),
            "texpdf.pkg": Path("stata/texpdf.pkg"),
            "stata.toc": Path("stata/stata.toc"),
            "_texpdf_plugin.plugin": args.plugin,
            "LICENSE": Path("LICENSE"),
        }
        for name, source in sources.items():
            copy_atomic(source, args.output_dir / name)

        build_info = {
            "schema_version": 1,
            "package": "texpdf",
            "package_version": "0.1.0",
            "target": args.target,
            "engine": "tectonic",
            "engine_version": "0.17.0",
            "bundle_name": bundle_info["bundle_name"],
            "bundle_version": bundle_info["bundle_version"],
            "bundle_digest": bundle_info["tectonic_bundle_digest"],
            "bundle_zip_sha256": bundle_info["zip_sha256"],
            "bundle_zip_size_bytes": bundle_info["zip_size_bytes"],
            "bundle_file_count": bundle_info["file_count"],
            "plugin_sha256": sha256_file(args.plugin),
            "plugin_size_bytes": args.plugin.stat().st_size,
            "standalone": True,
            "runtime_network_required": False,
            "system_tex_required": False,
        }
        write_json_atomic(args.output_dir / "BUILD_INFO.json", build_info)

        checksums = {
            path.name: sha256_file(path)
            for path in sorted(args.output_dir.iterdir())
            if path.is_file()
        }
        (args.output_dir / "CHECKSUMS.sha256").write_text(
            "".join(
                f"{digest}  {name}\n" for name, digest in sorted(checksums.items())
            ),
            encoding="utf-8",
        )

        args.zip_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_zip = args.zip_path.with_suffix(args.zip_path.suffix + ".tmp")
        temporary_zip.unlink(missing_ok=True)
        with zipfile.ZipFile(
            temporary_zip,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
            strict_timestamps=True,
        ) as archive:
            for path in sorted(args.output_dir.iterdir()):
                if path.is_file():
                    archive.writestr(zip_info(path.name), path.read_bytes())
        os.replace(temporary_zip, args.zip_path)

        manifest = {
            **build_info,
            "package_directory": str(args.output_dir),
            "package_zip": str(args.zip_path),
            "package_zip_sha256": sha256_file(args.zip_path),
            "package_zip_size_bytes": args.zip_path.stat().st_size,
            "installed_files": sorted(
                path.name for path in args.output_dir.iterdir() if path.is_file()
            ),
        }
        write_json_atomic(args.manifest, manifest)
        print(
            "TEXPDF_PACKAGE_READY "
            f"dir={args.output_dir} zip={args.zip_path} "
            f"zip_bytes={manifest['package_zip_size_bytes']} "
            f"zip_sha256={manifest['package_zip_sha256']} "
            f"plugin_bytes={manifest['plugin_size_bytes']}",
            flush=True,
        )
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_PACKAGE_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
