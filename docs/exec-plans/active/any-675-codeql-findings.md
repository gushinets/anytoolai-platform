# Execution Plan: Resolve CodeQL findings #1-#7 (ANY-675)

## Status

- State: active
- Owner: agent
- Linear: ANY-675
- Created: 2026-10-21
- Last updated: 2026-10-21
- Review date: 2026-10-28
- Next action: open the PR, then record the outcome table for alerts #1-#7 after the repeat CodeQL run.
- Blocker: none

## Goal

Close the seven first-run CodeQL alerts without changing CodeQL configuration or excluding files/rules.

## Scope

- #1, #2: `permissions: contents: read` in `docs.yml` and `frontend.yml`.
- #3: `_decode_urlsafe_base64` (shared by run, preset and version cursors) drops the regex for an
  alphabet check and enforces one length bound (`_CURSOR_MAX_LENGTH`) before any per-character
  work. Preset/version endpoints keep returning 422 `invalid_cursor` (no `Query(max_length=...)`,
  which would change the error contract).
- #4-#7: architecture test assertions use exact list equality instead of substring `any(...)`,
  keeping detection coverage for folded provider hosts in JS/Python and for imports from the
  allowed provider boundary.

## Verification

- Regression tests for long malformed cursors on runs, presets and versions.
- Architecture tests pass; disabling the folded-host resolver makes the three tests fail.
- `python scripts/agent/runner.py full-check` and required CI checks.
- Repeat CodeQL: record each alert's outcome with links in the PR.
