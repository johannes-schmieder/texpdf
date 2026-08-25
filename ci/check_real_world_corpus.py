#!/usr/bin/env python3
"""Validate the versioned real-world TeX compatibility corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/fixtures/real-world/manifest.json"
DEFAULT_STATA = ROOT / "ci/stata_real_world_corpus.do"
STATA_FIXTURE_RE = re.compile(
    r"^\s*\*\s*CORPUS_FIXTURE\s+(\S+)\s+(\S+)\s*$", re.MULTILINE
)
MACHINE_PATH_RE = re.compile(
    r"(?:/Users/|/home/|/projectnb/|Dropbox(?: \(Personal\))?|[A-Za-z]:[\\/])"
)
TEXT_SUFFIXES = {".bib", ".do", ".md", ".tex", ".txt"}
DIAGNOSTIC_KINDS = {"note", "warning", "error", "log"}


class CorpusError(RuntimeError):
    """The corpus contract is malformed or incomplete."""


def safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise CorpusError(f"{label} must be a nonempty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise CorpusError(f"{label} is unsafe: {value!r}")
    return path


def resolve_file(root: Path, value: object, label: str) -> Path:
    relative = safe_relative(value, label)
    path = root.joinpath(*relative.parts)
    if path.is_symlink():
        raise CorpusError(f"{label} may not be a symlink: {relative}")
    if not path.is_file():
        raise CorpusError(f"{label} is missing: {relative}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise CorpusError(f"{label} escapes the corpus: {relative}") from error
    return path


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusError(f"cannot read manifest {path}: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise CorpusError("manifest must be a schema-version-1 JSON object")
    fixtures = value.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise CorpusError("manifest fixtures must be a nonempty list")
    return value


def validate_manifest(manifest_path: Path, stata_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    root = manifest_path.parent.resolve()
    fixtures = manifest["fixtures"]
    engine_diagnostics = manifest.get("permitted_engine_diagnostics")
    if not isinstance(engine_diagnostics, list) or not engine_diagnostics:
        raise CorpusError("manifest must explicitly permit expected engine notes")
    for diagnostic in engine_diagnostics:
        if not isinstance(diagnostic, dict) or diagnostic.get("kind") != "note":
            raise CorpusError("common engine diagnostics may permit notes only")
        contains = diagnostic.get("contains")
        if not isinstance(contains, str) or not contains:
            raise CorpusError("common engine diagnostic needs a contains value")
    fixture_ids: set[str] = set()
    manifest_stata: dict[str, str] = {}
    managed_files: set[Path] = {manifest_path.resolve()}

    for number, fixture in enumerate(fixtures, 1):
        if not isinstance(fixture, dict):
            raise CorpusError(f"fixture {number} is not an object")
        identifier = fixture.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9-]+", identifier):
            raise CorpusError(f"fixture {number} has an invalid id")
        if identifier in fixture_ids:
            raise CorpusError(f"duplicate fixture id: {identifier}")
        fixture_ids.add(identifier)

        entrypoint = resolve_file(root, fixture.get("entrypoint"), f"{identifier} entrypoint")
        if entrypoint.suffix != ".tex":
            raise CorpusError(f"{identifier} entrypoint must be a .tex file")
        managed_files.add(entrypoint.resolve())
        manifest_stata[identifier] = str(
            safe_relative(fixture["entrypoint"], f"{identifier} entrypoint")
        )

        assets = fixture.get("assets")
        if not isinstance(assets, list) or not assets:
            raise CorpusError(f"{identifier} assets must be a nonempty list")
        asset_names: set[str] = set()
        for asset_number, asset in enumerate(assets, 1):
            relative = safe_relative(asset, f"{identifier} asset {asset_number}")
            encoded = str(relative)
            if encoded in asset_names:
                raise CorpusError(f"{identifier} lists duplicate asset {encoded}")
            asset_names.add(encoded)
            managed_files.add(
                resolve_file(root, encoded, f"{identifier} asset {asset_number}").resolve()
            )

        capabilities = fixture.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities or not all(
            isinstance(value, str) and value for value in capabilities
        ):
            raise CorpusError(f"{identifier} capabilities must be nonempty strings")

        provenance = fixture.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("kind") != "synthetic-derivative":
            raise CorpusError(f"{identifier} provenance must identify a synthetic derivative")
        if not isinstance(provenance.get("description"), str) or not provenance["description"]:
            raise CorpusError(f"{identifier} provenance needs a description")

        permitted = fixture.get("permitted_diagnostics")
        if not isinstance(permitted, list):
            raise CorpusError(f"{identifier} permitted_diagnostics must be a list")
        for diagnostic in permitted:
            if not isinstance(diagnostic, dict):
                raise CorpusError(f"{identifier} has a malformed permitted diagnostic")
            if diagnostic.get("kind") not in DIAGNOSTIC_KINDS:
                raise CorpusError(f"{identifier} has an invalid diagnostic kind")
            contains = diagnostic.get("contains")
            if not isinstance(contains, str) or not contains:
                raise CorpusError(f"{identifier} diagnostic needs a nonempty contains value")
        if identifier != "latexlog-legacy" and permitted:
            raise CorpusError(f"{identifier} must compile without permitted diagnostics")
        if identifier == "latexlog-legacy" and any(
            diagnostic.get("kind") != "warning" for diagnostic in permitted
        ):
            raise CorpusError("the legacy fixture may permit only warnings")

        contract = fixture.get("generator_contract")
        if contract is not None:
            if identifier != "latexlog-current" or not isinstance(contract, dict):
                raise CorpusError(f"unexpected generator contract on {identifier}")
            script = resolve_file(root, contract.get("script"), "latexlog generator script")
            managed_files.add(script.resolve())
            digest = contract.get("latexlog_ado_sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise CorpusError("latexlog generator hash must be lowercase SHA-256")
            if contract.get("normalized_comment") != "% LATEXLOG GENERATED TIMESTAMP":
                raise CorpusError("latexlog normalized comment changed unexpectedly")

    try:
        stata_text = stata_path.read_text(encoding="utf-8")
    except OSError as error:
        raise CorpusError(f"cannot read Stata corpus runner: {error}") from error
    stata_fixtures = dict(STATA_FIXTURE_RE.findall(stata_text))
    if len(stata_fixtures) != len(STATA_FIXTURE_RE.findall(stata_text)):
        raise CorpusError("Stata corpus runner contains duplicate fixture ids")
    if stata_fixtures != manifest_stata:
        raise CorpusError(
            "Stata fixture list is not synchronized with manifest: "
            f"manifest={manifest_stata!r} stata={stata_fixtures!r}"
        )

    for path in sorted(managed_files):
        if path.suffix.lower() not in TEXT_SUFFIXES and path != manifest_path.resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        match = MACHINE_PATH_RE.search(text)
        if match:
            raise CorpusError(f"machine-specific path in {path.relative_to(root)}: {match.group(0)}")

    return {
        "fixture_count": len(fixtures),
        "asset_count": sum(len(fixture["assets"]) for fixture in fixtures),
        "fixture_ids": sorted(fixture_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--stata-runner", type=Path, default=DEFAULT_STATA)
    args = parser.parse_args()
    try:
        result = validate_manifest(args.manifest.resolve(), args.stata_runner.resolve())
    except (CorpusError, OSError, UnicodeError) as error:
        print(f"TEXPDF_REAL_WORLD_CORPUS_ERROR {error}", file=sys.stderr)
        return 2
    print(
        "TEXPDF_REAL_WORLD_CORPUS_VALID "
        f"fixtures={result['fixture_count']} assets={result['asset_count']} "
        f"ids={','.join(result['fixture_ids'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
