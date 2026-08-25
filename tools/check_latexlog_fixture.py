#!/usr/bin/env python3
"""Regenerate the current latexlog fixture without mutating its source checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "tests/fixtures/real-world"
MANIFEST = CORPUS_ROOT / "manifest.json"
FIXTURE_ROOT = CORPUS_ROOT / "latexlog-current"
TIMESTAMP_RE = re.compile(r"^%\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s*$")


class ContractError(RuntimeError):
    """The latexlog regeneration contract failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def current_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fixtures = [item for item in manifest["fixtures"] if item["id"] == "latexlog-current"]
    if len(fixtures) != 1:
        raise ContractError("manifest must contain exactly one latexlog-current fixture")
    fixture = fixtures[0]
    contract = fixture.get("generator_contract")
    if not isinstance(contract, dict):
        raise ContractError("latexlog-current generator contract is missing")
    return fixture, contract


def normalize_tex(text: str, replacement: str) -> str:
    lines = text.splitlines()
    if not lines or not TIMESTAMP_RE.fullmatch(lines[0]):
        raise ContractError("generated TeX has no recognizable latexlog timestamp comment")
    lines[0] = replacement
    return "\n".join(lines) + "\n"


def validate_asset(path: Path) -> None:
    data = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        valid = data.startswith(b"%PDF-") and len(data) > 1_000
    elif path.suffix.lower() == ".png":
        valid = data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 500
    else:
        raise ContractError(f"unexpected generated asset type: {path.name}")
    if not valid:
        raise ContractError(f"generated asset is invalid or trivial: {path}")


def install_asset(source: Path, destination: Path, ghostscript_bin: Path | None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() != ".pdf":
        shutil.copyfile(source, destination)
        return
    if ghostscript_bin is None or not ghostscript_bin.is_file():
        raise ContractError(
            "updating PDF fixtures requires Ghostscript via --ghostscript-bin or PATH"
        )
    temporary = destination.with_suffix(".normalized.pdf")
    process = subprocess.run(
        [
            str(ghostscript_bin),
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.3",
            f"-sOutputFile={temporary}",
            str(source),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise ContractError(
            f"Ghostscript normalization failed: {process.stdout}{process.stderr}"
        )
    validate_asset(temporary)
    os.replace(temporary, destination)


def run(
    stata_bin: Path,
    latexlog_dir: Path,
    update: bool,
    ghostscript_bin: Path | None = None,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    fixture, contract = current_contract()
    ado = latexlog_dir / "latexlog.ado"
    if not ado.is_file():
        raise ContractError(f"latexlog.ado is absent: {ado}")
    expected_hash = str(contract["latexlog_ado_sha256"])
    actual_hash = sha256_file(ado)
    if actual_hash != expected_hash:
        raise ContractError(
            f"latexlog.ado hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    if not stata_bin.is_file():
        raise ContractError(f"Stata executable is absent: {stata_bin}")

    with tempfile.TemporaryDirectory(prefix="texpdf-latexlog-contract-") as temporary:
        work = Path(temporary)
        output = work / "output"
        output.mkdir()
        environment = os.environ.copy()
        environment["LATEXLOG_DIR"] = str(latexlog_dir.resolve())
        script_source = CORPUS_ROOT / str(contract["script"])
        script = work / "generate.do"
        shutil.copyfile(script_source, script)
        try:
            process = subprocess.run(
                [str(stata_bin), "-q", "-b", "do", str(script), str(output)],
                cwd=work,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise ContractError(
                f"Stata generator timed out after {timeout_seconds} seconds; "
                "use the command-line Stata executable"
            ) from error
        logs = sorted(work.glob("*.log"))
        log_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace") for path in logs
        )
        if process.returncode != 0 or "TEXPDF LATEXLOG GENERATOR PASS" not in log_text:
            inventory = "\n".join(
                f"{path.relative_to(work)} ({path.stat().st_size} bytes)"
                for path in sorted(work.rglob("*"))
                if path.is_file()
            )
            excerpt = (
                process.stdout + process.stderr + "\n" + log_text + "\nFILES\n" + inventory
            )[-12_000:]
            raise ContractError(
                f"Stata generator failed with status {process.returncode}:\n{excerpt}"
            )

        generated_tex = output / "report.tex"
        if not generated_tex.is_file():
            raise ContractError("Stata generator produced no report.tex")
        normalized = normalize_tex(
            generated_tex.read_text(encoding="utf-8"), str(contract["normalized_comment"])
        )

        generated_assets: list[tuple[Path, Path]] = []
        for encoded in fixture["assets"]:
            relative = Path(encoded).relative_to("latexlog-current")
            source = output / relative
            validate_asset(source)
            generated_assets.append((source, FIXTURE_ROOT / relative))

        committed = FIXTURE_ROOT / "report.tex"
        matches = committed.is_file() and committed.read_text(encoding="utf-8") == normalized
        if update:
            committed.write_text(normalized, encoding="utf-8")
            for source, destination in generated_assets:
                install_asset(source, destination, ghostscript_bin)
            matches = True
        if not matches:
            raise ContractError(
                "normalized generated TeX differs from the committed snapshot; "
                "inspect the change and rerun with --update to replace it"
            )

    return {
        "latexlog_ado_sha256": actual_hash,
        "asset_count": len(fixture["assets"]),
        "updated": update,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--latexlog-dir",
        type=Path,
        default=Path(os.environ["LATEXLOG_DIR"]) if os.environ.get("LATEXLOG_DIR") else None,
    )
    parser.add_argument(
        "--stata-bin",
        type=Path,
        default=Path(os.environ["STATA_BIN"]) if os.environ.get("STATA_BIN") else None,
    )
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--ghostscript-bin",
        type=Path,
        default=Path(shutil.which("gs")) if shutil.which("gs") else None,
        help="Ghostscript executable used to normalize committed PDF assets to PDF 1.3",
    )
    args = parser.parse_args()
    if args.latexlog_dir is None or args.stata_bin is None:
        parser.error("--latexlog-dir/LATEXLOG_DIR and --stata-bin/STATA_BIN are required")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    try:
        ghostscript = args.ghostscript_bin.resolve() if args.ghostscript_bin else None
        result = run(
            args.stata_bin.resolve(),
            args.latexlog_dir.resolve(),
            args.update,
            ghostscript,
            args.timeout_seconds,
        )
    except (ContractError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"TEXPDF_LATEXLOG_CONTRACT_ERROR {error}", file=sys.stderr)
        return 2
    print(
        "TEXPDF_LATEXLOG_CONTRACT_PASS "
        f"ado_sha256={result['latexlog_ado_sha256']} "
        f"assets={result['asset_count']} updated={str(result['updated']).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
