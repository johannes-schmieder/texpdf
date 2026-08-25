#!/usr/bin/env python3
"""Fail closed when Stata and release version metadata disagree."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re


HEADER_RE = re.compile(
    r"\*!\s+(?:version\s+)?(?:texpdf\s+)?"
    r"(?P<version>\d+\.\d+\.\d+)\s+"
    r"(?P<date>\d{1,2}[a-zA-Z]{3}\d{4})"
)
FINAL_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
RC_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)-rc(?P<number>[1-9]\d*)$")
PKG_DATE_RE = re.compile(r"^d Distribution-Date:\s*(?P<date>\d{8})\s*$", re.MULTILINE)
DISPLAY_VERSION_RE = re.compile(r'display\s+as\s+text\s+"texpdf\s+(?P<version>\d+\.\d+\.\d+);')
WORKSPACE_PACKAGE_RE = re.compile(
    r"^\[workspace\.package\]\s*(?P<body>.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL
)
TOML_VERSION_RE = re.compile(r'^version\s*=\s*"(?P<version>\d+\.\d+\.\d+)"\s*$', re.MULTILINE)
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_stata_date(value: str) -> date:
    match = re.fullmatch(r"(\d{1,2})([a-zA-Z]{3})(\d{4})", value)
    if match is None or match.group(2).lower() not in MONTHS:
        raise ValueError(f"invalid Stata date: {value}")
    return date(
        int(match.group(3)),
        MONTHS[match.group(2).lower()],
        int(match.group(1)),
    )


def read_header(path: Path) -> tuple[str, date]:
    text = path.read_text(encoding="utf-8")
    match = HEADER_RE.search("\n".join(text.splitlines()[:10]))
    if match is None:
        raise ValueError(f"{path} has no version/date header near the top")
    return match.group("version"), parse_stata_date(match.group("date"))


def check(root: Path, tag: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        ado_path = root / "stata/texpdf.ado"
        ado_version, ado_date = read_header(ado_path)
        ado_text = ado_path.read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        return [str(error)]
    try:
        help_version, help_date = read_header(root / "stata/texpdf.sthlp")
    except (OSError, ValueError) as error:
        return [str(error)]

    if (help_version, help_date) != (ado_version, ado_date):
        errors.append(
            "ado/help metadata mismatch: "
            f"ado={ado_version} {ado_date.isoformat()} "
            f"help={help_version} {help_date.isoformat()}"
        )

    display_versions = DISPLAY_VERSION_RE.findall(ado_text)
    if display_versions != [ado_version]:
        errors.append(
            "texpdf, version output must contain exactly one version matching "
            f"the ado header: expected={ado_version} actual={display_versions}"
        )

    try:
        cargo_text = (root / "Cargo.toml").read_text(encoding="utf-8")
    except OSError as error:
        errors.append(str(error))
        cargo_text = ""
    workspace = WORKSPACE_PACKAGE_RE.search(cargo_text)
    cargo_version = TOML_VERSION_RE.search(workspace.group("body")) if workspace else None
    if cargo_version is None or cargo_version.group("version") != ado_version:
        errors.append(
            "Cargo workspace package version must match the ado header: "
            f"ado={ado_version} cargo={cargo_version.group('version') if cargo_version else 'missing'}"
        )

    try:
        package_text = (root / "stata/texpdf.pkg").read_text(encoding="utf-8")
    except OSError as error:
        errors.append(str(error))
        package_text = ""
    package_dates = PKG_DATE_RE.findall(package_text)
    expected_package_date = ado_date.strftime("%Y%m%d")
    if package_dates != [expected_package_date]:
        errors.append(
            "texpdf.pkg must contain exactly one Distribution-Date matching "
            f"the ado header: expected={expected_package_date} actual={package_dates}"
        )

    try:
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError as error:
        errors.append(str(error))
        changelog = ""
    if re.search(r"^## Unreleased\s*$", changelog, re.MULTILINE) is None:
        errors.append("CHANGELOG.md must contain a top-level Unreleased section")

    if tag is None:
        return errors

    final_match = FINAL_TAG_RE.fullmatch(tag)
    rc_match = RC_TAG_RE.fullmatch(tag)
    tag_match = final_match or rc_match
    if tag_match is None:
        errors.append("release tag must be vX.Y.Z or vX.Y.Z-rcN")
        return errors
    if tag_match.group("version") != ado_version:
        errors.append(
            f"tag version {tag_match.group('version')} does not match ado version {ado_version}"
        )
    if final_match is not None:
        heading = re.compile(
            rf"^## {re.escape(ado_version)} - (?P<date>\d{{4}}-\d{{2}}-\d{{2}})\s*$",
            re.MULTILINE,
        ).search(changelog)
        if heading is None:
            errors.append(
                f"final tag {tag} requires a dated CHANGELOG.md section for {ado_version}"
            )
        elif heading.group("date") != ado_date.isoformat():
            errors.append(
                "changelog release date does not match Stata metadata: "
                f"changelog={heading.group('date')} metadata={ado_date.isoformat()}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag")
    args = parser.parse_args()
    errors = check(args.root, args.tag)
    if errors:
        for error in errors:
            print(f"release metadata error: {error}")
        return 1
    print(f"TEXPDF_RELEASE_METADATA_PASS tag={args.tag or 'development'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
