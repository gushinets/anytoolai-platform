# Execution Plan: Product title and language in one row

## Status

- State: completed
- Owner: agent
- Created: 2026-09-24
- Last updated: 2026-09-24
- Review date: 2026-09-25
- Next action: none
- Blocker: none

## Goal

Place the product title on the left and the compact UI-language selector on the right without adding a separate row above the product.

## Scope

- Keep one host-owned selector for every product and for loading/error states.
- Align the selector with the title in the shared runtime header; wrap gracefully at narrow widths.
- Update the frontend ownership doc and rebuild the running web page.

## Validation

- `pnpm --filter @anytoolai/web-mirror test`
- `pnpm --filter @anytoolai/web-mirror build`
- `python scripts/agent/runner.py validate-docs`
- Browser inspection at desktop and narrow widths.

## Result

- Shared `ProductRunPage` now places the title and `LanguageSwitcher` in one flex row. Narrow screens wrap the selector to the right below the title without horizontal overflow.
- Loading and boot-error states retain one selector.
- Web build, lint, 224 tests, and docs validation passed. The rebuilt page is running on port 3100 and was visually checked in the browser.
