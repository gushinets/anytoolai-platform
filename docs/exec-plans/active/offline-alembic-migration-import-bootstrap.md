# Execution Plan: Offline Alembic Migration Import Bootstrap

## Status

- State: active
- Owner: agent
- Created: 2026-07-29
- Last updated: 2026-07-29
- Review date: 2026-07-29
- Next action: rerun docs validation and `quick-check`, then summarize the offline/online migration findings and the remaining environment papercuts.
- Blocker: none

## Goal

Make the platform Alembic environment load shared migration helper modules consistently in both
online and offline mode, and restore a working offline SQL-generation path for `upgrade head --sql`
without changing the migration graph or runtime schema contract.

## Scope

### In scope

- Audit the platform Alembic bootstrap, helper imports, and compatibility revisions for offline
  behavior.
- Move repo-root bootstrap earlier so revision imports do not depend on caller working directory.
- Make the existing compatibility revisions tolerate Alembic offline SQL generation.
- Add regression coverage for the real offline Alembic path and preserve online migration coverage.
- Add or update the repo-local Alembic CLI config only if needed for supported offline validation.

### Out of scope

- New migration revisions, revision-id changes, or schema redesign.
- Moving migration-only helpers into application runtime packages.
- Applying live database changes as part of offline SQL-generation tests.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/architecture/runtime-storage.md`
- `migrations/platform/README.md`

## Contracts touched

- DB: Alembic env bootstrap and existing compatibility revisions `0005` through `0009`.
- Tooling: supported offline Alembic invocation for SQL generation.
- Tests: migration regression coverage for offline and online execution.

## Implementation steps

- [x] Inspect migration docs, env/bootstrap code, helper imports, revision files, and current tests.
- [x] Reproduce the offline helper-import failure and confirm it occurs while Alembic imports
  revisions before `0009` SQL can be emitted.
- [x] Reproduce the full offline `head --sql` failure and confirm compatibility revisions also
  require offline-safe handling.
- [ ] Patch bootstrap and compatibility revisions with the smallest symmetric offline/online fix.
- [ ] Add offline regression coverage and validate the real Alembic command path.
- [ ] Run targeted migration tests plus repo validation commands.

## Validation

- [ ] `uv run python -m pytest apps/platform-api/tests/test_migrate.py -q`
- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -q`
- [ ] `uv run alembic -c <platform-alembic-config> upgrade head --sql`
- [ ] `uv run python scripts/agent/runner.py validate-architecture`
- [ ] `uv run python scripts/agent/runner.py validate-docs`
- [ ] `uv run python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-29 | Keep the fix inside the migration layer instead of duplicating DDL or moving helpers elsewhere. | The regression is caused by Alembic bootstrap timing and offline compatibility behavior, not by the existence of shared migration helpers. |
| 2026-07-29 | Treat full offline `upgrade head --sql` as the acceptance target, not only the isolated `0009` import case. | The real supported command currently fails earlier at `0005` on offline schema inspection, so the user-visible regression is broader than the import symptom alone. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-29 | Reviewed runtime-storage and migration docs, inspected `env.py`, helper modules, handoff revisions, Alembic entrypoints, and migration tests. Reproduced `0008:0009 --sql` failing with `ModuleNotFoundError` when repo root is absent from `sys.path`. Reproduced full offline `upgrade head --sql` stopping at `0005` because offline mock connections do not support `sa.inspect(...)`. | Patch env bootstrap first, then make compatibility revisions explicitly offline-safe and cover the real CLI/programmatic path in tests. |

## Open questions

- Whether the repo should check in a dedicated Alembic config file for CLI-driven offline SQL
  generation, or continue relying on programmatic `Config()` objects in tests and entrypoints.

## Follow-up debt

- Consider consolidating repeated offline-compatibility helpers inside `migrations/platform/` if
  more compatibility revisions are added later.
