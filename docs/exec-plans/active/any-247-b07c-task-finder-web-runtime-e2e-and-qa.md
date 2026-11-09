# ANY-247: Task Finder web runtime and QA

## Status
- State: active
- Owner: agent
- Created: 2026-11-09
- Last updated: 2026-11-09
- Review date: 2026-11-16
- Next action: Extract shared smoke infrastructure, then implement and validate Task Finder.
- Blocker: none

## Goal
Deliver Task Finder through the shared web runtime with deterministic browser evidence.

## Scope
Shared smoke infrastructure (TD-014); product fields, parser, renderer, seven locales, registration,
unit and browser tests, runner command, optional CI workflow, documentation.
No execution-kernel, atom, Provider Gateway, mapping DSL or handoff changes.

## Implementation steps
- [x] Extract shared DB helpers, smoke configuration, runner preamble and CI workflow; verify four existing smokes.
- [ ] Implement Task Finder using the shared runtime, canonical criterion ordering and independent score/verdict.
- [ ] Add localization, directory card, copy/activation/error/quota tests and Task Finder browser smoke.
- [ ] Run frontend/full checks and browser suites; record evidence and limitations.

## Decisions
The user authorized the mixed stack, number plus native meter, and optional ResultView.hideText.
Copy remains English per the renderer contract. On clipboard failure, reveal selectable text so the
existing fallback still works. Task Finder remains outside the committed release order; no handoff.
TD-014 extraction precedes the fifth smoke. Product-specific assertions stay in their suites.

## Validation
Use Python 3.12 from .quick-check-venv. Run doctor, frontend-check, full-check, documentation and
architecture validation, then all five product smokes against dev-up.

## Progress log
- 2026-11-09: Confirmed Python 3.12 managed environment passes doctor; pnpm and Docker work with sandbox escalation.

## Risks
Shared smoke changes affect four existing suites. CI triggers require remote validation.
Translations require native-speaker review. Fake-provider checks do not assess live model quality.

- 2026-11-09: Extraction validated: ProposalAI 10/10, Client Update Writer 4/4, Brief Decoder 8/8, Acceptance Builder 11/11; smoke lint/typecheck and six focused runner tests pass. Existing runner permission test fails because passwordless sudo is unavailable.
