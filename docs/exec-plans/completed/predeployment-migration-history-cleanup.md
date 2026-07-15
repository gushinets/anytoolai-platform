# Execution Plan: Predeployment Migration History Cleanup

## Status

- State: completed
- Owner: agent
- Created: 2026-06-22
- Last updated: 2026-06-22
- Completion note: superseded by the accepted migration compatibility contract in
  `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md` and the current migration chain.

## Goal

Collapse repair-only Alembic revisions back into the original MVP-A runtime migration chain so a
clean database reaches the final schema through `0001 -> 0002 -> 0003 -> 0004` with one head.

## Scope

### In scope

- Fold `scenario_sessions.created_at` and `ix_scenario_sessions_created_at` into
  `migrations/platform/versions/0001_runtime_tables.py`.
- Fold `platform.event_log` creation plus its indexes/constraints into
  `migrations/platform/versions/0002_event_log.py`.
- Remove repair migrations that only existed to fix old placeholder-applied revisions.
- Update migration-focused tests to validate the clean chain and final schema contract.
- Keep runtime storage table definitions and repositories aligned with the final schema.

### Out of scope

- Preserving compatibility for already-stamped placeholder local databases.
- Rewriting unrelated runtime storage, event emitter, or product logic.
- Adding new forward-fix migrations beyond the clean four-revision chain.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/event-taxonomy.md`

## Contracts touched

- DB: `platform.scenario_sessions`, `platform.event_log`, Alembic revision chain.
- Runtime storage: shared SQLAlchemy table metadata must continue matching the migration schema.
- Tests: migration-chain, runtime-storage, and event-log schema verification.

## Implementation steps

- [x] Confirm the current clean-schema definitions in `0001`, `0002`, and shared storage metadata.
- [x] Remove repair-only revisions from the Alembic chain and adjust tests to target the clean path.
- [x] Run migration, head, schema, and targeted runtime/event-log tests against a clean database.
- [ ] Summarize the folded migrations, removed repairs, final chain, checks, and local DB impact.

## Validation

- [x] `python scripts/agent/runner.py doctor` (environment failure: global Python missing `pytest`, `yaml`, `pydantic`)
- [x] `.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_event_log.py`
- [x] `.quick-check-venv\Scripts\python.exe` Alembic head check via `command.heads(...)` -> `0004 (head)`
- [x] Clean SQLite+attached-`platform` migration-to-head schema inspection for `scenario_sessions` and `event_log`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-22 | Treat `0005` and `0006` as removable repair history if they only serve placeholder-applied databases. | The project is still pre-deployment and the user explicitly asked for a clean chain instead of production-safe repair compatibility. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-22 | Reviewed repo architecture docs, runtime-storage/event-taxonomy docs, active runtime/event-log plans, and the current Alembic/test files. | Run doctor fallback, then patch the migration chain and remove repair-path tests. |
| 2026-06-22 | Removed repair-only `0005`/`0006`, updated migration tests to the four-revision chain, and verified clean-head schema plus targeted storage/event-log tests. | Deliver summary and note that local dev DBs may need recreation or restamping. |

## Open questions

None at the moment.

## Follow-up debt

- Local developer databases stamped against the removed repair revisions may need recreation or
  restamping after this cleanup.
