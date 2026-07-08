# Execution Plan: Weekly Doc Gardening

## Status

- State: active
- Owner: agent
- Last run: 2026-07-08

## Goal

Keep repository knowledge aligned with code behavior.

## Tasks

- [x] Check docs/index links.
- [x] Check architecture docs against current tests.
- [x] Update `docs/quality-score.md`.
- [x] Update `docs/tech-debt-tracker.md`.
- [x] Move completed execution plans.
- [x] Open targeted cleanup tasks for stale docs.

## 2026-07-08 Run Notes

- `docs/index.md` local file targets passed.
- Architecture docs are aligned with the current validation surface: `scripts/agent/validate_architecture.py`, `tests/architecture/*`, and focused runtime tests enforce product, provider, event, and LLM boundaries.
- Moved active plans marked `State: completed` to `docs/exec-plans/completed/`.
- Opened `docs/exec-plans/active/generated-doc-refresh-cadence.md` for generated-doc freshness and OpenAPI helper cleanup.
- Handoff and CE/web surfaces remain intentionally thin and are reflected in the quality/debt trackers.
- Quick-check initially failed because architecture tests scanned an ignored `tmp/review-any50-a08` review snapshot; the provider-boundary test skip list now excludes `tmp/`.

## Validation

- [x] `just doctor`
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/quick_check.py`
