# Execution Plan: SOLID Boundaries and PostgreSQL-Only Cleanup

## Status

- State: completed
- Owner: agent
- Created: 2026-07-30
- Last updated: 2026-07-30
- Review date: 2026-07-30
- Next action: none
- Blocker: `python scripts/agent/runner.py doctor` still fails under the system Python because
  `pytest`, `yaml`, and `pydantic` are missing there. This is a known local tooling papercut, not
  a blocker for the managed `quick-check` path.

## Goal

Tighten responsibility boundaries in three narrow areas without adding new speculative layers:

1. remove hidden multi-dialect policy from `QuotaUsageRepository`;
2. stop using `conftest.py` as an implicit test library;
3. make handoff migration revisions self-contained enough that historical behavior does not depend
   on future edits to mutable helper modules.

## Scope

### In scope

- `packages/backend/platform-core/src/anytoolai_platform_core/quotas/repository.py`
- test-support wiring around root/nested `conftest.py` and disposable database helpers
- handoff migration helper usage in `migrations/platform/versions/*`
- narrow documentation updates that explain the resulting structure

### Out of scope

- broader repository-wide SOLID refactors
- reintroducing SQLite compatibility or generic multi-dialect abstractions
- adding a large new testing infrastructure layer

## Relevant docs

- `ARCHITECTURE.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/quota-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Decisions to enforce

- PostgreSQL is the only supported runtime database path.
- The quota repository may rely on PostgreSQL-native SQL, but it must not quietly choose fallback
  behavior for unsupported engines.
- `conftest.py` stays pytest wiring, not a shared import library.
- Shared test DB helpers are allowed only as a minimal, explicit, test-only helper layer.
- Historical Alembic revisions should not import mutable helper behavior when the revision logic can
  be made self-contained.

## Implementation steps

- [x] Remove the quota repository's dialect branch and silent fallback.
- [x] Replace `from conftest import ...` test-library usage with explicit test-only helper imports.
- [x] Remove dynamic loading of repo-root `conftest.py` from nested test wiring.
- [x] Inline or otherwise isolate mutable handoff migration helper behavior from historical
  revisions.
- [x] Update docs that currently describe the old test-support or migration-helper arrangement.
- [x] Run focused pytest coverage and `python scripts/agent/runner.py quick-check`.

## Validation

- [x] `uv run python -m pytest tests/test_quick_check.py tests/test_runner.py packages/backend/platform-core/tests/unit/test_database_url.py apps/platform-api/tests/test_migrate.py -q --basetemp .quick-check-tmp\pytest-solid-boundaries-fast`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -q --basetemp .quick-check-tmp\pytest-solid-boundaries-runtime`
  Result: passed with PostgreSQL-marked tests skipped because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`
  is not configured in this local environment.
- [x] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q --basetemp .quick-check-tmp\pytest-solid-boundaries-quota`
  Result: skipped for the same missing disposable PostgreSQL test URL.
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-30 | Re-read the required architecture docs and confirmed the repository contract again: runtime state is PostgreSQL-only, test wiring should stay boring and explicit, and platform layers should not blur ownership. | Patch the three targeted boundary problems without adding speculative abstractions. |
| 2026-07-30 | Removed the quota repository's dialect policy, pushed PostgreSQL-only enforcement into runtime storage creation, replaced hidden `conftest.py` imports with explicit `tests.db_support` usage, and made handoff compatibility revisions self-contained. | Run focused validation and finish the handoff notes. |
| 2026-07-30 | Focused pytest coverage passed, PostgreSQL-marked suites skipped cleanly without a configured disposable PostgreSQL URL, `validate-architecture` passed, and `quick-check` passed (`209 passed, 230 deselected`). | Close the plan. |
