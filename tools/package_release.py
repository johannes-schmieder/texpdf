#!/usr/bin/env python3
"""Assemble a deterministic Stata installation tree and ZIP for texpdf.

Development packages always include the project license and a third-party notice
index. Complete source-bound license evidence can be included in a private
candidate without enabling public-release mode. Both modes fail closed when the
full notice tree is requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import zipfile

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
CHUNK_SIZE = 1024 * 1024
LICENSE_STATUS_PATH = Path("licenses/generated/STATUS.json")
LICENSE_GENERATED_ROOT = Path("licenses/generated")
LICENSE_EVIDENCE_FILES = (
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
ADO_VERSION_RE = re.compile(
    r"^\*!\s+(?:version\s+)?(?:texpdf\s+)?(?P<version>\d+\.\d+\.\d+)\s+",
    re.MULTILINE,
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


def read_ado_version(path: Path = Path("stata/texpdf.ado")) -> str:
    match = ADO_VERSION_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{path} has no conventional version header")
    return match.group("version")


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


def install_license_evidence(output_dir: Path) -> list[str]:
    installed: list[str] = []
    destination_root = output_dir / "LICENSES"
    for name in LICENSE_EVIDENCE_FILES:
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


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def helper_provenance(
    plugin: Path,
    target: str,
    helper: Path | None,
    universal_manifest: Path | None,
) -> tuple[dict[str, dict[str, object]], str | None]:
    if helper is not None and universal_manifest is not None:
        raise ValueError(
            "use either --embedded-helper or --embedded-helper-manifest, not both"
        )
    if helper is not None:
        if not helper.is_file():
            raise FileNotFoundError(helper)
        return (
            {
                target: {
                    "sha256": sha256_file(helper),
                    "size_bytes": helper.stat().st_size,
                }
            },
            str(helper),
        )
    if universal_manifest is None:
        return {}, None
    data = json.loads(universal_manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported embedded-helper manifest schema")
    universal = data.get("universal")
    if (
        not isinstance(universal, dict)
        or universal.get("sha256") != sha256_file(plugin)
        or universal.get("size_bytes") != plugin.stat().st_size
    ):
        raise ValueError("embedded-helper manifest does not match the plugin")
    slices = data.get("slices")
    if not isinstance(slices, dict) or not slices:
        raise ValueError("embedded-helper manifest has no architecture slices")
    records: dict[str, dict[str, object]] = {}
    for slice_name, slice_record in sorted(slices.items()):
        if not isinstance(slice_record, dict):
            raise ValueError(f"malformed helper slice {slice_name}")
        embedded = slice_record.get("embedded_helper")
        if not isinstance(embedded, dict):
            raise ValueError(f"helper provenance is missing for slice {slice_name}")
        helper_target = embedded.get("target")
        helper_sha = embedded.get("sha256")
        helper_size = embedded.get("size_bytes")
        if (
            not isinstance(helper_target, str)
            or not helper_target
            or helper_target in records
            or not valid_sha256(helper_sha)
            or not isinstance(helper_size, int)
            or helper_size <= 0
        ):
            raise ValueError(f"invalid helper provenance for slice {slice_name}")
        records[helper_target] = {
            "sha256": helper_sha,
            "size_bytes": helper_size,
        }
    return records, str(universal_manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument(
        "--embedded-helper",
        type=Path,
        help="target helper whose exact bytes were embedded in the plugin",
    )
    parser.add_argument(
        "--embedded-helper-manifest",
        type=Path,
        help="universal-build manifest binding every slice to its embedded helper",
    )
    parser.add_argument("--bundle-info", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target", default="aarch64-apple-darwin")
    parser.add_argument(
        "--package-version",
        help="package version; defaults to the version in stata/texpdf.ado",
    )
    parser.add_argument(
        "--public-release",
        action="store_true",
        help="require and package complete third-party license evidence",
    )
    parser.add_argument(
        "--include-license-evidence",
        action="store_true",
        help="package complete notices for a private candidate without publishing it",
    )
    args = parser.parse_args()

    try:
        ado_version = read_ado_version()
        package_version = args.package_version or ado_version
        if package_version.split("-", 1)[0] != ado_version:
            raise ValueError(
                f"package version {package_version} does not match ado version {ado_version}"
            )
        bundle_info = json.loads(args.bundle_info.read_text(encoding="utf-8"))
        if bundle_info.get("schema_version") != 1:
            raise ValueError("unsupported bundle-info schema")
        license_status = read_license_status()
        license_complete = license_status_complete(license_status)
        helpers, helper_source = helper_provenance(
            args.plugin,
            args.target,
            args.embedded_helper,
            args.embedded_helper_manifest,
        )
        include_license_evidence = args.public_release or args.include_license_evidence
        if args.public_release and not helpers:
            raise ValueError("public-release mode requires embedded-helper provenance")
        if include_license_evidence and not license_complete:
            raise ValueError(
                "license-evidence packaging requires licenses/generated/STATUS.json "
                "with release_license_complete=true and all fail-closed counts zero"
            )

        shutil.rmtree(args.output_dir, ignore_errors=True)
        args.output_dir.mkdir(parents=True)
        sources = {
            "texpdf.ado": Path("stata/texpdf.ado"),
            "texpdf.sthlp": Path("stata/texpdf.sthlp"),
            "texpdf_run.ado": Path("stata/texpdf_run.ado"),
            "texpdf.pkg": Path("stata/texpdf.pkg"),
            "stata.toc": Path("stata/stata.toc"),
            "_texpdf_plugin.plugin": args.plugin,
            "LICENSE": Path("LICENSE"),
            "THIRD_PARTY_NOTICES.md": Path("licenses/THIRD_PARTY_NOTICES.md"),
        }
        for name, source in sources.items():
            copy_atomic(source, args.output_dir / name)

        packaged_license_files: list[str] = []
        if include_license_evidence:
            packaged_license_files = install_license_evidence(args.output_dir)

        single_helper = next(iter(helpers.values())) if len(helpers) == 1 else None

        build_info = {
            "schema_version": 1,
            "package": "texpdf",
            "package_version": package_version,
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
                single_helper["sha256"] if single_helper is not None else None
            ),
            "embedded_helper_size_bytes": (
                single_helper["size_bytes"] if single_helper is not None else None
            ),
            "embedded_helper_count": len(helpers),
            "embedded_helpers": helpers,
            "embedded_helper_provenance_source": helper_source,
            "standalone": True,
            "runtime_network_required": False,
            "system_tex_required": False,
            "public_release_mode": args.public_release,
            "license_evidence_included": include_license_evidence,
            "release_license_complete": license_complete,
            "license_audit_source_sha": (
                license_status.get("source_sha") if license_status else None
            ),
            "packaged_license_file_count": len(packaged_license_files),
            "net_install_license_file_count": 0,
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
