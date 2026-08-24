#!/usr/bin/env python3
"""Assemble a deterministic Stata installation tree and ZIP for texpdf.

Development packages always include the project license and a third-party notice
index. Public-release mode is fail-closed: it additionally requires a complete
source-bound license audit and incorporates the generated inventories and
collected license texts into the package tree.
"""

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
LICENSE_STATUS_PATH = Path("licenses/generated/STATUS.json")
LICENSE_GENERATED_ROOT = Path("licenses/generated")
PUBLIC_LICENSE_FILES = (
    "STATUS.json",
    "STATUS.md",
    "tex-resources.json",
    "tex-resources.md",
    "cargo.json",
    "cargo.md",
    "dependencies.json",
    "dependencies.md",
    "license-texts.json",
    "tex-notices.json",
    "license-sources.lock.json",
)


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


def package_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def relative_name(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def read_license_status() -> dict[str, object] | None:
    if not LICENSE_STATUS_PATH.is_file():
        return None
    value = json.loads(LICENSE_STATUS_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("license audit status is not a JSON object")
    return value


def license_status_complete(status: dict[str, object] | None) -> bool:
    if status is None or status.get("release_license_complete") is not True:
        return False
    tex = status.get("tex_resources")
    codes = status.get("return_codes") or status.get("stage_return_codes")
    return (
        isinstance(tex, dict)
        and int(tex.get("resource_count", 0)) > 0
        and int(tex.get("ambiguous", -1)) == 0
        and int(tex.get("unmapped", -1)) == 0
        and int(tex.get("missing_license", -1)) == 0
        and isinstance(codes, dict)
        and bool(codes)
        and all(value == 0 for value in codes.values())
        and int(status.get("dependency_undeclared_count", -1)) == 0
        and int(status.get("missing_rust_notice_files", -1)) == 0
        and int(status.get("missing_native_notice_files", -1)) == 0
        and status.get("tex_notice_complete") is True
        and int(status.get("tex_notice_file_count", 0)) > 0
    )


def install_public_license_tree(output_dir: Path) -> list[str]:
    installed: list[str] = []
    destination_root = output_dir / "LICENSES"
    for name in PUBLIC_LICENSE_FILES:
        source = LICENSE_GENERATED_ROOT / name
        copy_atomic(source, destination_root / name)
        installed.append(f"LICENSES/{name}")

    texts_root = LICENSE_GENERATED_ROOT / "texts"
    if not texts_root.is_dir():
        raise FileNotFoundError(texts_root)
    for source in sorted(path for path in texts_root.rglob("*") if path.is_file()):
        relative = source.relative_to(LICENSE_GENERATED_ROOT)
        destination = destination_root / relative
        copy_atomic(source, destination)
        installed.append(relative_name(output_dir, destination))
    return installed


def append_pkg_files(pkg_path: Path, names: list[str]) -> None:
    if not names:
        return
    text = pkg_path.read_text(encoding="utf-8")
    existing = {
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("f ") and line[2:].strip()
    }
    additions = [name for name in sorted(names) if name not in existing]
    if additions:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "".join(f"f {name}\n" for name in additions)
        pkg_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument(
        "--embedded-helper",
        type=Path,
        help="target helper whose exact bytes were embedded in the plugin",
    )
    parser.add_argument("--bundle-info", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target", default="aarch64-apple-darwin")
    parser.add_argument("--package-version", default="0.1.0")
    parser.add_argument(
        "--public-release",
        action="store_true",
        help="require and package complete third-party license evidence",
    )
    args = parser.parse_args()

    try:
        bundle_info = json.loads(args.bundle_info.read_text(encoding="utf-8"))
        if bundle_info.get("schema_version") != 1:
            raise ValueError("unsupported bundle-info schema")
        license_status = read_license_status()
        license_complete = license_status_complete(license_status)
        if args.public_release and args.embedded_helper is None:
            raise ValueError("public-release mode requires --embedded-helper provenance")
        if args.embedded_helper is not None and not args.embedded_helper.is_file():
            raise FileNotFoundError(args.embedded_helper)
        if args.public_release and not license_complete:
            raise ValueError(
                "public-release mode requires licenses/generated/STATUS.json "
                "with release_license_complete=true and all fail-closed counts zero"
            )

        shutil.rmtree(args.output_dir, ignore_errors=True)
        args.output_dir.mkdir(parents=True)
        sources = {
            "texpdf.ado": Path("stata/texpdf.ado"),
            "texpdf.sthlp": Path("stata/texpdf.sthlp"),
            "texpdf.pkg": Path("stata/texpdf.pkg"),
            "stata.toc": Path("stata/stata.toc"),
            "_texpdf_plugin.plugin": args.plugin,
            "LICENSE": Path("LICENSE"),
            "THIRD_PARTY_NOTICES.md": Path("licenses/THIRD_PARTY_NOTICES.md"),
        }
        for name, source in sources.items():
            copy_atomic(source, args.output_dir / name)

        public_license_files: list[str] = []
        if args.public_release:
            public_license_files = install_public_license_tree(args.output_dir)
            append_pkg_files(args.output_dir / "texpdf.pkg", public_license_files)

        build_info = {
            "schema_version": 1,
            "package": "texpdf",
            "package_version": args.package_version,
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
            "embedded_helper_sha256": (
                sha256_file(args.embedded_helper)
                if args.embedded_helper is not None
                else None
            ),
            "embedded_helper_size_bytes": (
                args.embedded_helper.stat().st_size
                if args.embedded_helper is not None
                else None
            ),
            "standalone": True,
            "runtime_network_required": False,
            "system_tex_required": False,
            "public_release_mode": args.public_release,
            "release_license_complete": license_complete,
            "license_audit_source_sha": (
                license_status.get("source_sha") if license_status else None
            ),
            "packaged_license_file_count": len(public_license_files),
        }
        write_json_atomic(args.output_dir / "BUILD_INFO.json", build_info)

        checksums = {
            relative_name(args.output_dir, path): sha256_file(path)
            for path in package_files(args.output_dir)
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
            for path in package_files(args.output_dir):
                archive.writestr(
                    zip_info(relative_name(args.output_dir, path)), path.read_bytes()
                )
        os.replace(temporary_zip, args.zip_path)

        manifest = {
            **build_info,
            "package_directory": str(args.output_dir),
            "package_zip": str(args.zip_path),
            "package_zip_sha256": sha256_file(args.zip_path),
            "package_zip_size_bytes": args.zip_path.stat().st_size,
            "installed_files": [
                relative_name(args.output_dir, path)
                for path in package_files(args.output_dir)
            ],
        }
        write_json_atomic(args.manifest, manifest)
        print(
            "TEXPDF_PACKAGE_READY "
            f"dir={args.output_dir} zip={args.zip_path} "
            f"zip_bytes={manifest['package_zip_size_bytes']} "
            f"zip_sha256={manifest['package_zip_sha256']} "
            f"plugin_bytes={manifest['plugin_size_bytes']} "
            f"public_release={str(args.public_release).lower()} "
            f"license_complete={str(license_complete).lower()}",
            flush=True,
        )
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_PACKAGE_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
