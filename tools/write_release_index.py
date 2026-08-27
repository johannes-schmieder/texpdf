#!/usr/bin/env python3
"""Validate release archives and write one deterministic manifest/checksum index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PLATFORMS = {
    "macos": ("universal2-apple-darwin", "_texpdf_plugin_macosx.plugin"),
    "linux": ("x86_64-unknown-linux-gnu", "_texpdf_plugin_unix.plugin"),
    "windows": ("x86_64-pc-windows-msvc", "_texpdf_plugin_windows.plugin"),
}
SSC_PLUGIN = "_texpdf_plugin.plugin"
SSC_G_LINES = [
    "g LINUX64 _texpdf_plugin_unix.plugin _texpdf_plugin.plugin",
    "g MACINTEL64 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
    "g OSX.X8664 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
    "g MACARM64 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
    "g OSX.ARM64 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
    "g WIN64 _texpdf_plugin_windows.plugin _texpdf_plugin.plugin",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return value


def parse_asset(value: str) -> tuple[str, Path, Path]:
    parts = value.split("=", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError("--asset must be LABEL=ARCHIVE=MANIFEST")
    return parts[0], Path(parts[1]), Path(parts[2])


def build_index(args: argparse.Namespace) -> dict[str, object]:
    if not SHA_RE.fullmatch(args.source_sha):
        raise ValueError("--source-sha must be a lowercase 40-character Git SHA")
    parsed = [parse_asset(value) for value in args.asset]
    by_label = {label: (archive, manifest) for label, archive, manifest in parsed}
    expected = set(PLATFORMS) | {"ssc"}
    if len(parsed) != len(by_label) or set(by_label) != expected:
        raise ValueError(f"--asset labels must be exactly {sorted(expected)}")

    records: dict[str, object] = {}
    basenames: dict[str, str] = {}
    for label in sorted(by_label):
        archive, manifest_path = by_label[label]
        manifest = read_json(manifest_path)
        if not archive.is_file():
            raise ValueError(f"missing {label} archive: {archive}")
        folded = archive.name.casefold()
        if folded in basenames:
            raise ValueError(
                f"case-insensitive asset collision: {basenames[folded]} and {archive.name}"
            )
        basenames[folded] = archive.name
        digest = sha256(archive)
        size = archive.stat().st_size
        if label == "ssc":
            if (
                manifest.get("package_version") != args.version
                or manifest.get("release_kind") != args.release_kind
                or manifest.get("source_sha") != args.source_sha
                or manifest.get("archive_sha256") != digest
                or manifest.get("archive_size_bytes") != size
                or manifest.get("submitted_pkg_file") is not True
                or manifest.get("ssc_plugin_destination") != SSC_PLUGIN
                or manifest.get("ssc_platform_selection") != SSC_G_LINES
            ):
                raise ValueError("SSC archive or manifest does not match the release")
            distribution = "ssc-combined"
        else:
            target, plugin = PLATFORMS[label]
            if (
                manifest.get("package_version") != args.version
                or manifest.get("target") != target
                or manifest.get("installed_plugin") != plugin
                or manifest.get("public_release_mode") is not True
                or manifest.get("release_license_complete") is not True
                or manifest.get("license_audit_source_sha") != args.source_sha
                or manifest.get("package_zip_sha256") != digest
                or manifest.get("package_zip_size_bytes") != size
            ):
                raise ValueError(f"{label} archive or manifest does not match the release")
            distribution = target
        records[label] = {
            "archive": archive.name,
            "sha256": digest,
            "size_bytes": size,
            "distribution": distribution,
        }

    return {
        "schema_version": 1,
        "package": "texpdf",
        "version": args.version,
        "release_kind": args.release_kind,
        "source_sha": args.source_sha,
        "artifacts": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--release-kind",
        choices=("public_release_candidate", "final_release"),
        required=True,
    )
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_index(args)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.checksums.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        args.checksums.write_text(
            "".join(
                f"{record['sha256']}  {record['archive']}\n"
                for record in result["artifacts"].values()
            ),
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_RELEASE_INDEX_ERROR {error}", file=sys.stderr)
        return 2
    print(
        "TEXPDF_RELEASE_INDEX_READY "
        f"version={result['version']} source={result['source_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
