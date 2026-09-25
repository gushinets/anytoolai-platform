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
  renders localized, user-facing status copy and an expiry date formatted for the active locale
  instead of wire values; it must be rendered inside a `LocaleProvider` (the handoff route provides one).

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
| Shared: document | ui-ux-pro-max (navigation) | No page `<title>`, then one identical title for every route | Fixed: site title template `%s · AnytoolAI`; each route names itself (product pages via a server layout that reads the registry, handoff via its own layout, paywall/onboarding/result/404 via `metadata`); `routeTitles.test.ts` pins the metadata and `proposal-ai-smoke` asserts the rendered `<title>` in a real browser, after the network settles, for a product page and both kinds of 404 (unmatched route, unknown product). The unknown-product layout states `Page not found` itself: Next re-applies segment metadata after hydration and dropped the not-found title there |
| Shared: links | frontend-design | Default browser link colour unreadable on the dark background | Fixed: accent colour |
| Shared: result and error cards | frontend-design | Text, button and message stacked flush; unbounded line length; copy failure was a bare `<p>` | Fixed: card spacing, 70ch line cap, copy failure shown as `Toast` |
| Product pages: navigation | frontend-design, ui-ux-pro-max (navigation) | No way back to the tool list except the browser or a known URL | Fixed: "All tools" link in a `<nav>` above `<main>`. While a run is in flight it shows a hover/focus tooltip (Escape dismisses) that leaving loses the result and the quota is not restored; on touch, where a tap would navigate in the same gesture, the first tap reveals the warning, a tap anywhere else hides it again and the second tap on the link leaves. The link is never blocked. The busy state comes from `ProductRunPage` through `ProductShellContext`. A tool switcher menu is not built: the list would come from the registry when the product count needs it |
| ProposalAI: form | frontend-design | "Proposal style" legend looked like body text, unlike the labels | Fixed: legend uses label style |
| Client Update Writer: form | frontend-design | Label, field and error were separate grid children, so each label sat 24px from its field | Fixed: one group per field, error styling, each error tied to its control with `aria-describedby` (test added) |
| Client Update Writer: modes | frontend-design, ui-ux-pro-max | Bare native radios; selector stretched to 1160px above an 820px column; no gap under the heading | Fixed: chip switcher aligned to the column, DOM and accessible names unchanged |
| Client Update Writer: landmarks | ui-ux-pro-max (accessibility) | Heading and mode selector sat outside `<main>` | Fixed: the shell owns `<main>`; covered by a test |
| `/`: sample panel | ui-ux-pro-max (colour) | A raw `rgba(15, 12, 41, 0.45)` in the page CSS, outside the fixed Bundle 3 tokens | Fixed: `--color-background` |
| Handoff: layout | frontend-design | Unstyled raw buttons and lists, loading/error states outside `<main>`, no `<h1>` | Fixed: shared `Button`/`Card`/`Toast`, every state inside `<main>` with an `<h1>` that keeps the global Display size |
| Handoff: pending action | ui-ux-pro-max (touch, forms & feedback) | Accept/Decline only became disabled while the request ran; no spinner, `aria-busy` or announcement, and a slow accept can also refetch | Fixed: the clicked button uses the shared `loading` state and a `role="status"` line ("Accepting…" / "Declining…") announces it; test with a held response |
| Handoff: small screens | ui-ux-pro-max (layout) | Card wider than a 375px viewport; a long preview key widened the page | Fixed: `border-box`, label column capped at 40%, labels wrap |
| Handoff: values | frontend-design (copy) | Raw status enum and ISO timestamp | Fixed: status copy map (exhaustive over `HandoffStatus`), expiry in `<time>` with a locale-formatted date |
| `/` | frontend-design, ui-ux-pro-max | Bare list of links; English only | Fixed: hero with the Bundle 3 headline gradient, bento cards with a sample of each tool's output, one tab stop per card with a 2px focus ring, the sample output readable by screen readers (only the duplicate "Open tool" is hidden), language selector and copy in all 7 locales (`homeMessages`, covered by the i18n parity tests) |
| `/paywall`, `/onboarding`, `/r`, 404 | frontend-design, ui-ux-pro-max | One-line placeholders without a heading; default Next 404 | Fixed: heading and `<main>`; themed 404. English only; real content stays with the tickets that replace them |
| Shared: disabled text | ui-ux-pro-max (colour) | `--color-text-disabled` is a 30% alpha token | Rejected, not a defect: WCAG exempts disabled controls from the contrast requirement and the value is a fixed Bundle 3 token |
| Shared: headings | frontend-design | Cabinet Grotesk is loaded at weight 900 only, so Display (900, 44-56px) is the one heading role available; Section (800, 26-36px) is not | Rejected, contradicts Bundle 3: the roles are fixed and ANY-503's Fontshare decision limits delivery to weight 900; `h1` stays Display everywhere, including the home hero (capped at 56px) |
| `/`: card titles | frontend-design, ui-ux-pro-max (typography) | Card titles are `h2`; Cabinet 900 at a card-title size would pair the Display weight with a Section size | Fixed: `h2` card titles use the approved body face (DM Sans 700, 24px) instead of a mismatched heading role; `layout.test.ts` pins the hero and card-title rules |
| Shared: toast | ui-ux-pro-max | No warning variant, error border reuses the generic border | Rejected, contradicts Bundle 3 and has no caller: nothing in the app renders a warning message, so a warning variant would be dead code, and the error border uses the generic Bundle 3 border token by ANY-503's decision |
| Chip grids (ProposalAI tone, Client Update Writer modes) | ui-ux-pro-max (layout) | Collapsed at 640px, Bundle 3 names 860px | Fixed: both collapse to one column at 860px |
| Handoff: copy | frontend-design | Text is English only | Fixed: `HandoffConsent` is localized in all 7 locales (`handoffMessages`, covered by the i18n parity tests) with the language selector in its header, the expiry formatted for the active locale and the identity message reused from the host messages. The tab title stays English: it comes from a server layout |
| Handoff: outcome announcement | ui-ux-pro-max (accessibility) | The pending line vanished when the action settled, the terminal status was a plain `<dd>` and the focused button unmounted, so the outcome was never announced | Fixed: the status `<dd>`, present in both the consent and the terminal view, is a polite live region; test for accept and decline |

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
- [x] `proposal-ai-smoke` (9), `client-update-writer-smoke` (3), `client-handoff-smoke` (2) on the final head.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-24 | Fix findings in this change instead of filing follow-up tasks | Requested by the ticket owner |
| 2026-09-25 | Close every remaining "Accepted" row as fixed (chip breakpoint, Handoff copy) or rejected with a recorded reason (disabled text, heading weights, toast variants) | The ticket wants findings fixed or tracked; rejected-by-Bundle-3 items are not defects and the owner asked for no other tasks |
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
- Give `HandoffConsent` real target details once a product-to-product handoff exists (today both ends of the only handoff are Kernel Demo).
