# Execution Plan: ANY-524 Web Pages UI/UX Audit

## Status

- State: active
- Owner: agent
- Created: 2026-09-24
- Last updated: 2026-09-24
- Review date: 2026-09-25
- Next action: merge.
- Blocker: none

## Goal

Run every existing web page of `apps/web-mirror` through the `frontend-design` and
`ui-ux-pro-max` skills, record the findings per page, and fix them in this one change instead of
spawning follow-up tasks.

## Scope

### In scope

- `/products/proposal_ai`, `/products/client_update_writer`, the shared product shell and
  `@anytoolai/shared-ui`.
- `/handoff/[handoffToken]` (`HandoffConsent`).
- Home page `/`, plus host pages `/paywall/[productId]`, `/onboarding/[productId]`, `/r/[artifactId]` and the 404
  page: given a heading and a `<main>` landmark only. Their real content belongs to the tickets
  that replace them.

### Out of scope

- Palette, fonts, radii and tokens of Bundle 3 (`docs/exec-plans/active/any-503-adopt-bundle3-design-system.md`).
- Localization of `HandoffConsent` (English only, as before).
- Brief Decoder: its web page is not on `main` yet (it lands with ANY-248) and must be audited
  against this matrix when it does.
- Products that have no bundle or page yet (Client Message Decoder, Scope Creep Guard, Send-Ready).
- New tokens, permanent a11y automation and screenshot regression tests (new dependencies).

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/exec-plans/active/any-503-adopt-bundle3-design-system.md`

## Contracts touched

- API: none.
- DB: none.
- Config: none.
- Events: none.
- Frontend: `ProductPageShell` owns the single `<main>` when a product runs inside it;
  `ProductRunPage` renders a `<div>` there and stays its own `<main>` standalone. `HandoffConsent`
  renders user-facing status copy and a localized expiry date instead of wire values.

## Reconciling the skills with Bundle 3

Bundle 3 is fixed, so palette, fonts, radii and tokens are not audited. `frontend-design` was
applied to layout, hierarchy, copy, states and content components; `ui-ux-pro-max` to its
priority 1-10 checklist (accessibility, touch, layout, typography, animation, forms, navigation).
Anything that would need a new token is recorded below as an accepted deviation.

## Audit matrix

| Page / state | Skill | Finding | Resolution |
|---|---|---|---|
| Shared: buttons, fields | ui-ux-pro-max (touch) | Buttons about 40px high, no minimum target | Fixed: `min-height: 44px` on buttons and fields |
| Shared: labels | ui-ux-pro-max (typography) | Labels 11px, below the 12px minimum | Fixed: 12px |
| Shared: spinner, transitions | ui-ux-pro-max (animation) | No reduced-motion handling; the spinner only slowed down | Fixed: global reduced-motion rule, spinner static |
| Shared: page padding | ui-ux-pro-max (layout) | 40px/20px padding kept on phones | Fixed: 24px/16px at 520px and below |
| Shared: document | ui-ux-pro-max (navigation) | No page `<title>` | Fixed: `AnytoolAI` |
| Shared: links | frontend-design | Default browser link colour unreadable on the dark background | Fixed: accent colour |
| Shared: result and error cards | frontend-design | Text, button and message stacked flush; unbounded line length; copy failure was a bare `<p>` | Fixed: card spacing, 70ch line cap, copy failure shown as `Toast` |
| ProposalAI: form | frontend-design | "Proposal style" legend looked like body text, unlike the labels | Fixed: legend uses label style |
| Client Update Writer: form | frontend-design | Label, field and error were separate grid children, so each label sat 24px from its field | Fixed: one group per field, error styling |
| Client Update Writer: modes | frontend-design, ui-ux-pro-max | Bare native radios; selector stretched to 1160px above an 820px column; no gap under the heading | Fixed: chip switcher aligned to the column, DOM and accessible names unchanged |
| Client Update Writer: landmarks | ui-ux-pro-max (accessibility) | Heading and mode selector sat outside `<main>` | Fixed: the shell owns `<main>`; covered by a test |
| Handoff: layout | frontend-design | Unstyled raw buttons and lists, loading/error states outside `<main>`, no `<h1>` | Fixed: shared `Button`/`Card`/`Toast`, every state inside `<main>` with a heading |
| Handoff: small screens | ui-ux-pro-max (layout) | Card wider than a 375px viewport; a long preview key widened the page | Fixed: `border-box`, label column capped at 40%, labels wrap |
| Handoff: values | frontend-design (copy) | Raw status enum and ISO timestamp | Fixed: status copy map (exhaustive over `HandoffStatus`), expiry in `<time>` with a locale-formatted date |
| `/` | frontend-design, ui-ux-pro-max | Bare list of links; English only | Fixed: hero with the Bundle 3 headline gradient, bento cards with a sample of each tool's output, one tab stop per card with a 2px focus ring, language selector and copy in all 7 locales (`homeMessages`, covered by the i18n parity tests) |
| `/paywall`, `/onboarding`, `/r`, 404 | frontend-design, ui-ux-pro-max | One-line placeholders without a heading; default Next 404 | Fixed: heading and `<main>`; themed 404. English only; real content stays with the tickets that replace them |
| Shared: disabled text | ui-ux-pro-max (colour) | `--color-text-disabled` is a 30% alpha token | Accepted: disabled controls are exempt from contrast and the token is fixed by Bundle 3 |
| Shared: headings | frontend-design | `h2`/`h3` have no size, Cabinet Grotesk is loaded at weight 900 only | Accepted: no `h2`/`h3` is rendered; the weight follows the Fontshare licence decision in ANY-503 |
| Shared: toast | ui-ux-pro-max | No warning variant, error border reuses the generic border | Accepted: Bundle 3 has no warning/error border tokens |
| ProposalAI: chip grid | ui-ux-pro-max (layout) | Collapses at 640px, Bundle 3 names 860px | Accepted: three chips still fit the 820px column; unchanged |
| Handoff: copy | frontend-design | Text is English only | Accepted: out of scope, see above |

## Implementation steps

- [x] Audit each page against both skills and fill the matrix.
- [x] Fix shared-ui and shell issues.
- [x] Restyle Client Update Writer fields and mode switcher.
- [x] Restyle `HandoffConsent`, map status and expiry, keep the smoke selectors.
- [x] Give host pages and the 404 a heading and landmark.
- [x] Re-run the three web smokes on the final head.

## Validation

- [x] `python scripts/agent/runner.py frontend-check`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] Production build (`next build` + `next start`) inspected in Chrome and Playwright at 375, 390
  and 1280px, against the real `dev-up` backend for both products, and against a real handoff token
  for the consent page.
- [x] `proposal-ai-smoke` (8), `client-update-writer-smoke` (3), `client-handoff-smoke` (2) on the final head.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-24 | Fix findings in this change instead of filing follow-up tasks | Requested by the ticket owner |
| 2026-09-24 | Duplicate the chip styles in the Client Update Writer CSS module | Two consumers only; move into shared-ui when a third appears |
| 2026-09-24 | Show the handoff expiry with the browser locale | The consent page is not inside the product locale provider and has no translations yet |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-24 | Audit done, fixes applied, code-review findings addressed, smokes green | Merge |

## Open questions

- Not done in this pass: a keyboard-only walkthrough and an automated axe run. Both would need
  tooling that is not in the repository.

## Follow-up debt

- Audit Brief Decoder against the matrix when ANY-248 lands.
- Localize `HandoffConsent` and give it real target details once a product-to-product handoff exists.
