#!/usr/bin/env python3
"""Cross-platform smoke test for the exported texpdf plugin ABI.

The Rust bridge does not call Stata's callback table, so it can be exercised
with ctypes before an actual Stata runtime is available. This verifies the
binary exports, argument ABI, embedded bundle, result schema, real PDF output,
and recoverable TeX failures. It does not replace licensed Stata qualification.
"""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import tempfile


class SmokeError(RuntimeError):
    """A plugin ABI smoke-test failure."""


def parse_result(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SmokeError(f"plugin did not create result file: {path}")
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        key, separator, value = line.partition("=")
        if not separator or not key:
            raise SmokeError(f"malformed result line {number}: {line!r}")
        if key in values:
            raise SmokeError(f"duplicate result key: {key}")
        values[key] = value
    if values.get("schema_version") != "1":
        raise SmokeError(f"unexpected result schema: {values.get('schema_version')!r}")
    if values.get("status") not in {"success", "failure"}:
        raise SmokeError(f"invalid result status: {values.get('status')!r}")
    try:
        int(values["rc"])
    except (KeyError, ValueError) as error:
        raise SmokeError("result record has no valid rc") from error
    return values


def load_plugin(path: Path):
    try:
        library = ctypes.CDLL(str(path.resolve()))
    except OSError as error:
        raise SmokeError(f"cannot load plugin {path}: {error}") from error
    try:
        pginit = library.pginit
        stata_call = library.stata_call
    except AttributeError as error:
        raise SmokeError(f"required plugin export is missing: {error}") from error
    pginit.argtypes = [ctypes.c_void_p]
    pginit.restype = ctypes.c_int
    stata_call.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
    stata_call.restype = ctypes.c_int
    return library, pginit, stata_call


def call(stata_call, arguments: list[str]) -> int:
    encoded = [value.encode("utf-8") for value in arguments]
    vector_type = ctypes.c_char_p * len(encoded)
    vector = vector_type(*encoded)
    return int(stata_call(len(encoded), vector))


def require_success(record: dict[str, str], operation: str) -> None:
    if record.get("status") != "success" or record.get("rc") != "0":
        raise SmokeError(f"{operation} failed: {record}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.plugin.is_file():
        raise SmokeError(f"plugin does not exist: {args.plugin}")
    _library, pginit, stata_call = load_plugin(args.plugin)
    spi = int(pginit(None))
    if spi != 3:
        raise SmokeError(f"pginit returned SPI {spi}, expected 3")

    with tempfile.TemporaryDirectory(prefix="texpdf-abi-smoke-") as temporary_text:
        temporary = Path(temporary_text)
        version_result = temporary / "version.result"
        native_rc = call(stata_call, ["version", str(version_result)])
        if native_rc != 0:
            raise SmokeError(f"version native call returned {native_rc}")
        version = parse_result(version_result)
        require_success(version, "version")
        if version.get("engine") != "tectonic":
            raise SmokeError(f"unexpected engine: {version.get('engine')}")
        if version.get("engine_version") != "0.17.0":
            raise SmokeError(f"unexpected engine version: {version.get('engine_version')}")
        if len(version.get("bundle_digest", "")) != 64:
            raise SmokeError("bundle digest is missing or malformed")

        include_dir = temporary / "sections"
        include_dir.mkdir()
        (include_dir / "part.tex").write_text(
            "ABI smoke test with Unicode: café, $\\alpha+\\beta$.\n",
            encoding="utf-8",
        )
        source = temporary / "main document é.tex"
        source.write_text(
            """\\documentclass{article}
\\usepackage{amsmath}
\\usepackage{booktabs}
\\begin{document}
\\input{sections/part.tex}
\\begin{tabular}{lr}
\\toprule
Statistic & Value \\\\
\\midrule
N & 100 \\\\
\\bottomrule
\\end{tabular}
\\end{document}
""",
            encoding="utf-8",
        )
        pdf = temporary / "compiled result é.pdf"
        compile_result = temporary / "compile.result"
        native_rc = call(
            stata_call,
            ["compile", str(source), str(pdf), str(compile_result), "0", "0"],
        )
        if native_rc != 0:
            raise SmokeError(f"compile native call returned {native_rc}")
        compiled = parse_result(compile_result)
        require_success(compiled, "compile")
        if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):
            raise SmokeError("real compile did not produce a PDF")

        existing_result = temporary / "existing.result"
        native_rc = call(
            stata_call,
            ["compile", str(source), str(pdf), str(existing_result), "0", "0"],
        )
        if native_rc != 0:
            raise SmokeError(f"existing-output native call returned {native_rc}")
        existing = parse_result(existing_result)
        if existing.get("status") != "failure" or existing.get("rc") != "602":
            raise SmokeError(f"existing-output policy returned unexpected record: {existing}")

        bad_source = temporary / "bad.tex"
        bad_source.write_text(
            "\\documentclass{article}\\begin{document}\\undefinedcontrolsequence\\end{document}",
            encoding="utf-8",
        )
        bad_pdf = temporary / "bad.pdf"
        bad_result = temporary / "bad.result"
        native_rc = call(
            stata_call,
            ["compile", str(bad_source), str(bad_pdf), str(bad_result), "0", "0"],
        )
        if native_rc != 0:
            raise SmokeError(f"bad-TeX native call returned {native_rc}")
        failed = parse_result(bad_result)
        if failed.get("status") != "failure" or failed.get("rc") != "459":
            raise SmokeError(f"bad TeX returned unexpected record: {failed}")
        if bad_pdf.exists():
            raise SmokeError("failed compilation left a PDF behind")

        recovery_result = temporary / "recovery.result"
        native_rc = call(stata_call, ["version", str(recovery_result)])
        if native_rc != 0:
            raise SmokeError(f"post-error version native call returned {native_rc}")
        require_success(parse_result(recovery_result), "post-error version")

        payload = {
            "schema_version": 1,
            "plugin": str(args.plugin),
            "plugin_size_bytes": args.plugin.stat().st_size,
            "spi_version": spi,
            "engine": version["engine"],
            "engine_version": version["engine_version"],
            "bundle_version": version.get("bundle_version"),
            "bundle_digest": version.get("bundle_digest"),
            "bundle_zip_sha256": version.get("bundle_zip_sha256"),
            "version": "success",
            "compile": "success",
            "existing_output": "success",
            "bad_tex": "success",
            "post_error_recovery": "success",
            "stata_runtime_qualified": False,
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print("TEXPDF_PLUGIN_ABI_SMOKE_PASS", json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as error:
        print(f"TEXPDF_PLUGIN_ABI_SMOKE_ERROR {error}")
        raise SystemExit(2)
