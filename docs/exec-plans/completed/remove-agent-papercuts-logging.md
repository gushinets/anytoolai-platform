# Execution Plan: Remove Agent Papercuts Logging

## Status

- State: completed
- Owner: agent
- Created: 2026-08-03
- Last updated: 2026-08-03
- Review date: 2026-08-03
- Next action: none; implementation and clean-worktree validation are complete.
- Blocker: none

## Goal

Remove the repository-level papercut logging workflow so agents are no longer instructed to append
minor workflow friction to a shared `PAPERCUTS.md` file.

## Scope

### In scope

- Root agent instructions in `AGENTS.md`.
- The tracked repository-root `PAPERCUTS.md` artifact.
- Documentation index entries that advertise papercut logging.
- Weekly documentation-gardening tasks that review or promote papercut entries.
- Active execution-plan references that still direct future papercut-log maintenance.

### Out of scope

- Runtime code, APIs, schemas, migrations, generated artifacts, and product behavior.
- Converting historical papercut entries into bugs, tech debt, or Linear issues.
- Rewriting completed execution-plan history unless a completed plan is still linked as current
  operating guidance.

## Relevant docs

- `../../index.md`
- `../../agent/harness-engineering-map.md`
- `../../agent/codex-operating-model.md`
- `../../exec-plans/completed/any-131-agent-papercuts.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Remove the `## Log papercuts` section from root `AGENTS.md`.
- [x] Delete the tracked root `PAPERCUTS.md` file.
- [x] Remove the `PAPERCUTS.md` maintenance entry from `docs/index.md`.
- [x] Update `docs/exec-plans/active/weekly-doc-gardening.md` so the recurring task no longer
  reviews papercut entries.
- [x] Search `AGENTS.md`, `docs/`, and other tracked Markdown for `PAPERCUTS`, `papercut`, and
  `papercuts`; remove or update only live guidance and active maintenance references.
- [ ] Leave historical completed-plan references intact when they only describe past work.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py quick-check`
- [x] Manual check: no active agent instruction tells agents to log papercuts.
- [x] Manual check: no active maintenance task refers to reviewing `PAPERCUTS.md`.
- [x] Manual check: completed-plan history remains understandable after the log artifact is removed.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-03 | Delete the tracked `PAPERCUTS.md` artifact instead of leaving an empty retired log. | Keeping the file would preserve the visible workflow and invite future entries. |
| 2026-08-03 | Preserve historical references that do not direct future work. | Completed execution plans should remain accurate records of past repository state. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-03 | Plan created after finding current papercut references in `AGENTS.md`, `docs/index.md`, weekly documentation gardening, the tracked root log, and execution-plan history. | Implement the scoped documentation removal and run validation. |
| 2026-08-03 | Removed live logging guidance, deleted the tracked log, and removed weekly gardening/index references. | Run search/manual checks and repository validation. |
| 2026-08-03 | Search/manual checks passed. `doctor` passed. `validate-docs` and `quick-check` fail on pre-existing untracked docs validation issues in `docs/reviews/mvp-a-p0-review.md` and `docs/exec-plans/active/any-150-idempotent-scenario-start-review.md`. | Resolve or remove the unrelated untracked docs files, then rerun validation. |
| 2026-08-03 | Clean detached worktree validation at the PR commit passed `doctor`, `validate-docs`, and `quick-check`; `quick-check` reported 215 passed and 266 deselected. | None. |

## Open questions

None.

## Follow-up debt

None.
