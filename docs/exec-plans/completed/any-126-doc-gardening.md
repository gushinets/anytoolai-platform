# Execution Plan: ANY-126 Documentation Gardening

## Status

- State: completed
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: None; PR #25 merged to `main`.
- Blocker: None.
- Linear: `ANY-126`

## Goal

Make repository documentation and execution-plan placement accurately describe the current
MVP-A/MVP-B implementation state.

## Scope

### In scope

- Audit all active/completed execution plans and normalize status metadata.
- Move only verified completed plans to `docs/exec-plans/completed/`.
- Fix conclusive link, command, path, architecture, and implementation-status drift.
- Update quality and debt records with current evidence.
- Record unresolved discrepancies rather than inventing decisions.

### Out of scope

- Implementing unfinished plan tasks or MVP domain behavior.
- Hand-editing generated documents whose generators are incomplete.
- Changing accepted product scope or architecture decisions.

## Relevant docs

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/agent/codex-operating-model.md`

## Implementation steps

- [x] Inventory plan state/location and verify completed claims.
- [x] Move verified completed plans and normalize ambiguous active plans.
- [x] Audit indexed repository documentation against code, tests, configs, and ADRs.
- [x] Fix conclusive discrepancies and record unresolved decisions.
- [x] Update quality score, debt tracker, weekly gardening notes, and parent plan.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [ ] `python scripts/agent/quick_check.py`
- [x] Manual indexed-link and plan-location audit.

`quick_check.py` reached 231 passing tests and one pre-existing failure:
`test_gateway_request_cancellation_persists_failed_provider_call` observes the two provider events
in the reverse order when timestamps collide. The focused rerun reproduces it; ANY-126 changes only
documentation.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-15 | Use repository evidence before moving any plan. | A status word alone must not hide unfinished acceptance criteria. |
| 2026-07-15 | Leave generated-doc remediation to `ANY-128`. | Avoid hand-editing outputs before deterministic generation exists. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-15 | Created plan after doctor passed through the documented Python fallback. | Inventory active/completed plans. |
| 2026-07-15 | Archived 33 verified plans, normalized the four remaining active plans, corrected conclusive drift, and updated quality/debt records. | Review and publish the child PR after GitHub authentication is restored. |
| 2026-07-15 | PR #25 merged and subsequent harness work resolved the recorded ordering regression. | Archive this completed plan. |

## Open questions

- None.

## Follow-up debt

- Mechanical plan-state/link enforcement belongs to `ANY-128`.
