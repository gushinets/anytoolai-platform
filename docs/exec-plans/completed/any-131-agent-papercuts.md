# Execution Plan: ANY-131 Agent Papercut Logging

## Status

- State: completed
- Owner: agent
- Created: 2026-07-16
- Last updated: 2026-07-16
- Review date: 2026-07-16
- Next action: none; implementation and validation are complete.
- Blocker: none

## Goal

Give agents a shared, actionable, deduplicated, and privacy-safe place to record minor repository and
tooling friction without interrupting their main task.

## Scope

### In scope

- Root agent guidance.
- A tracked repository-root papercut log and entry template.
- Documentation discovery and recurring gardening.

### Out of scope

- APIs, schemas, runtime code, generated artifacts, and product behavior.
- Automated issue creation or papercut collection.

## Relevant docs

- `../../agent/harness-engineering-map.md`
- `../../agent/codex-operating-model.md`
- `../../adr/0003-short-agents-md.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Add concise papercut guidance to root `AGENTS.md`.
- [x] Create and index the shared `PAPERCUTS.md` template without fabricated entries.
- [x] Add papercut review to weekly documentation gardening.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-16 | Keep the log at repository root and track it in Git. | All agents need one shared history, including from nested directories. |
| 2026-07-16 | Use documentation gardening for lightweight triage. | Existing maintenance work can promote recurring friction without adding automation. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-16 | Plan created and repository doctor passed. | Implement guidance and run validation. |
| 2026-07-16 | Guidance, shared log, index, and gardening lifecycle added; documentation validation and 248 baseline tests passed. | None. |

## Open questions

None.

## Follow-up debt

None.
