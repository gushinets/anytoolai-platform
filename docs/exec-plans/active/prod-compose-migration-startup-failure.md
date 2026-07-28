# Execution Plan: Production Compose Migration Startup Failure

## Status

- State: active
- Owner: Codex
- Created: 2026-07-28
- Last updated: 2026-07-28
- Review date: 2026-07-28
- Next action: finish the remaining validation commands, then shut the production validation stack down cleanly.
- Blocker: none currently.

## Goal

Identify the real cause of `uv run python scripts/agent/runner.py prod-up` failing and fix it
without bypassing migrations, so the production Compose stack starts cleanly with PostgreSQL,
the migration service, the API, and the worker.

## Diagnostic Findings

- `python scripts/agent/runner.py doctor` is blocked under the system interpreter because
  `pytest`, `yaml`, and `pydantic` are not installed there.
- `uv run python scripts/agent/runner.py prod-up` currently fails immediately on this machine
  unless `ANYTOOLAI_POSTGRES_USER`, `ANYTOOLAI_POSTGRES_PASSWORD`, and `ANYTOOLAI_POSTGRES_DB`
  are explicitly provided, because `infra/compose/.env.prod` is absent locally.
- With explicit production-style Postgres env vars set, `prod-up` currently fails earlier than the
  reported migration-container exit: Docker BuildKit cannot read the repo build context because it
  includes `.pytest-tmp/a12-vertical-api`, which has restrictive Windows ACLs.
- The Alembic graph is healthy: a single head (`0008`) with a valid linear chain back to `0001`.
- The real migration entrypoint succeeds against a clean PostgreSQL database when run directly from
  the repo with `python -m anytoolai_platform_api.migrate`, so the migration code path itself is
  not currently broken on a clean PostgreSQL upgrade.

## Plan

1. Exclude local temp/venv/build artifacts from the production Docker build context so the real
   container path is testable and deterministic.
2. Re-run the actual production Compose startup with explicit local production env vars and inspect
   `migrate` logs/exit state.
3. If the migration container still fails, capture the exact traceback and patch the smallest
   root-cause fix in the migration/image/Compose path.
4. Add regression coverage for the root cause and re-run the required validation ladder.

## Validation Log

- [x] `python scripts/agent/runner.py doctor` (failed as expected under system Python; recorded)
- [x] `uv run python scripts/agent/runner.py prod-up` (failed locally first due missing prod env)
- [x] `uv run python scripts/agent/runner.py prod-up` with explicit prod env vars (failed during
      Docker build-context send because `.pytest-tmp/a12-vertical-api` is unreadable)
- [x] Alembic head/history inspection
- [x] Real migration entrypoint against clean PostgreSQL outside the image build path
- [ ] Re-run production Compose path after build-context fix
- [ ] Inspect `migrate` container logs/exit status after the build-context fix
- [ ] Run focused regression tests
- [ ] Run `validate-configs`
- [ ] Run `validate-architecture`
- [ ] Run `validate-docs`
- [ ] Run `generate-docs --check`
- [ ] Run `quick-check`
- [ ] Run final `prod-up` / `docker compose ps` / `prod-down`
