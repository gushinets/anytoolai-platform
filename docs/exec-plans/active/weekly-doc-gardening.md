# Execution Plan: Weekly Doc Gardening

## Status

- State: active
- Owner: agent
- Created: 2026-07-08
- Last updated: 2026-08-05
- Review date: 2026-08-05
- Last run: 2026-08-05
- Next action: repeat the inventory and discrepancy review after the next MVP feature merge.
- Blocker: none

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

## 2026-07-15 Run Notes

- Inventoried every plan in `active/` and `completed/`; implementation-complete plans were
  verified against goals, tests, and merged history before archival.
- Retained the ANY-122 transition, this recurring gardening plan, and the MVP delivery map as the
  authoritative active plans.
- Marked older architecture audits as superseded by current repository documentation and ANY-126.
- Recorded generated-document freshness under ANY-128 instead of keeping an overlapping plan active.
- Rechecked indexed links and corrected stale repository orientation, command evidence, and provider
  gateway paths.
- Recorded truthful-CI, worktree isolation, structured diagnostics, and placeholder-smoke gaps in
  the quality and debt trackers.

## 2026-08-05 Run Notes

- Inventoried active/completed plans against current code, tests, and merged history; archived 17
  verified completed plans covering A10/A11 recovery and identity follow-ups, A13 quota work,
  artifact correlation, CE client foundations, migrations, test alignment, and papercut removal.
- Reconciled each archived record so completed means its defined implementation scope is merged
  and supported by current regressions or canonical CI evidence. Separately owned work, including
  ANY-171's real CE quota/start/polling integration, remains follow-up debt rather than an open
  completion criterion in the archived plan.
- Kept genuinely unfinished migration, quota-conflict, handoff, worker external-follow-up,
  production Compose, delivery-map, SQLite-eradication, and recurring gardening plans active.
- Corrected stale kernel-smoke, CE-kit, provider retry, quality-score, and debt-tracker claims.
- Reopened the SQLite-eradication discrepancy in its existing plan after finding current SQLite
  harnesses, migration branches, and worker fallbacks that conflict with its zero-SQLite goal.
- Extended architecture scan exclusions for `.tmp/` review snapshots after quick-check proved they
  could create false import-boundary failures.
- Recorded locally skipped PostgreSQL commands as historical non-evidence and cited PR #54's
  successful canonical `postgresql-check` for production-dialect proof. The zero-SQLite
  eradication plan remains active because current repository behavior still conflicts with its goal.

## 2026-08-05 Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check`
