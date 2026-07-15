# Execution Plan: Windows Quick-Check Maturin Bootstrap

## Status

- State: completed
- Owner: agent
- Created: 2026-07-12
- Last updated: 2026-07-12

## Goal

Quick-check can install the editable monorepo on Windows when LiteLLM requires Maturin during its
non-isolated build.

## Scope

### In scope

- Quick-check bootstrap build requirements.
- Focused bootstrap command regression coverage.
- Task and handoff records.

### Out of scope

- LiteLLM runtime behavior or version changes.
- CI workflow-only setup.
- Application package runtime dependency changes.

## Relevant docs

- `docs/agent/harness-engineering-map.md`
- `docs/architecture/llm-runtime.md`

## Implementation steps

- [x] Inspect quick-check bootstrap and LiteLLM dependency flow.
- [x] Add Maturin to the canonical non-isolated build bootstrap.
- [x] Update bootstrap command coverage.
- [x] Run focused and full quick-check validation.
- [x] Record handoff and task summary.

## Validation

- [x] `python -m pytest tests/test_quick_check.py -q` (run in the managed quick-check environment)
- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-12 | Install Maturin in quick-check before the editable root install. | Quick-check explicitly disables build isolation, so its managed environment must contain LiteLLM's build backend on Windows. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-12 | Found the failing command: the root editable install follows a build-tool-only install that lacks Maturin. | Add Maturin to that canonical list and verify bootstrap commands. |
| 2026-07-12 | Added Maturin before the non-isolated editable install. | Direct and runner quick-check both installed Maturin and passed all 203 checks on Windows. |
