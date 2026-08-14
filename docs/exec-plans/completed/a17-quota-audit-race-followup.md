# A17 Follow-Up: Preserve Quota Audit Across Decline/Expiry Recovery Races

## Status

- State: completed
- Owner: agent
- Created: 2026-08-05
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: none; implementation merged in PR #53 and current repository validation preserves
  the documented contracts.
- Blocker: none
- Parent issue: ANY-20
- Review source: PR #36

## Goal

Make immediate handoff quota exhaustion deterministic under recovery races: once accept wins the
handoff claim and discovers exhausted target quota, quota recovery owns the terminal result and the
request may return `429 quota_exhausted` only after the durable audit chain is committed.

## Semantic decision

Use Option A. Quota recovery owns terminal arbitration after the accepted claim reaches quota
evaluation. Decline and expiry must not replace that outcome; they wait behind handoff lifecycle
serialization and then observe `failed` with `error_code=quota_exhausted`.

## Implementation checklist

- [x] Add handoff lifecycle advisory-lock ownership that survives the accept transaction rollback
      through quota recovery.
- [x] Make handoff quota-exhaustion rollback recovery critical for returned `429` responses.
- [x] Keep quota recovery atomic: `failed` handoff, quota usage row, quota audit pair, and
      `handoff.failed`.
- [x] Add deterministic PostgreSQL coverage for accept-vs-decline, accept-vs-expiry, parallel
      exhausted accepts, retry/fallback idempotency.
- [x] Update handoff/quota/event/runtime docs and generated docs if needed.
- [x] Run focused, PostgreSQL, docs, quick-check, and full-check validation. The original local
      PostgreSQL/full-check limitations remain historical context below; required merge CI and the
      2026-08-13 gardening validation provide the completion evidence.

## Validation notes

- `python scripts/agent/runner.py doctor` failed before implementation because the system Python
  lacks repo dev modules (`pytest`, `yaml`, `pydantic`). Use `uv run python ...` for validation.
- `uv run python scripts/agent/runner.py doctor`: passed.
- Focused DB-free transaction tests: 2 passed.
- Focused handoff/quota collection: 2 passed, PostgreSQL-marked cases skipped locally.
- `uv run python scripts/agent/runner.py validate-configs`: passed.
- `uv run python scripts/agent/runner.py validate-architecture`: passed.
- `uv run python scripts/agent/runner.py validate-docs`: passed after adding required metadata.
- `uv run python scripts/agent/runner.py generate-docs --check`: passed.
- `uv run python scripts/agent/runner.py quick-check`: passed, 227 passed, 297 deselected.
- `uv run python scripts/agent/runner.py full-check`: blocked after embedded quick-check because
  `pnpm install --frozen-lockfile` could not start (`Command not found: None`). `corepack enable
  pnpm` also failed with `EPERM` writing to `D:\Program Files\node.js\pnpm`.
- `uv run python scripts/agent/runner.py postgresql-check`: blocked by missing
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`.
- `uv run python scripts/agent/runner.py dev-up`: blocked because Docker Desktop Linux engine is
  not running, so a local PostgreSQL service could not be provisioned.
