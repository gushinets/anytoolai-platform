# Execution Plan: Resolve CodeQL findings #1-#7 (ANY-675)

## Status

- State: active
- Owner: agent
- Linear: ANY-675
- Created: 2026-10-21
- Last updated: 2026-10-21
- Review date: 2026-10-28
- Next action: after merge, confirm alerts #1-#7 are `fixed` on `main` and fill the Result column below.
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

## Alert outcomes

State on 2026-10-21: every alert is still `open` on `main` (the fix is not merged); CodeQL on this PR
(Python, JavaScript/TypeScript, Actions) passed for `dfb1d423`
([run](https://github.com/gushinets/anytoolai-platform/actions/runs/39564174775)) and reports no new
alerts. The PR merge ref has no open alerts, but that does not prove each older alert is resolved:
that is verified only by the `main` scan after merge.

| Alert | Rule | Disposition | Result |
| -- | -- | -- | -- |
| #1 | missing-workflow-permissions | fix: `docs.yml` permissions | pending `main` scan |
| #2 | missing-workflow-permissions | fix: `frontend.yml` permissions | pending `main` scan |
| #3 | polynomial-redos | fix: alphabet check + length bound before trimming | pending `main` scan |
| #4 | incomplete-url-substring-sanitization | fix: exact assertions (false positive by meaning) | pending `main` scan |
| #5 | incomplete-url-substring-sanitization | fix: exact assertions (false positive by meaning) | pending `main` scan |
| #6 | incomplete-url-substring-sanitization | fix: exact assertions (false positive by meaning) | pending `main` scan |
| #7 | incomplete-url-substring-sanitization | fix: exact assertions (false positive by meaning) | pending `main` scan |

After merge: run `gh api repos/gushinets/anytoolai-platform/code-scanning/alerts/<n>` for each alert,
record `fixed` plus the `main` CodeQL run link here and in the PR, then move this plan to `completed/`.
If any of #4-#7 stays open, dismiss only that alert as a false positive with the code link.
