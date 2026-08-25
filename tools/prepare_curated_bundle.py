#!/usr/bin/env python3
"""Build the tested offline texpdf ZIP from indexed-tar byte ranges."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import fnmatch
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
CHUNK = 1024 * 1024
MAX_RANGE_ATTEMPTS = 12


class BundleError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def parse_lock(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    active = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            active = line == "[bundle]"
            continue
        if not active:
            continue
        key, separator, raw_value = line.partition("=")
        if not separator:
            raise BundleError(f"malformed bundle lock line: {raw!r}")
        value = raw_value.strip()
        if len(value) < 2 or value[0] != '"' or value[-1] != '"':
            raise BundleError(f"unsupported bundle lock value: {raw!r}")
        values[key.strip()] = value[1:-1]
    for key in (
        "name",
        "version",
        "source_url",
        "index_url",
        "transform_version",
        "selection_name",
        "selection_version",
    ):
        if key not in values:
            raise BundleError(f"bundle lock is missing {key}")
    return values


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "texpdf-bundle-builder/0.1",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            expected = response.headers.get("Content-Length")
            with temporary.open("wb") as output:
                while chunk := response.read(CHUNK):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
        if expected is not None and temporary.stat().st_size != int(expected):
            raise BundleError(
                f"incomplete download: expected {expected}, got {temporary.stat().st_size}"
            )
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_index(path: Path) -> dict[str, tuple[int, int]]:
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
            except ValueError as error:
                raise BundleError(f"invalid index line {line_number}") from error
            if offset < 0 or length < 0:
                raise BundleError(f"negative index range on line {line_number}")
            entries[name] = (offset, length)
    if "SHA256SUM" not in entries:
        raise BundleError("bundle index does not contain SHA256SUM")
    return entries


def retry_delay(error: Exception, attempt: int) -> float:
    if isinstance(error, urllib.error.HTTPError):
        retry_after = error.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(60.0, max(1.0, float(retry_after)))
            except ValueError:
                pass
    return min(30.0, 1.5 * attempt)


def fetch_range(url: str, name: str, offset: int, length: int) -> bytes:
    if length == 0:
        return b""
    end = offset + length - 1
    last_error: Exception | None = None
    for attempt in range(1, MAX_RANGE_ATTEMPTS + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "texpdf-bundle-builder/0.1",
                "Accept-Encoding": "identity",
                "Range": f"bytes={offset}-{end}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status = getattr(response, "status", None)
                data = response.read()
                content_range = response.headers.get("Content-Range", "")
            if status != 206:
                raise BundleError(f"range request for {name} returned HTTP {status}")
            if not content_range.startswith(f"bytes {offset}-{end}/"):
                raise BundleError(f"invalid Content-Range for {name}: {content_range!r}")
            if len(data) != length:
                raise BundleError(
                    f"short range response for {name}: expected {length}, got {len(data)}"
                )
            return data
        except Exception as error:
            last_error = error
            if attempt < MAX_RANGE_ATTEMPTS:
                time.sleep(retry_delay(error, attempt))
    raise BundleError(f"failed to fetch {name}: {last_error}")


def resource_cache_path(cache: Path, name: str, offset: int, length: int) -> Path:
    key = hashlib.sha256(f"{name}\0{offset}\0{length}".encode()).hexdigest()
    return cache / "resources" / key


def safe_resource_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if (
        not name
        or "\\" in name
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise BundleError(f"unsafe logical bundle path: {name!r}")
    return root.joinpath(*relative.parts)


def write_cache(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".part")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def read_source_range(source_tar: Path, offset: int, length: int) -> bytes:
    with source_tar.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(length)
    if len(data) != length:
        raise BundleError(
            f"short local source range: expected {length}, got {len(data)}"
        )
    return data


def obtain_resource(
    source_url: str,
    cache: Path,
    resource_dir: Path | None,
    source_tar: Path | None,
    name: str,
    offset: int,
    length: int,
    expected_sha256: str | None,
) -> tuple[str, bytes, str]:
    path = resource_cache_path(cache, name, offset, length)

    candidates: list[Path] = []
    if resource_dir is not None:
        candidates.append(safe_resource_path(resource_dir, name))
    candidates.append(path)

    for candidate in candidates:
        if not candidate.is_file():
            continue
        if candidate.stat().st_size != length:
            if candidate == path:
                candidate.unlink()
                continue
            raise BundleError(
                f"resolved resource length mismatch for {name}: "
                f"expected {length}, got {candidate.stat().st_size}"
            )
        data = candidate.read_bytes()
        digest = sha256_bytes(data)
        if expected_sha256 is not None and digest != expected_sha256:
            if candidate == path:
                candidate.unlink()
                continue
            raise BundleError(
                f"resolved resource checksum mismatch for {name}: "
                f"expected {expected_sha256}, got {digest}"
            )
        if candidate != path:
            write_cache(path, data)
        return name, data, digest

    if source_tar is not None:
        data = read_source_range(source_tar, offset, length)
    else:
        data = fetch_range(source_url, name, offset, length)
    digest = sha256_bytes(data)
    if expected_sha256 is not None and digest != expected_sha256:
        raise BundleError(
            f"resource checksum mismatch for {name}: expected {expected_sha256}, got {digest}"
        )
    write_cache(path, data)
    return name, data, digest


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def load_resource_policy(path: Path) -> dict[str, object]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BundleError(f"cannot read resource policy {path}: {error}") from error
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise BundleError("resource policy must be a schema-version-1 JSON object")
    exclusions = policy.get("exclude")
    replacements = policy.get("replacements")
    if not isinstance(exclusions, list) or not all(
        isinstance(value, str) and value for value in exclusions
    ):
        raise BundleError("resource policy exclude must be a list of patterns")
    if not isinstance(replacements, dict):
        raise BundleError("resource policy replacements must be an object")
    for name, item in replacements.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise BundleError("resource policy replacement is malformed")
        required = (item.get("source"), item.get("origin"), item.get("license"))
        if not all(isinstance(value, str) and value for value in required):
            raise BundleError(
                f"resource policy replacement {name!r} needs source, origin, and license"
            )
    return policy


def policy_excludes(name: str, policy: dict[str, object]) -> bool:
    return any(
        fnmatch.fnmatchcase(name, pattern)
        for pattern in policy["exclude"]  # type: ignore[index]
    )


def replacement_resources(
    selected_names: set[str], policy: dict[str, object], repository_root: Path
) -> dict[str, tuple[bytes, dict[str, str]]]:
    result: dict[str, tuple[bytes, dict[str, str]]] = {}
    replacements = policy["replacements"]
    assert isinstance(replacements, dict)
    for name, raw in replacements.items():
        if name not in selected_names:
            continue
        assert isinstance(raw, dict)
        source = (repository_root / str(raw["source"])).resolve()
        try:
            source.relative_to(repository_root)
        except ValueError as error:
            raise BundleError(f"replacement source escapes repository: {source}") from error
        if not source.is_file():
            raise BundleError(f"replacement source is absent: {source}")
        metadata = {
            "source": str(raw["source"]),
            "origin": str(raw["origin"]),
            "license": str(raw["license"]),
        }
        result[name] = (source.read_bytes(), metadata)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--trace", type=Path)
    source.add_argument("--manifest", type=Path)
    parser.add_argument("--write-manifest", type=Path)
    parser.add_argument("--resource-dir", type=Path)
    parser.add_argument("--source-tar", type=Path)
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
        default=Path(os.environ.get("TEXPDF_BUNDLE_CACHE", tempfile.gettempdir()))
        / "texpdf-curated-bundle-cache",
    )
    parser.add_argument(
        "--resource-policy",
        type=Path,
        default=Path("bundle/resource-policy.json"),
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    try:
        lock = parse_lock(args.lock)
        repository_root = Path.cwd().resolve()
        policy = load_resource_policy(args.resource_policy)
        cache = args.cache_dir.expanduser().resolve()
        resource_dir = (
            args.resource_dir.expanduser().resolve()
            if args.resource_dir is not None
            else None
        )
        source_tar = (
            args.source_tar.expanduser().resolve()
            if args.source_tar is not None
            else None
        )
        if source_tar is not None and not source_tar.is_file():
            raise BundleError(f"source tar does not exist: {source_tar}")

        index_path = cache / f"{lock['name']}.tar.index.gz"
        if not index_path.is_file():
            print(f"TEXPDF_BUNDLE_INDEX_DOWNLOAD url={lock['index_url']}", flush=True)
            download(lock["index_url"], index_path)
        index_sha = sha256_file(index_path)
        locked_index = lock.get("index_sha256", "")
        if locked_index and index_sha != locked_index:
            raise BundleError(
                f"index checksum mismatch: expected {locked_index}, got {index_sha}"
            )
        index = parse_index(index_path)

        expected: dict[str, str | None] = {}
        selected_names: set[str] = set()
        manifest_generated: dict[str, dict[str, object]] = {}
        excluded_names: list[str] = []
        missing_from_index: list[str] = []
        if args.trace is not None:
            trace_names = sorted(
                {
                    line.strip()
                    for line in args.trace.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                }
            )
            for name in trace_names:
                if name == "SHA256SUM":
                    continue
                if policy_excludes(name, policy):
                    excluded_names.append(name)
                    continue
                if name in index:
                    expected[name] = None
                    selected_names.add(name)
                else:
                    missing_from_index.append(name)
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            if manifest.get("index_sha256") != index_sha:
                raise BundleError("selection manifest was generated from a different index")
            if manifest.get("resource_policy_sha256") != sha256_file(args.resource_policy):
                raise BundleError("selection manifest was generated from a different resource policy")
            recorded_exclusions = manifest.get("excluded_resources", [])
            if not isinstance(recorded_exclusions, list) or not all(
                isinstance(name, str) and policy_excludes(name, policy)
                for name in recorded_exclusions
            ):
                raise BundleError("selection manifest has invalid policy exclusions")
            excluded_names.extend(recorded_exclusions)
            for item in manifest.get("resources", []):
                name = item["name"]
                if policy_excludes(name, policy):
                    raise BundleError(f"manifest contains policy-excluded resource: {name}")
                selected_names.add(name)
                if item.get("generated") is True:
                    manifest_generated[name] = item
                    continue
                if name not in index:
                    raise BundleError(f"manifest resource is absent from index: {name}")
                if list(index[name]) != [item["offset"], item["length"]]:
                    raise BundleError(f"manifest range changed for {name}")
                expected[name] = item["sha256"]

        if not selected_names:
            raise BundleError("resource selection is empty")

        replacements = replacement_resources(selected_names, policy, repository_root)
        if args.manifest is not None and set(manifest_generated) != set(replacements):
            raise BundleError("manifest generated-resource set differs from resource policy")
        for name, (data, metadata) in replacements.items():
            recorded = manifest_generated.get(name)
            if recorded is None:
                continue
            expected_metadata: dict[str, object] = {
                "source": metadata["source"],
                "origin": metadata["origin"],
                "license": metadata["license"],
                "length": len(data),
                "sha256": sha256_bytes(data),
            }
            for key, expected_value in expected_metadata.items():
                if recorded.get(key) != expected_value:
                    raise BundleError(
                        f"generated manifest metadata changed for {name}: {key}"
                    )
        for name in replacements:
            expected.pop(name, None)

        source_sha = lock.get("source_sha256", "")
        if source_sha and not SHA256_RE.fullmatch(source_sha):
            raise BundleError("locked source SHA-256 is malformed")
        if source_tar is not None:
            maximum_end = max(index[name][0] + index[name][1] for name in expected)
            if source_tar.stat().st_size < maximum_end:
                raise BundleError(
                    f"source tar is too short: need {maximum_end}, "
                    f"have {source_tar.stat().st_size}"
                )
            actual_source_sha = sha256_file(source_tar)
            if source_sha and actual_source_sha != source_sha:
                raise BundleError(
                    f"source tar checksum mismatch: expected {source_sha}, "
                    f"got {actual_source_sha}"
                )
            source_sha = actual_source_sha
            print(
                f"TEXPDF_CURATED_SOURCE_TAR_READY path={source_tar} "
                f"bytes={source_tar.stat().st_size} sha256={source_sha}",
                flush=True,
            )

        resources: dict[str, bytes] = {}
        resource_hashes: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(
                    obtain_resource,
                    lock["source_url"],
                    cache,
                    resource_dir,
                    source_tar,
                    name,
                    index[name][0],
                    index[name][1],
                    digest,
                ): name
                for name, digest in expected.items()
            }
            for future in as_completed(futures):
                name, data, digest = future.result()
                resources[name] = data
                resource_hashes[name] = digest
        for name, (data, _) in replacements.items():
            resources[name] = data
            resource_hashes[name] = sha256_bytes(data)

        digest_computer = hashlib.sha256()
        for name in sorted(resources):
            digest_computer.update(name.encode("utf-8"))
            digest_computer.update(b"\0")
            digest_computer.update(bytes.fromhex(resource_hashes[name]))
        bundle_digest = digest_computer.hexdigest()
        digest_bytes = (bundle_digest + "\n").encode("ascii")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary_zip = args.output.with_suffix(args.output.suffix + ".part")
        temporary_zip.unlink(missing_ok=True)
        with zipfile.ZipFile(
            temporary_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
            strict_timestamps=True,
        ) as archive:
            archive.writestr(zip_info("SHA256SUM"), digest_bytes)
            for name in sorted(resources):
                archive.writestr(zip_info(name), resources[name])
        os.replace(temporary_zip, args.output)

        manifest_payload = {
            "schema_version": 1,
            "bundle_name": lock["selection_name"],
            "bundle_version": lock["selection_version"],
            "source_url": lock["source_url"],
            "index_url": lock["index_url"],
            "source_sha256": source_sha,
            "index_sha256": index_sha,
            "missing_trace_names": missing_from_index,
            "resource_policy_sha256": sha256_file(args.resource_policy),
            "excluded_resources": sorted(excluded_names),
            "resources": [],
        }
        for name in sorted(resources):
            if name in replacements:
                _, metadata = replacements[name]
                manifest_payload["resources"].append(
                    {
                        "name": name,
                        "generated": True,
                        "length": len(resources[name]),
                        "sha256": resource_hashes[name],
                        **metadata,
                    }
                )
            else:
                manifest_payload["resources"].append(
                    {
                        "name": name,
                        "offset": index[name][0],
                        "length": index[name][1],
                        "sha256": resource_hashes[name],
                    }
                )
        info = {
            "schema_version": 1,
            "bundle_name": lock["selection_name"],
            "bundle_version": lock["selection_version"],
            "transform_version": "range-closure-v2-english-only",
            "source_sha256": source_sha,
            "index_sha256": index_sha,
            "tectonic_bundle_digest": bundle_digest,
            "zip_sha256": sha256_file(args.output),
            "file_count": len(resources) + 1,
            "zip_size_bytes": args.output.stat().st_size,
            "uncompressed_resource_bytes": sum(len(value) for value in resources.values())
            + len(digest_bytes),
            "missing_trace_names": missing_from_index,
            "excluded_resource_count": len(excluded_names),
            "resource_policy_sha256": sha256_file(args.resource_policy),
        }
        manifest_payload.update(
            {
                "file_count": len(resources),
                "bundle_file_count": info["file_count"],
                "bundle_zip_sha256": info["zip_sha256"],
                "bundle_content_digest": info["tectonic_bundle_digest"],
            }
        )
        if args.write_manifest is not None:
            atomic_json(args.write_manifest, manifest_payload)
        atomic_json(args.info, info)
        print(
            "TEXPDF_CURATED_BUNDLE_READY "
            f"files={info['file_count']} zip_bytes={info['zip_size_bytes']} "
            f"uncompressed_bytes={info['uncompressed_resource_bytes']} "
            f"index_sha256={index_sha} zip_sha256={info['zip_sha256']}",
            flush=True,
        )
        return 0
    except (BundleError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_CURATED_BUNDLE_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
