# Execution Plan: ANY-503 Adopt Bundle 3 Design System

## Status

- State: active
- Owner: agent
- Created: 2026-09-16
- Last updated: 2026-09-16
- Review date: 2026-09-16
- Next action: run full verification (frontend-check/full-check) and address any findings.
- Blocker: none

## Goal

Port Bundle 3 (the dark-glass/bento design system already used by Payment Portal) once into
`@anytoolai/shared-ui`, so every web product under `apps/web-mirror` inherits real styling by
construction instead of each page/product styling itself. Full ticket text: `plans/ANY-503.md`.

## Design decisions

1. **CSS approach: plain CSS Modules + one global token stylesheet.** No new dependency — the repo
   has zero CSS tooling today (no Tailwind/PostCSS/CSS-in-JS), and Next.js 15 App Router supports
   global CSS and CSS Modules natively.
2. **Token/prose gaps in the upstream source are resolved by narrowing scope, not improvising
   values** (upstream `SKILL.md` names `surfaceNav`/`surfaceModal` tokens that don't exist in
   `tokens.json`; `tokens.json`'s `warning` color has no background/border pair, and — found while
   re-verifying against the live upstream source — `error` has `errorBackground` but no
   `errorBorder` either, only `success` has a full pair). Concretely: no nav/modal surface
   component, no `Toast` warning variant, and the `Toast` error variant's border uses the generic
   `border`/`borderStrong` token rather than an invented `errorBorder`.
3. **Cabinet Grotesk (display font) is not a Google Font** and no licensed file is available in
   this pass. Decision: ship DM Sans/DM Mono via `next/font/google` now, and use a documented
   temporary fallback stack (`"DM Sans", ui-sans-serif, system-ui, sans-serif`) for the headline
   role instead of Cabinet Grotesk. Follow-up debt: self-host a licensed Cabinet Grotesk file via
   `next/font/local` once one is sourced.
4. **Scope addition beyond the ticket's named component list:** `Input`/`Select` are added
   alongside `TextArea`, because `ProposalAIFields` (tone `<select>`, language `<input>`) would
   otherwise stay unstyled after this ticket.
5. **`HandoffConsent.tsx`** (`apps/web-mirror/src/components/HandoffConsent.tsx`, live at
   `/handoff/[handoffToken]`) is a fully-built, non-stub component rendering raw
   `<button>`/`<dl>`/`<p role="alert">` — found during plan review to be missing from the ticket's
   own restyle-target list. Decision: **out of scope for this pass**, tracked as explicit follow-up
   debt below, to keep this diff to the ticket's stated targets (`layout.tsx`, `ProposalAIFields`,
   `ResultView`, `ErrorState`, `ProductRunPage`). `EmailCaptureForm.tsx` and the
   `onboarding`/`paywall`/`r` route pages are still literal placeholder stubs and are correctly out
   of scope.

## Follow-up debt (explicit, not silently dropped)

- Cabinet Grotesk: temporary fallback font stack for headline role; swap to `next/font/local` once
  a licensed file is sourced.
- `Toast` has no `warning` variant (missing token pair upstream).
- No nav/modal surface component (missing token pair upstream).
- `HandoffConsent.tsx` still renders raw unstyled elements — needs its own restyle pass.

## Verification

```
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
pnpm --filter @anytoolai/shared-ui test
pnpm --filter @anytoolai/shared-ui build
pnpm --filter @anytoolai/web-mirror test
pnpm --filter @anytoolai/web-mirror typecheck
pnpm --filter @anytoolai/web-mirror build
```
