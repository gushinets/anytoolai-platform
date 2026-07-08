# Execution Plan: Provider Event Token Usage Sanitizer Fix

## Status

- State: completed
- Owner: agent
- Created: 2026-07-02
- Last updated: 2026-07-02

## Goal

Keep provider event usage counters numeric in persisted event properties without weakening secret
redaction for API tokens, bearer tokens, cookies, or credentials.

## Scope

### In scope

- Inspect provider event emission and event property sanitization.
- Add a narrow safe path for usage counter keys such as `total_tokens`.
- Prove in tests that numeric usage counters remain numeric while secret-like token fields stay
  redacted.

### Out of scope

- Broad event taxonomy changes.
- Changing unrelated provider-call persistence rules.

## Relevant docs

- `AGENTS.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/provider-gateway.md`

## Contracts touched

- Events: provider event property sanitization and success payload fields
- Runtime: provider success event emission path

## Implementation steps

- [x] Patch the event sanitizer with a narrow allowlist for safe numeric usage counters.
- [x] Update provider event tests to assert numeric usage counters are preserved.
- [x] Run the requested provider/event checks and quick-check.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py -q`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-02 | Prefer a narrow sanitizer allowlist over renaming event fields. | `total_tokens` is already a useful audit/analytics name; the bug is the over-broad redaction rule, not the event taxonomy itself. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-02 | Traced the issue to `events/emitter.py`, where any key containing `token` is redacted, including safe counters like `total_tokens`. | Add a numeric allowlist for usage counters and update provider event tests. |
| 2026-07-02 | Added a narrow allowlist for numeric usage counters (`input_tokens`, `output_tokens`, `total_tokens`), updated event tests to keep those numeric while `token_value` remains redacted, and passed the requested test slice plus quick-check. | No further work for this fix. |
