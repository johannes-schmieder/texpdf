#!/usr/bin/env python3
"""Create the deterministic ZIP bundle embedded by texpdf.

The Tectonic v33 web bundle is an indexed tar: the gzip-compressed index maps
logical resource names to byte ranges in the raw tar stream. This script
reconstructs those resources into a flat deterministic ZIP understood by
tectonic_bundles::zip::ZipBundle.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile

LOCK_VALUE_RE = re.compile(r'^([A-Za-z0-9_]+)\s*=\s*"([^"]*)"\s*$')
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOWNLOAD_CHUNK = 1024 * 1024
COPY_CHUNK = 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class BundleError(RuntimeError):
    """A deterministic bundle preparation failure."""


def parse_lock(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    in_bundle = False
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_bundle = line == "[bundle]"
            continue
        if not in_bundle:
            continue
        match = LOCK_VALUE_RE.match(line)
        if match is None:
            raise BundleError(f"{path}:{line_number}: unsupported lock syntax")
        values[match.group(1)] = match.group(2)

    required = {"name", "version", "source_url", "index_url", "transform_version"}
    missing = sorted(required.difference(values))
    if missing:
        raise BundleError(f"bundle lock is missing: {', '.join(missing)}")
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(DOWNLOAD_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "texpdf-bundle-builder/0.1"})
    try:
        with contextlib.closing(urllib.request.urlopen(request, timeout=120)) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output, length=DOWNLOAD_CHUNK)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def obtain(url: str, destination: Path, expected_sha256: str) -> str:
    if expected_sha256 and not SHA256_RE.fullmatch(expected_sha256):
        raise BundleError(f"invalid locked SHA-256 for {destination.name}")

    if destination.exists():
        actual = sha256_file(destination)
        if not expected_sha256 or actual == expected_sha256:
            return actual
        destination.unlink()

    print(f"TEXPDF_BUNDLE_DOWNLOAD url={url}", flush=True)
    download(url, destination)
    actual = sha256_file(destination)
    if expected_sha256 and actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise BundleError(
            f"checksum mismatch for {url}: expected {expected_sha256}, got {actual}"
        )
    return actual


def parse_index(path: Path, source_size: int) -> list[tuple[str, int, int]]:
    entries: dict[str, tuple[int, int]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, 1):
            parts = raw.split()
            if len(parts) != 3:
                raise BundleError(f"malformed index line {line_number}")
            name, offset_text, length_text = parts
            try:
                offset = int(offset_text)
                length = int(length_text)
            except ValueError as exc:
                raise BundleError(f"invalid index numbers on line {line_number}") from exc
            if not name or name.startswith("/") or "\\" in name:
                raise BundleError(f"unsafe bundle name on line {line_number}: {name!r}")
            if any(part in {"", ".", ".."} for part in name.split("/")):
                raise BundleError(f"unsafe bundle path on line {line_number}: {name!r}")
            if offset < 0 or length < 0 or offset + length > source_size:
                raise BundleError(f"out-of-range entry on line {line_number}: {name!r}")
            entries[name] = (offset, length)
    if "SHA256SUM" not in entries:
        raise BundleError("source bundle index has no SHA256SUM entry")
    return [(name, *entries[name]) for name in sorted(entries)]


def read_range(source, offset: int, length: int) -> bytes:
    source.seek(offset)
    remaining = length
    pieces: list[bytes] = []
    while remaining:
        chunk = source.read(min(COPY_CHUNK, remaining))
        if not chunk:
            raise BundleError("unexpected end of source bundle")
        pieces.append(chunk)
        remaining -= len(chunk)
    return b"".join(pieces)


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_zip(source_path: Path, entries: list[tuple[str, int, int]], output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    bundle_digest = ""
    try:
        with source_path.open("rb") as source:
            with zipfile.ZipFile(
                temporary,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
                allowZip64=True,
                strict_timestamps=True,
            ) as archive:
                for name, offset, length in entries:
                    data = read_range(source, offset, length)
                    if name == "SHA256SUM":
                        digest_text = data[:64].decode("ascii", errors="strict").lower()
                        if not SHA256_RE.fullmatch(digest_text):
                            raise BundleError("source SHA256SUM entry is invalid")
                        bundle_digest = digest_text
                    archive.writestr(zip_info(name), data, compress_type=zipfile.ZIP_DEFLATED)
        if not bundle_digest:
            raise BundleError("bundle digest was not captured")
        os.replace(temporary, output)
        return bundle_digest
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=Path("bundle/bundle.lock.toml"))
    parser.add_argument(
        "--output", type=Path, default=Path("bundle/generated/texpdf-bundle.zip")
    )
    parser.add_argument(
        "--info", type=Path, default=Path("bundle/generated/bundle-info.json")
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "TEXPDF_BUNDLE_CACHE",
                str(Path(tempfile.gettempdir()) / "texpdf-bundle-cache"),
            )
        ),
    )
    args = parser.parse_args()

    try:
        lock = parse_lock(args.lock)
        cache = args.cache_dir.expanduser().resolve()
        cache.mkdir(parents=True, exist_ok=True)
        raw_path = cache / f"{lock['name']}.tar"
        index_path = cache / f"{lock['name']}.tar.index.gz"
        source_sha = obtain(lock["source_url"], raw_path, lock.get("source_sha256", ""))
        index_sha = obtain(lock["index_url"], index_path, lock.get("index_sha256", ""))
        cache_key = f"v{lock['transform_version']}-{source_sha[:16]}-{index_sha[:16]}"
        cached_zip = cache / f"{lock['name']}-{cache_key}.zip"
        cached_info = cache / f"{lock['name']}-{cache_key}.json"

        if cached_zip.exists() and cached_info.exists():
            info = json.loads(cached_info.read_text(encoding="utf-8"))
            if sha256_file(cached_zip) != info.get("zip_sha256"):
                cached_zip.unlink(missing_ok=True)
                cached_info.unlink(missing_ok=True)

        if not cached_zip.exists():
            entries = parse_index(index_path, raw_path.stat().st_size)
            bundle_digest = build_zip(raw_path, entries, cached_zip)
            info = {
                "schema_version": 1,
                "bundle_name": lock["name"],
                "bundle_version": lock["version"],
                "transform_version": lock["transform_version"],
                "source_url": lock["source_url"],
                "index_url": lock["index_url"],
                "source_sha256": source_sha,
                "index_sha256": index_sha,
                "tectonic_bundle_digest": bundle_digest,
                "zip_sha256": sha256_file(cached_zip),
                "file_count": len(entries),
                "zip_size_bytes": cached_zip.stat().st_size,
            }
            write_json_atomic(cached_info, info)
        else:
            info = json.loads(cached_info.read_text(encoding="utf-8"))

        copy_atomic(cached_zip, args.output)
        write_json_atomic(args.info, info)
        locked = bool(lock.get("source_sha256") and lock.get("index_sha256"))
        print(
            "TEXPDF_BUNDLE_READY "
            f"files={info['file_count']} zip_bytes={info['zip_size_bytes']} "
            f"source_sha256={info['source_sha256']} index_sha256={info['index_sha256']} "
            f"zip_sha256={info['zip_sha256']} locked={str(locked).lower()}",
            flush=True,
        )
        return 0
    except (BundleError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TEXPDF_BUNDLE_ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
