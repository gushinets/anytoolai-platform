# Execution Plan: Handoff Migration Table-Check Canonicalization

## Status

- State: active
- Owner: agent
- Created: 2026-07-29
- Last updated: 2026-07-29
- Review date: 2026-07-29
- Next action: patch the helper/docs/tests so future handoff migrations use one canonical
  schema-aware table-existence helper while `0008` keeps its historical self-contained guard.
- Blocker: none

## Goal

Clarify and enforce the canonical migration-layer pattern for schema-aware `product_handoffs`
table-existence checks without rewriting historical compatibility revision behavior unnecessarily.

## Scope

### In scope

- Reconfirm the migration-history policy around historical compatibility revisions.
- Keep or refine `product_handoffs_table_exists()` as the canonical helper for future revisions.
- Add comments/docs that explain why `0008_handoffs_compat.py` retains its inline historical check.
- Add focused regression coverage for the helper and handoff compatibility behavior.

### Out of scope

- Changing revision IDs or adding new migration revisions.
- Rewriting `0008` to depend on mutable helper modules unless the repo clearly treats it as
  rebasable.
- Any application-layer imports or runtime model dependencies in migrations.

## Relevant docs

- `docs/architecture/runtime-storage.md`
- `migrations/platform/README.md`
- `docs/exec-plans/completed/a17-review-followups.md`
- `docs/exec-plans/completed/a17-access-log-review-followup.md`

## Contracts touched

- DB: migration-layer helper guidance for `product_handoffs` compatibility revisions.
- Tests: handoff migration helper and compatibility regression coverage.
- Docs: migration-layer policy/guidance for future revisions.

## Implementation steps

- [x] Inspect migration policy docs, handoff helper usage, and current compatibility tests.
- [ ] Patch helper/doc/comment guidance with the chosen historical-migration policy.
- [ ] Add focused regression coverage and run the relevant migration validation ladder.

## Validation

- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -q`
- [ ] `uv run python -m pytest apps/platform-api/tests/test_migrate.py -q`
- [ ] `uv run alembic -c migrations/platform/alembic.ini upgrade head --sql`
- [ ] `uv run python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-29 | Keep `0008_handoffs_compat.py` self-contained instead of rewriting it to call `_handoffs_table.product_handoffs_table_exists()`. | Prior repo decisions already treated `0008` as a historical compatibility revision that should not depend on mutable non-revision helpers. |
| 2026-07-29 | Make `product_handoffs_table_exists()` the documented canonical helper for new handoff migrations. | That preserves one forward-looking pattern without retroactively changing released behavior. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-29 | Reviewed the handoff helper, revisions `0008`/`0009`, runtime-storage docs, and prior completed plans. Confirmed the repo already rejected rewriting `0008` to depend on mutable helpers and that `0009` is the only revision using the shared helper today. | Patch comments/docs/helper guidance, then add focused tests and rerun offline/online migration validation. |

## Open questions

- None at the moment.

## Follow-up debt

- If future migration-layer helper modules grow further, consider a short `migrations/platform/`
  guidance section dedicated to what historical compatibility revisions may or may not import.
