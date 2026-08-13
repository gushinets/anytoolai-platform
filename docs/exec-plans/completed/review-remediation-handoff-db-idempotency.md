# Execution Plan: Review Remediation — Handoff, Test DB, and Idempotency

## Status

- State: completed
- Owner: Codex
- Created: 2026-07-31
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: none; implementation is merged, focused regressions pass, and the production-dialect
  cases remain owned by the required PostgreSQL CI gate.
- Blocker: none

## Goal

Make handoff schema failures diagnosable, disposable PostgreSQL test databases reliably cleaned up,
and preserve idempotency router/OpenAPI coverage in the appropriate fast and PostgreSQL gates.

## Scope

### In scope

- Attached review findings 1–4 and their focused regression coverage
- A concise relevance verdict for every finding
- A task handoff document with exact validation results

### Out of scope

- Product-specific behavior
- Unrelated test-infrastructure refactors
- Changes to already-uncommitted remediation work outside these findings

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/handoff-model.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/config-model.md`

## Contracts touched

- API: idempotency conflict status/message contracts
- DB: disposable PostgreSQL test database lifecycle only
- Config: handoff target-schema diagnostics
- Events: none expected
- Frontend: none

## Implementation steps

- [x] Classify all attached findings against the current repository state.
- [x] Add a distinct safe configuration error for malformed handoff target schemas and test it.
- [x] Make disposable database cleanup cover failed setup and active-session teardown safely, with tests.
- [x] Restore only missing idempotency API/OpenAPI coverage in the correct test gates.
- [x] Run targeted and repository validation; record unavailable local PostgreSQL coverage accurately.
- [x] Create the requested task handoff document.

## Validation

- [x] Focused handoff-schema, database-helper, and idempotency-router tests (`5 passed` on 2026-08-13)
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-31 | Keep actual PostgreSQL lifecycle behavior PostgreSQL-specific. | SQLite cannot prove database create/drop semantics or idempotency transaction behavior. |
| 2026-07-31 | Use `DROP DATABASE ... WITH (FORCE)` for cleanup. | CI runs PostgreSQL 16, where forced drop is supported and atomically eliminates the terminate/reconnect window. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-31 | Created plan; reviewed the runtime-storage, handoff, and config contracts; `doctor` was attempted and is blocked by absent system-Python dependencies. | Verify each finding and inspect existing tests before implementation. |
| 2026-07-31 | Confirmed all four findings: handoff runtime taxonomy and schema-load validation were incomplete; setup cleanup began after database creation; teardown had a terminate/drop race; idempotency lacked fast router/OpenAPI and PostgreSQL HTTP conflict tests. | Run focused and available repository checks; PostgreSQL-marked tests remain unavailable locally without the maintenance URL. |

## Open questions

- Is a disposable PostgreSQL maintenance URL available locally for end-to-end lifecycle validation?

## Follow-up debt

- None identified yet.
