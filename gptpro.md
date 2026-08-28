# Licensed Stata and Rust CI handoff

This repository uses a repository-scoped GitHub Actions runner on Johannes's
Mac Studio. It accepts only trusted pushes and explicit dispatches; no
pull-request event can execute on it. Operational setup and recovery details
live in [`STATA_CI_RUNNER.md`](STATA_CI_RUNNER.md).

## What this repository provides

The workflow is named **Licensed Stata and Rust CI**. A normal push to `main` or a trusted `codex/**` branch runs one nonredundant macOS lane:

1. a licensed Stata/MP batch test; and
2. a Rust quick test.

The Stata lane runs the selected licensed profile against the repository
package. The Rust lane runs formatting, strict Clippy, and workspace tests with
the pinned toolchain. Release qualification uses additional platform, memory,
license, corpus, and package workflows described in `RELEASING.md`.

There is no self-hosted `pull_request` trigger and no redundant GitHub-hosted matrix on ordinary pushes.

## Development loop

1. Read this file, `PLAN.md`, `STATA_CI_RUNNER.md`, the workflow, and the current `main` state.
2. **Develop directly on `main` unless the owner explicitly requests otherwise.** Do not create a development branch by default.
3. Make one focused change, record the exact full source commit SHA, and push it to `main` using the write-capable GitHub/Codex tools available in the session. Push frequently so the repository remains the durable source of truth.
4. Query workflow runs for that exact commit when the connector exposes commit-bound workflow discovery. Otherwise use the immutable receipt below when it appears.
5. Read `.ci/stata/results/<full-source-sha>.json`. Do not infer success from the branch head or from an older receipt.
6. Require all of:
   - `tested_sha` exactly equals the intended source commit;
   - `status` is `success`;
   - `stata_status` is `success`;
   - `rust_status` is `success`;
   - `profile` is the intended profile.
7. Use `.ci/stata/latest.json` only as a convenience pointer and always verify its complete `tested_sha`. Receipt publisher commits advance `main` after the source push and use `[skip ci]`.
8. On failure, inspect `failure_kind`, `process_rc`, `stata_rc`, `rust_rc`, the workflow jobs, and the artifact named for the source SHA/run. Fix the source in another small `main` checkpoint and repeat; do not rewrite history.
9. Never put a deliberate failing checkpoint on `main`. If failure-reporting infrastructure itself must be tested, use a temporary trusted branch and do not merge its failing tip.

Manual workflow profiles are `version`, `smoke`, and `quick`. Normal pushes use `quick`. More profiles can be added in repository configuration when actual Stata/Mata or plugin tests exist; no machine-level runner changes should be needed.

## Important failure semantics

Stata on this Mac can return shell status zero even after a Stata-language error. The workflow therefore treats the explicit Stata status file and PASS marker as authoritative. It separately distinguishes launch failure, timeout, crash or missing output, ordinary Stata error, and Rust failure.

A missing exact-SHA receipt is not evidence that the source passed or failed. It means the run may be queued, the runner may be offline or busy, the run may have been cancelled, or the publisher may have failed. Inspect the exact commit's workflow run or ask the owner to check **Settings → Actions → Runners**.

## GitHub access note

OpenAI's standard ChatGPT GitHub app may be read-only in some ChatGPT experiences. If the current GPT Pro session lacks branch/file write actions, it cannot push a checkpoint by itself; use a write-capable Codex session or another authorized Git client for the push, then use the same receipt loop.

## Security boundary

The self-hosted runner executes workflow code with the authority of the logged-in macOS user. Therefore:

- execute self-hosted jobs only from trusted pushes or explicit dispatches in
  this repository;
- never add `pull_request` or `pull_request_target` triggers to a self-hosted
  or licensed-Stata workflow, and never execute an untrusted fork/ref;
- keep every third-party action pinned to a full commit SHA and default
  workflow permissions read-only;
- never print, request, commit, or upload registration tokens, passwords, credentials, Stata license material, home-directory contents, unrelated files, or confidential research data;
- use synthetic fixtures unless the owner explicitly authorizes data;
- keep artifacts limited to `.ci/stata/run/`;
- do not change machine-level runner configuration from repository code;
- do not claim Stata or Rust ran locally inside the ChatGPT sandbox.

Lead every CI report with the exact tested SHA, profile, overall status, Stata status, Rust status, and any qualification boundary.
