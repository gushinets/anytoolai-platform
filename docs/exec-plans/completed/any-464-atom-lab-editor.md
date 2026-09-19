# Execution Plan: ANY-464 Atom Lab contract editor

## Status

- State: completed
- Owner: agent
- Created: 2026-09-19
- Last updated: 2026-09-19
- Review date: 2026-09-19
- Next action: none; implementation and verification are complete.
- Blocker: aggregate frontend-check has 62 pre-existing local Node 26 `web-mirror` failures because
  `window.localStorage` is unavailable; the Atom Lab package, lint, typecheck, drift check, and
  build pass.

## Goal

Deliver the protected Russian Atom Lab editor for all eleven catalog atoms without changing the
catalog or run API contracts. The browser preserves one exact JSON-compatible draft across form and
JSON modes, exposes every current schema field, keeps prompt edits local, and never persists the
access code.

## Scope

### In scope

- Expand the existing `platform-api` static Atom Lab shell and assets.
- Render atom navigation, purpose, transformation, readonly input/output schemas, input/prompt tabs,
  schema-driven form controls, raw JSON editing, example restore, and base-prompt restore.
- Preserve omission separately from `null`, empty string, `false`, and zero.
- Keep invalid JSON verbatim until corrected and prevent actions that require a valid payload.
- Warn before dirty atom/example/prompt-reset navigation.
- Add runnable browser-state coverage for all eleven current catalog examples and schema features.
- Keep the access code in module memory only and render catalog/server strings through safe DOM APIs.

### Out of scope

- Run submission, model/reasoning selection, result rendering, presets, and history UI (ANY-465/466).
- Backend contract, atom schema, provider, or runtime changes.
- A new frontend deployment or framework.

## Relevant docs

- `docs/superpowers/specs/2026-09-09-atom-lab-design.md`
- `docs/exec-plans/active/atom-lab-v1.md`
- `docs/architecture/frontend-boundaries.md`

## Contracts touched

- API: no JSON contract changes; replace the Atom Lab script asset route with `atom_lab.mjs`.
- DB: none.
- Config: none.
- Events: none.
- Frontend: static Atom Lab shell and exact JSON-compatible draft state.

## Implementation steps

- [x] Add failing page/assets and browser-state tests.
- [x] Implement the static HTML/CSS shell and schema-driven draft editor.
- [x] Cover all eleven current input contracts, dirty navigation, safe rendering, and path errors.
- [x] Complete canonical repository validation and final review.

## Validation

- [x] `python3 scripts/agent/runner.py quick-check` — 1722 passed, 479 deselected.
- [ ] `python3 scripts/agent/runner.py frontend-check` — lint and typecheck pass, then 62 pre-existing Node 26 `web-mirror` tests fail because `window.localStorage` is unavailable; focused lint, typecheck, build, and Atom Lab tests pass.
- [x] `pnpm --filter @anytoolai/atom-lab-browser-tests test` — 17 passed.
- [x] `pnpm --filter @anytoolai/atom-lab-browser-tests browser` — Chromium interaction passed at 375 px.
- [x] `pnpm --filter @anytoolai/atom-lab-browser-tests lint`.
- [x] `pnpm -r typecheck` and `pnpm -r build`.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-19 | Use the dependency-free browser-state harness pattern. | It matches the existing stakeholder-demo browser harness and avoids adding a UI framework or test dependency. |
| 2026-09-19 | Render closed-schema unknown fields readably with a removal control. | Invalid JSON must remain recoverable in form mode instead of becoming visible only to technical users. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-19 | Baseline quick-check passed: 1722 passed, 479 deselected. | Implement with TDD. |
| 2026-09-19 | Focused API tests, 17 browser-state tests, Chromium interaction, lint, typecheck, OpenAPI drift, build, and quick-check passed. Independent review findings were fixed and regression-covered. | Complete. |

## Open questions

None.

## Follow-up debt

- The system `pnpm` 11 wrapper hangs under local Node 26; validation uses repository-pinned pnpm
  10.34.1 through `npm exec`.
- Node 26 `web-mirror` storage behavior keeps the unmodified aggregate frontend-check red locally;
  all 62 failures are outside ANY-464 files.
