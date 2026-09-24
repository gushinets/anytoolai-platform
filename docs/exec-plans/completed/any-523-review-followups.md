# ANY-523 review followups

## Status

- State: completed
- Owner: agent
- Created: 2026-09-24
- Last updated: 2026-09-24
- Review date: 2026-09-25
- Next action: none
- Blocker: none

## Goal

Address PR #143 review comments without changing the approved ProposalAI layout.

## Work

1. Put the bundled Cyrillic font after DM Sans in every shared body-font declaration.
2. Return selector ownership to ProductPageShell while keeping it beside the product title.
3. Verify an arbitrary registered product still receives a selector, and run frontend checks.

## Result

- DM Sans, bundled Noto Sans Cyrillic, and the system fallback now form the shared body, heading, and label font stacks.
- The shell owns the title and selector for every registered product; the runtime omits its duplicate when hosted there.
- Added a regression check for an arbitrary product component and verified a single selector on ProposalAI.
- Typecheck, 226 web tests, 48 shared UI tests, lint, production build, docs and architecture validation passed. Browser inspection confirmed the layout and computed font stacks.
