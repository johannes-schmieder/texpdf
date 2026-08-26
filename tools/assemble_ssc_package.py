#!/usr/bin/env python3
"""Combine qualified platform packages into one deterministic SSC submission."""

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
PLATFORMS = {
    "macos": ("universal2-apple-darwin", "_texpdf_plugin_macosx.plugin"),
    "linux": ("x86_64-unknown-linux-gnu", "_texpdf_plugin_unix.plugin"),
    "windows": ("x86_64-pc-windows-msvc", "_texpdf_plugin_windows.plugin"),
}
SHARED_FILES = (
    "texpdf.ado",
    "texpdf.sthlp",
    "texpdf_run.ado",
    "stata.toc",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def require_casefold_unique(root: Path) -> None:
    seen: dict[str, str] = {}
    for path in files(root):
        relative = path.relative_to(root).as_posix()
        folded = relative.casefold()
        previous = seen.get(folded)
        if previous is not None and previous != relative:
            raise ValueError(
                f"case-insensitive filename collision: {previous} and {relative}"
            )
        seen[folded] = relative


def deterministic_zip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
        strict_timestamps=True,
    ) as archive:
        for path in files(source):
            archive.writestr(zip_info(path.relative_to(source).as_posix()), path.read_bytes())
    os.replace(temporary, destination)


def load_build(package: Path) -> dict[str, object]:
    value = json.loads((package / "BUILD_INFO.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"malformed BUILD_INFO.json in {package}")
    return value


def directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in files(root):
        name = path.relative_to(root).as_posix().encode()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def validate_source_pkg(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    plugins = sorted(
        line.split(None, 1)[1]
        for line in lines
        if line.startswith("f _texpdf_plugin_") and line.endswith(".plugin")
    )
    expected = sorted(value[1] for value in PLATFORMS.values())
    if plugins != expected or lines.count("f texpdf_licenses.zip") != 1:
        raise ValueError("stata/texpdf.pkg is not synchronized with the SSC file set")


def assemble(args: argparse.Namespace) -> dict[str, object]:
    if len(args.source_sha) != 40 or any(c not in "0123456789abcdef" for c in args.source_sha):
        raise ValueError("--source-sha must be a lowercase 40-character Git SHA")
    packages = {name: Path(getattr(args, name)).resolve() for name in PLATFORMS}
    builds = {name: load_build(path) for name, path in packages.items()}
    license_digests: set[str] = set()
    shared_hashes: dict[str, str] = {}
    platform_records: dict[str, object] = {}

    validate_source_pkg(Path("stata/texpdf.pkg"))
    for name, (target, plugin_name) in PLATFORMS.items():
        package = packages[name]
        build = builds[name]
        if build.get("package_version") != args.package_version:
            raise ValueError(f"{name} package version mismatch")
        if build.get("target") != target or build.get("installed_plugin") != plugin_name:
            raise ValueError(f"{name} package target/plugin mismatch")
        if build.get("public_release_mode") is not True:
            raise ValueError(f"{name} package was not assembled in public-release mode")
        if build.get("release_license_complete") is not True:
            raise ValueError(f"{name} package has incomplete license evidence")
        if build.get("license_audit_source_sha") != args.source_sha:
            raise ValueError(f"{name} package license evidence belongs to another source")
        plugin = package / plugin_name
        if not plugin.is_file() or sha256(plugin) != build.get("plugin_sha256"):
            raise ValueError(f"{name} plugin identity mismatch")
        unexpected = [
            candidate.name
            for candidate in package.glob("_texpdf_plugin*.plugin")
            if candidate.name != plugin_name
        ]
        if unexpected:
            raise ValueError(f"{name} package contains foreign plugins: {unexpected}")
        licenses = package / "LICENSES"
        if not licenses.is_dir() or not files(licenses):
            raise ValueError(f"{name} package has no unpacked license tree")
        license_digests.add(directory_digest(licenses))
        for shared in SHARED_FILES:
            path = package / shared
            digest = sha256(path)
            if shared in shared_hashes and shared_hashes[shared] != digest:
                raise ValueError(f"shared package file differs by platform: {shared}")
            shared_hashes[shared] = digest
        platform_records[name] = {
            "target": target,
            "plugin": plugin_name,
            "plugin_sha256": build["plugin_sha256"],
            "plugin_size_bytes": build["plugin_size_bytes"],
            "embedded_helpers": build["embedded_helpers"],
            "bundle_zip_sha256": build["bundle_zip_sha256"],
        }
    if len(license_digests) != 1:
        raise ValueError("platform packages contain different license trees")
    bundle_hashes = {record["bundle_zip_sha256"] for record in platform_records.values()}
    if len(bundle_hashes) != 1:
        raise ValueError("platform packages contain different embedded bundles")

    output = Path(args.output_dir)
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    first = packages["macos"]
    for shared in SHARED_FILES:
        shutil.copyfile(first / shared, output / shared)
    for name, (_, plugin_name) in PLATFORMS.items():
        shutil.copyfile(packages[name] / plugin_name, output / plugin_name)
    deterministic_zip(first / "LICENSES", output / "texpdf_licenses.zip")

    combined = {
        "schema_version": 1,
        "package": "texpdf",
        "package_version": args.package_version,
        "release_kind": args.release_kind,
        "source_sha": args.source_sha,
        "distribution": "ssc-combined",
        "platforms": platform_records,
        "bundle_zip_sha256": next(iter(bundle_hashes)),
        "license_tree_digest": next(iter(license_digests)),
        "license_zip_sha256": sha256(output / "texpdf_licenses.zip"),
        "license_zip_size_bytes": (output / "texpdf_licenses.zip").stat().st_size,
        "submitted_pkg_file": False,
    }
    (output / "BUILD_MANIFEST.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_path = output / "CHECKSUMS.sha256"
    checksum_path.write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(output).as_posix()}\n"
            for path in files(output)
            if path != checksum_path
        ),
        encoding="utf-8",
    )
    require_casefold_unique(output)
    if any(path.suffix == ".pkg" for path in files(output)):
        raise ValueError("SSC submission must not contain a .pkg file")
    deterministic_zip(output, Path(args.zip_path))
    external = {
        **combined,
        "archive": str(args.zip_path),
        "archive_sha256": sha256(Path(args.zip_path)),
        "archive_size_bytes": Path(args.zip_path).stat().st_size,
        "installed_files": [path.relative_to(output).as_posix() for path in files(output)],
    }
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(external, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return external


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--macos", required=True)
    parser.add_argument("--linux", required=True)
    parser.add_argument("--windows", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument(
        "--release-kind", choices=("public_release_candidate", "final_release"), required=True
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--zip", dest="zip_path", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        result = assemble(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_SSC_PACKAGE_ERROR {error}", file=sys.stderr)
        return 2
    print(
        "TEXPDF_SSC_PACKAGE_READY "
        f"sha256={result['archive_sha256']} bytes={result['archive_size_bytes']} "
        f"source={result['source_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
