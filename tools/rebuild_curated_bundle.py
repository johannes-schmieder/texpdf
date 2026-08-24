#!/usr/bin/env python3
"""Rebuild the exact qualified curated bundle from its committed manifest.

This path is intended for release and cross-platform builders. It does not run
resource discovery: it reconstructs the already-qualified byte-range selection
and rejects any result whose size or SHA-256 differs from QUALIFICATION.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
import urllib.request
import zipfile

ZIP_TIME = (1980, 1, 1, 0, 0, 0)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NAME_KEYS = ("name", "path", "logical_name", "resource", "filename")
OFFSET_KEYS = ("offset", "start", "byte_offset")
LENGTH_KEYS = ("length", "size", "byte_length")
DIGEST_KEYS = ("sha256", "digest", "file_sha256")
ORIGIN_KEYS = ("origin", "source", "archive", "bundle")


class RebuildError(RuntimeError):
    """An exact curated-bundle reconstruction failure."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def first_string(value: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def first_int(value: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def normalize_name(name: str) -> str:
    value = name.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or ".." in value.split("/"):
        raise RebuildError(f"unsafe resource name: {name!r}")
    return value


def origin_text(value: dict[str, Any]) -> str:
    for key in ORIGIN_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            nested = first_string(
                candidate,
                ("name", "kind", "archive", "source", "url", "path"),
            )
            if nested:
                return nested
    return "source"


def candidate_record(value: dict[str, Any], fallback_name: str | None) -> dict[str, Any] | None:
    name = first_string(value, NAME_KEYS) or fallback_name
    length = first_int(value, LENGTH_KEYS)
    generated = value.get("generated") is True
    source = first_string(value, ("source",))
    offset = first_int(value, OFFSET_KEYS)
    nested_origin = value.get("origin") if isinstance(value.get("origin"), dict) else {}
    if offset is None and isinstance(nested_origin, dict):
        offset = first_int(nested_origin, OFFSET_KEYS)
    if length is None and isinstance(nested_origin, dict):
        length = first_int(nested_origin, LENGTH_KEYS)
    if not name or length is None:
        return None
    if generated and not source:
        raise RebuildError(f"generated resource {name!r} has no source")
    if not generated and offset is None:
        return None
    digest = first_string(value, DIGEST_KEYS)
    if digest is None and isinstance(nested_origin, dict):
        digest = first_string(nested_origin, DIGEST_KEYS)
    record = {
        "name": normalize_name(name),
        "offset": offset,
        "length": length,
        "sha256": (digest or "").lower(),
        "origin": origin_text(value),
        "generated": generated,
        "source": normalize_name(source) if source else None,
        "url": first_string(value, ("url", "source_url", "archive_url"))
        or (
            first_string(nested_origin, ("url", "source_url", "archive_url"))
            if isinstance(nested_origin, dict)
            else None
        ),
    }
    if generated and not SHA256_RE.fullmatch(record["sha256"]):
        raise RebuildError(f"generated resource {name!r} has no SHA-256")
    return record


def extract_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    collections: list[list[dict[str, Any]]] = []

    def rows(value: Any) -> list[dict[str, Any]]:
        result = []
        if isinstance(value, list):
            iterable = [(None, item) for item in value]
        elif isinstance(value, dict):
            iterable = list(value.items())
        else:
            return result
        for fallback, item in iterable:
            if not isinstance(item, dict):
                continue
            record = candidate_record(item, str(fallback) if fallback is not None else None)
            if record is not None:
                result.append(record)
        return result

    for key in ("selected", "selected_resources", "resources", "files", "entries"):
        found = rows(manifest.get(key))
        if found:
            collections.append(found)

    def visit(value: Any) -> None:
        found = rows(value)
        if found:
            collections.append(found)
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    if not collections:
        visit(manifest)
    if not collections:
        raise RebuildError("no reconstructable resource records found in manifest")
    selected = max(collections, key=len)
    deduplicated: dict[str, dict[str, Any]] = {}
    for record in selected:
        existing = deduplicated.get(record["name"])
        if existing is not None and existing != record:
            raise RebuildError(f"conflicting manifest records for {record['name']}")
        deduplicated[record["name"]] = record
    return [deduplicated[name] for name in sorted(deduplicated)]


