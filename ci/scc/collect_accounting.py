#!/usr/bin/env python3
"""Collect and validate SGE accounting for a completed Linux qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


def accounting(job_id: str) -> dict[str, object]:
    result = subprocess.run(
        ["qacct", "-j", job_id], text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"qacct is unavailable for {job_id}: {result.stderr.strip()}")
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line or line.startswith("===="):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1].strip()
    if values.get("failed") != "0" or values.get("exit_status") != "0":
        raise RuntimeError(
            f"job {job_id} failed: failed={values.get('failed')} "
            f"exit_status={values.get('exit_status')}"
        )
    return {
        "job_id": job_id,
        "failed": 0,
        "exit_status": 0,
        "hostname": values.get("hostname"),
        "queue": values.get("qname"),
        "slots": int(values.get("slots", "0")),
        "ru_wallclock_seconds": int(float(values.get("ru_wallclock", "0"))),
        "cpu_seconds": float(values.get("cpu", "0")),
        "maxvmem": values.get("maxvmem"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    names = ("build", "stata_18_quick", "stata_18_stress1000", "stata_19_quick")
    payload = {
        "schema_version": 1,
        "source_sha": jobs["source_sha"],
        "candidate_version": jobs["candidate_version"],
        "status": "success",
        "jobs": {name: accounting(str(jobs[name])) for name in names},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("TEXPDF_SCC_ACCOUNTING_PASS", *(f"{name}={jobs[name]}" for name in names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
