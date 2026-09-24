# ANY-523: product title contract review

## Status

- State: completed
- Owner: agent
- Created: 2026-09-24
- Last updated: 2026-09-24

## Goal

Require every registered product to provide a localized `title`, which the host page shell renders.

## Steps

1. Verify the registry, locale message type, and translation tests against the review finding.
2. Strengthen the registry message type and check registered titles in every locale.
3. Run focused web typecheck/tests and relevant repository validation; push the fix to PR #143 and reply in the review thread.

## Result

- The registry type requires `title` in every locale; the generic test helper preserves the supplied message shape.
- Translation tests assert that each registered title is nonempty.
- Web typecheck, 227 tests, lint, docs and architecture validation passed.
