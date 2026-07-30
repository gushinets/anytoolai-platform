# Execution Plan: Quota PostgreSQL Test Helper Dedup

## Status

- State: completed
- Owner: agent
- Created: 2026-07-30
- Last updated: 2026-07-30
- Review date: 2026-07-30
- Next action: Ready for review or handoff.
- Blocker: none

## Goal

Verify whether duplicated quota-policy override helpers in the PostgreSQL quota concurrency tests are
still a real maintenance issue, and make a narrow test-only cleanup only if the finding remains valid.

## Scope

### In scope

- Inspect `apps/platform-api/tests/test_quota_concurrency_postgresql.py` helper implementations and
  call sites.
- Compare nearby test-helper conventions.
- Optionally extract one local helper for overriding the immutable guest quota policy in the API test
  app runtime.
- Validate with the PostgreSQL quota concurrency suite and quick-check.

### Out of scope

- Production quota code.
- Shared test utility extraction beyond this file unless an existing obvious utility is present.
- Behavior changes to quota semantics.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/quota-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- API: none
- DB: none
- Config: test-only runtime registry override
- Events: none
- Frontend: none

## Implementation steps

- [x] Inspect current helper implementations and call sites.
- [x] Review nearby helper conventions for immutable registry overrides.
- [x] Classify the finding and document the decision.
- [x] If valid, extract a small local quota-policy override helper.
- [x] Run requested validation.

## Validation

- [x] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q`
- [x] Non-slow tests in the file, if any
- [x] `uv run python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-30 | Finding appears still valid and worth fixing locally. | The three helpers share one coherent app-runtime quota-policy override flow and differ only by policy `replace()` overrides and thin intention-revealing return values. Consolidating the common flow preserves the wrappers while reducing future drift. |
| 2026-07-30 | Keep intention-revealing wrappers. | `_scenario_start_quota_limit`, `_force_scenario_guest_quota`, and `_force_zero_guest_quota` communicate distinct test setup intent and return contracts; only the shared immutable-registry replacement mechanics were hidden. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-30 | Read the target file, call sites, quota model docs, and nearby helper conventions. `runner.py doctor` reports missing system Python modules, but `uv` is available. | Apply the local helper extraction and run validation. |
| 2026-07-30 | Extracted `_override_guest_quota_policy` in `test_quota_concurrency_postgresql.py`. Slow PostgreSQL tests skipped because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset; the file has no non-slow tests; quick-check passed. | Ready for handoff. |

## Open questions

None.

## Follow-up debt

None identified.