def flatten_strings(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.extend(flatten_strings(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(flatten_strings(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        result.append((prefix.lower(), value))
    return result


def lock_values(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        section = ""
        values: list[tuple[str, str]] = []
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                if not section:
                    raise RebuildError(f"empty lock section on line {line_number}")
                continue
            key, separator, encoded = line.partition("=")
            if not separator or not section:
                raise RebuildError(f"malformed lock line {line_number}: {raw!r}")
            try:
                value = json.loads(encoded.strip())
            except json.JSONDecodeError as error:
                raise RebuildError(
                    f"lock line {line_number} requires a quoted string value"
                ) from error
            if not isinstance(value, str):
                raise RebuildError(
                    f"lock line {line_number} value must be a string"
                )
            values.append((f"{section}.{key.strip()}", value))
        if not values:
            raise RebuildError(f"bundle lock is empty: {path}")
        return values
    return flatten_strings(tomllib.loads(text))


def url_candidates(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in values
        if value.startswith(("https://", "http://"))
        and "index" not in key
    ]


def checksum_for_url(values: list[tuple[str, str]], url_key: str) -> str:
    prefix = url_key.rsplit(".", 1)[0] if "." in url_key else ""
    candidates = []
    for key, value in values:
        if not SHA256_RE.fullmatch(value.lower()):
            continue
        score = 0
        if prefix and key.startswith(prefix):
            score += 4
        for token in re.split(r"[.\[\]_\-]+", url_key):
            if token and token in key:
                score += 1
        if "index" in key:
            score -= 5
        candidates.append((score, key, value.lower()))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2] if candidates[0][0] > 0 else ""


def select_url(record: dict[str, Any], values: list[tuple[str, str]]) -> tuple[str, str]:
    if record.get("url"):
        return str(record["url"]), ""
    urls = url_candidates(values)
    if not urls:
        raise RebuildError("bundle lock contains no non-index source URLs")
    origin = str(record["origin"]).lower()
    wants_local = any(token in origin for token in ("local", "tlextras", "extra"))
    ranked = []
    for key, url in urls:
        key_text = f"{key} {url}".lower()
        is_local = any(token in key_text for token in ("local", "tlextras", "extra"))
        score = 0
        if is_local == wants_local:
            score += 10
        for token in re.split(r"[^a-z0-9]+", origin):
            if len(token) >= 4 and token in key_text:
                score += 2
        if "source" in key and not wants_local:
            score += 1
        ranked.append((score, key, url))
    ranked.sort(reverse=True)
    _, key, url = ranked[0]
    return url, checksum_for_url(values, key)


def download(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if not expected_sha256 or sha256_file(destination) == expected_sha256:
            return
        destination.unlink()
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "texpdf-exact-bundle-rebuilder/0.1"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        with temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    actual = sha256_file(temporary)
    if expected_sha256 and actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RebuildError(
            f"archive checksum mismatch for {url}: expected {expected_sha256}, got {actual}"
        )
    os.replace(temporary, destination)


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def rebuild(
    records: list[dict[str, Any]],
    lock: list[tuple[str, str]],
    qualification: dict[str, Any],
    cache: Path,
    output: Path,
    source_root: Path,
) -> None:
    archives: dict[str, Path] = {}
    handles: dict[str, Any] = {}
    data_by_name: dict[str, bytes] = {}
    try:
        for record in records:
            name = record["name"]
            if name == "SHA256SUM":
                continue
            if record["generated"]:
                root = source_root.resolve()
                source = (root / str(record["source"])).resolve()
                if source != root and root not in source.parents:
                    raise RebuildError(f"generated resource source escapes root: {name}")
                if not source.is_file():
                    raise RebuildError(f"generated resource source is missing: {source}")
                data = source.read_bytes()
                if len(data) != record["length"]:
                    raise RebuildError(f"generated resource length mismatch for {name}")
                if sha256_bytes(data) != record["sha256"]:
                    raise RebuildError(f"generated resource checksum mismatch for {name}")
                data_by_name[name] = data
                continue
            url, expected_archive_sha = select_url(record, lock)
            if url not in archives:
                suffix = Path(urllib.request.urlparse(url).path).name or "archive.bin"
                archive_path = cache / f"{sha256_bytes(url.encode())[:16]}-{suffix}"
                download(url, archive_path, expected_archive_sha)
                archives[url] = archive_path
                handles[url] = archive_path.open("rb")
            stream = handles[url]
            stream.seek(record["offset"])
            data = stream.read(record["length"])
            if len(data) != record["length"]:
                raise RebuildError(f"short archive read for {name}")
            expected_file_sha = record["sha256"]
            if expected_file_sha and sha256_bytes(data) != expected_file_sha:
                raise RebuildError(f"resource checksum mismatch for {name}")
            data_by_name[name] = data
    finally:
        for stream in handles.values():
            stream.close()

    bundle = qualification["bundle"]
    data_by_name["SHA256SUM"] = (bundle["content_digest"] + "\n").encode("ascii")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
        strict_timestamps=True,
    ) as archive:
        ordered_names = ["SHA256SUM"] + sorted(
            name for name in data_by_name if name != "SHA256SUM"
        )
        for name in ordered_names:
            archive.writestr(zip_info(name), data_by_name[name])
    os.replace(temporary, output)

    expected_count = int(bundle["file_count"])
    expected_size = int(bundle["zip_size_bytes"])
    expected_sha = str(bundle["zip_sha256"])
    with zipfile.ZipFile(output) as archive:
        actual_count = len(archive.namelist())
    actual_size = output.stat().st_size
    actual_sha = sha256_file(output)
    errors = []
    if actual_count != expected_count:
        errors.append(f"file count {actual_count} != {expected_count}")
    if actual_size != expected_size:
        errors.append(f"size {actual_size} != {expected_size}")
    if actual_sha != expected_sha:
        errors.append(f"SHA-256 {actual_sha} != {expected_sha}")
    if errors:
        output.unlink(missing_ok=True)
        raise RebuildError("exact bundle reconstruction failed: " + "; ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("bundle/curated-manifest.json"))
    parser.add_argument("--lock", type=Path, default=Path("bundle/bundle.lock.toml"))
    parser.add_argument("--qualification", type=Path, default=Path("bundle/QUALIFICATION.json"))
    parser.add_argument("--output", type=Path, default=Path("bundle/generated/texpdf-bundle.zip"))
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("."),
        help="repository root used for project-generated manifest resources",
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
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        qualification = json.loads(args.qualification.read_text(encoding="utf-8"))
        records = extract_records(manifest)
        rebuild(
            records,
            lock_values(args.lock),
            qualification,
            args.cache_dir,
            args.output,
            args.source_root,
        )
        info = {
            "schema_version": 1,
            "bundle_name": qualification["bundle"]["name"],
            "bundle_version": qualification["bundle"]["version"],
            "tectonic_bundle_digest": qualification["bundle"]["content_digest"],
            "zip_sha256": qualification["bundle"]["zip_sha256"],
            "file_count": qualification["bundle"]["file_count"],
            "zip_size_bytes": qualification["bundle"]["zip_size_bytes"],
            "rebuild_mode": "exact-qualified-manifest",
        }
        info_path = args.output.parent / "bundle-info.json"
        info_path.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "TEXPDF_EXACT_BUNDLE_REBUILT "
            f"files={info['file_count']} zip_bytes={info['zip_size_bytes']} "
            f"zip_sha256={info['zip_sha256']}"
        )
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, RebuildError) as error:
        print(f"TEXPDF_EXACT_BUNDLE_ERROR {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
