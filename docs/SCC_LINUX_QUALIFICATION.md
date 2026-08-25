# BU SCC Linux qualification

This is the authoritative Linux runtime gate for the private RC. Hosted Linux
artifacts remain useful development evidence but do not qualify a Stata target.

## Development-only core corpus

For a Linux core corpus check that does not launch licensed Stata or advance
target qualification, deploy an exact source checkout to a new immutable run
directory and submit:

```sh
ci/scc/submit_corpus_linux.sh /projectnb/welfgr/texpdf/runs/RUN_ID
```

The job reconstructs the exact development bundle, validates the corpus
manifest, runs only `texpdf-core`'s real-world corpus integration test, retains
the three PDFs under the run directory, and writes
`receipts/linux-core-corpus.json` with the source SHA, bundle identity, glibc,
platform, and output hashes. It is development evidence, not Linux licensed-
Stata qualification.

The current bounded result is SCC job `7311141` in
`/projectnb/welfgr/texpdf/runs/20260825T212251Z-21cf284-corpus-attempt2`.
It passed on RHEL 8 / GLIBC 2.28 for source `21cf28493624191d52488146b914b8d26cc5291d`;
the committed receipt lives under `release/development-corpus/`.

## Prepare an exact attempt

Use one immutable directory under
`/projectnb/welfgr/texpdf/runs/<UTC>-<full-source-SHA>-linux`. Populate its
`code/` directory from the exact committed source, including `.git`, and verify
that `git status --porcelain` is empty and `git rev-parse HEAD` is the intended
candidate SHA. Never reuse a failed attempt directory.

The SCC workflow pins GCC 12.2.0, CMake 3.31.7, Ninja 1.10.2, Miniconda
25.3.1/Python 3.12.11, and Rust 1.97.1. It uses persistent pinned dependency
caches but a fresh run-scoped Cargo target directory.

## Submit

From the exact checkout on SCC:

```sh
ci/scc/submit_linux_qualification.sh /projectnb/welfgr/texpdf/runs/RUN_ID
```

The command submits a four-slot build and three build-dependent licensed-Stata
jobs: Stata 18 quick, Stata 18 stress1000, and Stata 19 quick. Every consumer
validates the build receipt because `hold_jid` guarantees completion, not
success.

## Accept and collect

After every job leaves `qstat`, run:

```sh
/share/pkg.8/miniconda/25.3.1/install/bin/python3 \
  ci/scc/collect_accounting.py \
  --jobs /projectnb/welfgr/texpdf/runs/RUN_ID/receipts/jobs.json \
  --output /projectnb/welfgr/texpdf/runs/RUN_ID/receipts/scheduler.json
```

This fails unless every `qacct` record has `failed=0` and `exit_status=0`.
Inspect bounded job and Stata logs, then collect the run's `receipts/`, the
Linux ZIP, its manifest, binary policy, bundle information, and plugin-smoke
record without overwriting earlier attempts.

Import collected evidence from repository root with:

```sh
python3 ci/scc/import_linux_qualification.py /path/to/collected-run
python3 tools/sync_project_state.py --require-candidate-ready
```

The importer rejects source or artifact mismatches. Qualification requires no
GLIBC symbol newer than 2.28 and exact successful Stata 18 quick/stress1000 and
Stata 19 quick receipts for the packaged plugin.
