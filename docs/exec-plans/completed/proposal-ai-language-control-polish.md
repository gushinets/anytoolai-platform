# Execution Plan: Proposal AI language control polish

## Status

- State: completed
- Owner: agent
- Created: 2026-09-24
- Last updated: 2026-09-24
- Review date: 2026-09-25
- Next action: none
- Blocker: none

## Goal

Fit the shared UI-language selector into the product column, make its native options readable, and preserve DM Sans typography in Russian.

## Scope

- Compact right-aligned selector above the product heading on desktop and mobile.
- Dark, high-contrast native option menu using existing tokens.
- Cyrillic subset for the body font.
- Rebuild and visually verify the running Proposal AI page.

## Validation

- `pnpm --filter @anytoolai/web-mirror test`
- `pnpm --filter @anytoolai/web-mirror build`
- `python scripts/agent/runner.py validate-docs`
- Browser checks at current and narrow widths, including the native menu and Russian locale.

## Result

- The shared language selector is 168px wide and right-aligned to the 820px product column.
- Native options use dark colors from shared tokens and the selector opts into dark system chrome.
- DM Sans remains the Latin body font; Noto Sans supplies Cyrillic glyphs because DM Sans has no Cyrillic subset.
- `web-mirror` build passed; 224 web tests and 48 shared-ui tests passed; web lint and docs validation passed.
- The rebuilt page is running on port 3100. Browser checks covered English, Russian, and a 390px viewport without horizontal overflow.
