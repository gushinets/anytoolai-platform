# Execution Plan: ANY-220 Atom Runtime Proof CLI And Evidence Report

## Status

- State: active
- Owner: agent
- Created: 2026-08-18
- Last updated: 2026-08-18
- Review date: 2026-08-18
- Next action: open the PR.
- Blocker: none.

## Goal

One reproducible command, `python scripts/agent/runner.py atoms-proof`, that drives all 11
standalone atoms and all 3 composite kernel_demo workflows over live HTTP against a running
dev/prod compose stack, verifies the DB ledger/event correlation each run actually left behind,
prints per-case PASS/FAIL evidence plus an 11/11 + 3/3 summary, and persists a privacy-safe JSON
evidence report to `.agent/atoms-proof/`.

Full design rationale lives in `plans/ANY-220.md` (Design section) — this file tracks
implementation status only.

## Scope

### In scope

- `scripts/agent/atoms_proof.py`: reuses `kernel_demo_smoke.py`'s HTTP start/poll/schema_ref
  logic verbatim; adds a read-only DB ledger/event check (jobs/action_runs/provider_calls/
  artifacts/event_log tables, filtered by `scenario_session_id`) not covered by either existing
  proof mechanism for a live run.
- `atoms-proof` command wired into `scripts/agent/runner.py`, following `dev-smoke`'s pattern.
- `tests/test_atoms_proof.py`: no-DB/no-network unit tests for the pure classification logic
  and the evidence report writer.
- `scripts/agent/quick_check.py`: added the new test file to `PYTEST_TARGETS`.

### Out of scope

- ANY-221 (live-provider canary) — still runs against the fake provider stack.
- Any change to `kernel_demo_smoke.py`'s own behavior/output, or to the frozen hot-path files
  listed in ANY-220/ANY-24.

## Relevant docs

- `plans/ANY-220.md` (full design, including two corrections found during review: the
  `postgresql+psycopg` driver requirement, and resolving `job_id`/`result_artifact_id` via
  `jobs_table` keyed by `scenario_session_id` rather than assuming `job_id` is available from
  the HTTP layer).
- `docs/architecture/package-layering.md`

## Contracts touched

- API: none (read-only consumer of existing `/v1/*` endpoints).
- DB: read-only (`jobs`, `action_runs`, `provider_calls`, `artifacts`, `event_log`).
- Config: none.
- Events: none produced; existing event types read and asserted against.
- Frontend: none.

## Implementation steps

- [x] `scripts/agent/atoms_proof.py`: HTTP reuse + DB ledger check (`_classify_ledger` pure
      function + `_check_ledger` DB wrapper), evidence report writer, CLI entrypoint.
- [x] Wire `atoms-proof` into `scripts/agent/runner.py` (function + `COMMANDS` registration).
- [x] `tests/test_atoms_proof.py` (15 cases, no DB/network) + register in `quick_check.py`.
- [x] `validate-configs` / `validate-architecture` / `quick-check` all pass (760 tests).
- [x] Live proof: `dev-up` -> `atoms-proof` (11/11 + 3/3, exit 0, evidence JSON written and
      inspected) -> `dev-down`. Ran twice to confirm determinism.
- [x] `full-check` (baseline + frontend typecheck/test/build/generate-api-types + freelancer-suite).
- [ ] PR opened.

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py dev-up && python scripts/agent/runner.py atoms-proof && python scripts/agent/runner.py dev-down`
- [x] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-18 | Filter `action_runs`/`provider_calls`/`artifacts` by `scenario_session_id`, not `job_id` | `CaseResult` from the reused `kernel_demo_smoke._run_one_case` only exposes `session_id`; `job_id` isn't available without an extra DB lookup, and all three tables already carry an indexed `scenario_session_id` column. |
| 2026-08-18 | Resolve `job_id`/`result_artifact_id` via one `jobs_table` lookup keyed by `scenario_session_id` | Needed for the `result_artifact_id` membership check; avoids modifying `kernel_demo_smoke.py` (out of scope) or adding an extra HTTP round-trip. |
| 2026-08-18 | Coerce `RuntimeIdentity.database_url`'s bare `postgresql://` to `postgresql+psycopg://` before `sa.create_engine` | Repo only installs `psycopg` v3, no `psycopg2`; the bare scheme defaults to the psycopg2 dialect and fails at engine-creation time otherwise. |
| 2026-08-18 | Check `result_artifact_id` is present among artifacts (membership), not "equals the last step's artifact id" | `workflows/runner.py`'s `_create_final_artifact` always creates a separate artifact row (`action_run_id=None`); it never reuses a step's own `output_artifact_id` (confirmed by `test_composite_workflow_matrix.py`). |
| 2026-08-18 | Split `_check_ledger` (DB query) from `_classify_ledger` (pure pass/fail logic) | Makes the PROOF00x failure-classification branches unit-testable with fake dict rows, no real Postgres needed. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-18 | Implemented `atoms_proof.py`, wired `atoms-proof`, added tests, ran quick-check gate and a live `dev-up`/`atoms-proof`/`dev-down` cycle twice — both 11/11 + 3/3, exit 0. Ran `full-check` (frontend + backend) clean. | Open PR. |

## Open questions

None outstanding.

## Follow-up debt

None identified.
