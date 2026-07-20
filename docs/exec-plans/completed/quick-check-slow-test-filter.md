# Execution Plan: Quick-Check Slow Test Filter

## Status

- State: completed
- Owner: agent
- Created: 2026-07-21
- Last updated: 2026-07-21
- Review date: 2026-07-21
- Next action: none; quick-check excludes `slow` tests and the explicit slow path is documented.
- Blocker: none

## Goal

Keep slow/stress tests available while preventing them from running in the required quick-check/CI
fast path.

## Scope

### In scope

- Inspect current marker usage and quick-check pytest invocation.
- Update quick-check to exclude `slow` tests by default.
- Add regression coverage for the quick-check pytest marker expression.
- Document how to intentionally run slow quota stress checks.

### Out of scope

- Deleting, weakening, or skipping the stress test globally.
- Changing ordinary direct `pytest` semantics outside quick-check.

## Relevant docs

- `docs/architecture/runtime-storage.md`
- `docs/exec-plans/active/a13-postgresql-concurrency-and-ce-scope.md`

## Contracts touched

- Test runner: `scripts/agent/quick_check.py`
- Tests: quick-check command construction and explicit slow/stress invocation
- Docs: fast path vs slow/stress path wording

## Implementation steps

- [x] Add `-m "not slow"` to quick-check's pytest command.
- [x] Add a quick-check unit test proving the marker expression is present.
- [x] Update docs/plans with explicit slow-test commands.
- [x] Validate focused tests and quick-check behavior.

## Validation

- [x] `uv run python -m pytest tests/test_quick_check.py -q`
- [x] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_stress.py -m slow -q`
- [x] `uv run python -m pytest apps/platform-api/tests/test_scenario_runtime_api.py apps/platform-api/tests/test_quota_concurrency_stress.py -m "not slow" -q`
- [x] `uv run python scripts/agent/runner.py validate-docs`
- [x] `uv run python scripts/agent/runner.py generate-docs --check`
- [x] `uv run python scripts/agent/runner.py quick-check`

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-21 | Added `-m "not slow"` to quick-check, pinned the command in a regression test, documented explicit slow quota stress commands, and verified quick-check reports `291 passed, 2 deselected`. | None. |
