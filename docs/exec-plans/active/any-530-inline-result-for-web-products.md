# Execution Plan: ANY-530 Inline "Inputs + Result" Layout For All Web Products

## Status

- State: active
- Owner: agent
- Created: 2026-09-28
- Last updated: 2026-09-28
- Review date: 2026-10-05
- Next action: native-speaker review of the six non-English locales; CI on the PR.
- Blocker: none. Open owner questions have defaults below.

## Goal

Client Update Writer and Brief Decoder show the form and the result on one screen exactly like
ProposalAI (ANY-528): two equal cards side by side on wide screens, stacked on narrow ones; inputs
survive generation; a regeneration keeps the previous result visible and marked; waiting and errors
live in the result card; "Copy" and "New task" share one action group.

## Decisions

- The layout is the runtime's only layout. After migration no product uses the result-only branch,
  so `ProductDefinition.inlineResult` and `hasStartAnother` are removed together with that branch.
  (Kept as a self-contained change so it can be reverted if the owner prefers the flags.)
- `ProductPageShell` always uses the wide shell; there is no per-product switch.
- Message ownership is split. Host (`i18n/messages/*`): `workspace.inputTitle|previousDetails|
  backToInputs|newTask` -- identical for every product. Product, under its `messageScope`:
  `<scope>.resultTitle|placeholder|regenerate` -- the noun differs per product and per Client
  Update Writer mode (update / reply draft / payment request).
- Focus after "New task" stays `textarea, input` (first field). This is now a documented contract in
  `productDefinition.ts` and tested per product/mode; no focus API until a product's first field is
  a `select`.
- Client Update Writer keeps "switching mode = new task" (remount). Open question for the owner:
  keep, block switching while a result is shown, or store values per mode. Default: keep.
- "Equal cards" means equal width (two `1fr` tracks; review #2 replaced ProposalAI's `0.9fr/1.1fr`),
  surface, radius, padding and heading structure, not equal height (`DESIGN.md`: panels stay in
  document flow). The smokes assert the width match.
- Brief Decoder result is embedded: three inner `Card`s become plain sections, section headings
  drop from `h2` to `h3` (the workspace cards own `h2`).

## UI skill notes (`frontend-design`, `ui-ux-pro-max`; design system unchanged)

- Responsive: one column at <=860px, no horizontal scroll, content-driven heights; long brief text
  keeps `min-width: 0; overflow-wrap: anywhere`.
- Headings stay sequential: `h1` product, `h2` per workspace card, `h3` for Brief Decoder parts.
- Touch: the "Back to details" link and both actions keep 44px targets; the action group wraps.
- Focus: "New task" returns focus to the first field; a new result focuses its card heading.
- No new tokens, no decoration; nothing outside `shared-ui` tokens.

## Steps

- [x] Shell: drop the `proposal_ai` special case.
- [x] Messages: move workspace keys to host/scope, migrate ProposalAI, add the two products x 7 locales.
- [x] Runtime: single layout, host `newTask`, remove `inlineResult`/`hasStartAnother`.
- [x] Client Update Writer and Brief Decoder: embedded results with `secondaryAction`.
- [x] Tests: shared inline scenario, per product/mode scenario, updated old assertions.
- [x] Browser smokes: geometry, "New task", headings.
- [x] Docs: `frontend-boundaries.md`, `DESIGN.md`, `add-product-recipe.md`, stale comments.
- [x] `frontend-check`, `validate-docs`.

## Risks

- Machine translations for six locales need native review; `i18n.test.ts` checks structure only.
- Browser smokes are optional in CI; layout regressions on narrow screens are only caught locally.
- The known race at `ProductRunPage.test.tsx` (`scenario_completed` timing) is fixed by #150, not here.

## Verification (2026-09-28)

- `frontend-check` (290 web-mirror tests, typecheck, drift check, build), `validate-docs`,
  `generate-docs --check`, web-mirror lint: green.
- `proposal-ai-smoke` (9), `client-update-writer-smoke` (4), `brief-decoder-smoke` (8) on `dev-up`:
  green, including the new wide (side by side) / narrow (stacked, no horizontal scroll) geometry checks.
- Manual screenshots at 1280 and 390 px for Client Update Writer and Brief Decoder.
