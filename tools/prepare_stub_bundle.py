#!/usr/bin/env python3
"""Create a tiny deterministic compile-only bundle for fast Rust CI.

This artifact is never a release bundle and is never used for engine runtime
qualification. It exists solely so `include_bytes!` and the native dependency
graph can be compiled without downloading the full Tectonic resource bundle on
every source push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZERO_DIGEST = "0" * 64


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("bundle/generated/texpdf-bundle.zip")
    )
    parser.add_argument(
        "--info", type=Path, default=Path("bundle/generated/bundle-info.json")
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=False,
            strict_timestamps=True,
        ) as archive:
            archive.writestr(zip_info("SHA256SUM"), ZERO_DIGEST)
        os.replace(temporary, args.output)
        payload = {
            "schema_version": 1,
            "bundle_name": "texpdf-compile-only-stub",
            "bundle_version": "stub",
            "transform_version": "stub-1",
            "source_url": "",
            "index_url": "",
            "source_sha256": ZERO_DIGEST,
            "index_sha256": ZERO_DIGEST,
            "tectonic_bundle_digest": ZERO_DIGEST,
            "zip_sha256": sha256_file(args.output),
            "file_count": 1,
            "zip_size_bytes": args.output.stat().st_size,
            "qualification": "compile-only; not a runtime or release bundle",
        }
        write_json_atomic(args.info, payload)
        print(
            "TEXPDF_STUB_BUNDLE_READY "
            f"zip_bytes={payload['zip_size_bytes']} zip_sha256={payload['zip_sha256']}",
            flush=True,
        )
        return 0
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        print(f"TEXPDF_STUB_BUNDLE_ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
