# Execution Plan: ANY-846 ProposalAI Gap Precision

## Status

- State: active
- Owner: agent
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-12
- Next action: review the round 1 fixes; leave live acceptance and example confirmation pending.
- Blocker: user requested local checks only, so live model acceptance remains unverified. The local
  full-check environment still lacks passwordless sudo for an existing test.
- Implementation authorized; product confirmation and live evidence remain separate gates.

## Goal

The experience-gap block of ProposalAI reports only real, explicitly required tools, platforms and
skills that the positioning lacks. It does not report ordinary parts of the work the freelancer
already does. The wording keeps the meaning and numbers of the requirement.

## Scope

- ProposalAI gap prompt and its contract test.
- Python eval checks, case hashing, gap fixtures and regression tests.
- Product specification and verification evidence.

## Decisions

- Keep the existing prompt reference, language rule, workflow and output contract.
- Match forbidden gap literals only in descriptions; source evidence can quote routine components
  without claiming that they are missing experience.
- `gap_must` is a list of nonempty regex groups. Each group describes one requirement and must
  match a single gap description in full; different groups may match different gaps. Reject the
  obsolete flat format instead of silently interpreting its strings as groups of characters.
- HubSpot groups bind the number to the years unit and also require experience wording and HubSpot.
- Hash new checks only when present, preserving ANY-631 case approvals.
- Searches across ProposalAI, Acceptance Builder, Client Update Writer and Brief Decoder found
  this experience-gap classifier only in ProposalAI; no sibling prompt requires the same change.
- Include Spanish coverage alongside the required Russian and English cases.
- Regex checks detect specified literal failures; human criteria still assess meaning and coverage.

## Examples

Proposed. Needs product owner confirmation in ANY-846. Implementation does not wait for confirmation.

1. Substantive requirements: a required named tool, platform, protocol, language, certification,
   domain or experience minimum. Missing HubSpot experience is a gap; four years of HubSpot does
   not satisfy ten. Figma design without development does not cover a mandatory Webflow build.
2. Routine parts: landing-page first screen, course program, reviews/testimonials, schedule, form,
   buttons, footer and mobile version; automation cleanup, deduplication, notifications and docs.
   A separate requirement to fetch reviews through Trustpilot API can be a Trustpilot API gap.
3. Adjacent experience: landing pages in Figma cover an online-school landing page; responsive
   design covers a mobile version. Figma does not cover an explicitly mandatory Sketch requirement.
   Retail landing-page experience covers a healthcare landing page when healthcare is only the
   target niche; it does not cover an explicit prerequisite of prior healthcare-industry work.
   Mandatory domains, protocols, certifications, skills and experience minimums override adjacency.

## Baseline

- Source SHA: `b48eaaceaf36338683e529538982ccad78116183`.
- Baseline not run: no running live stack. Local credentials are configured, but automatic
  approval review rejected starting the stack because provider egress and costs need explicit
  approval. The user then explicitly chose local checks only. Model/effort: not verified.
- Required baseline: three attempts per gap case on the unchanged prompt; retain failed attempts.

## Progress

- Read architecture, task requirements, eval consumers and pinned-suite tests.
- System Python 3.14 doctor failed (pytest/pydantic absent); managed Python 3.12.13 doctor passed.
- Implemented the prompt rules, opt-in gap checks and backward-compatible case hashing.
- Added nine gap cases (RU/EN/ES), retaining the exact P01 inputs and documenting the reconstructed
  landing-reviews input. Human criteria assess meaning; regex checks only flag specified literals.
- Targeted eval and freelancer-suite tests: 370 passed, including the pinned ANY-631 suite.
- Documentation validation and generated-document drift check passed.
- Initial sandbox runs could not resolve Python build dependencies; the targeted test collection
  also hit a LiteLLM import error during its remote price-map fallback. Targeted tests passed with
  public network access. Interrupted the sandbox baseline after failures and ran full-check
  outside the sandbox.
- Full-check stopped in its baseline: 3595 passed, 12 skipped, 657 deselected, one failure in
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user` because
  `sudo -n -u nobody` requires interactive authentication. No tests were changed, disabled or
  marked expected-failure to bypass this environment limitation. Existing skips/deselections
  are not evidence of PostgreSQL or slow-test coverage. The freelancer-suite tests already passed
  in the targeted run.
- Separate frontend-check: lint, typecheck, unit tests (including 673 web-mirror tests), all 339
  Atom Lab browser tests and generated API-type drift checks passed. The web-mirror build failed
  prerendering `/404`: `<Html> should not be imported outside of pages/_document`. Next.js also
  auto-added a Node types dependency during that build; restored both the package manifest and
  lockfile to their original contents. No frontend source or dependencies are part of this fix.
- Collected sanitized diagnostic context for the full-check failure. Local implementation is
  ready for review; full-check and frontend-check are not claimed green.
- Repository text scan found pre-existing prohibited local-skill references in plans for ANY-17,
  ANY-339, ANY-391, ANY-221 and ANY-227; none were introduced or changed in this task.

## Code review round 1

All three findings are addressed locally; the user explicitly authorized fixes, regression tests
and plan updates, with no live evaluation.

1. Forbidden-component checks now read only the claimed gap description. The regression uses the
   real Webflow task as evidence, including its reviews, first-screen and form wording, and still
   rejects a description that actually reports the reviews block as missing experience.
2. Migrated every gap fixture and test to grouped `gap_must`. One requirement's details must occur
   in one description; multiple independent requirements can use separate descriptions. Tests
   cover split details, missing groups, absent evidence, invalid/empty groups, and CLI reporting
   of the obsolete flat format. RU/EN/ES HubSpot cases bind 10 to years and require experience
   wording, rejecting months, training and mere references to a product's age. Grouping is part
   of the existing hash payload; approved ANY-631 case hashes remain unchanged.
3. The prompt and product spec explicitly preserve every mandatory prerequisite over adjacency,
   including domain, certification, skill and experience minimums. Added mandatory/incidental
   healthcare-domain pairs in RU/EN/ES; the gap fixture now contains 15 cases. The prompt contract
   test pins the rule and its healthcare example. These are local regression assets, not evidence
   that a live model follows the instruction.

Validation on managed Python 3.12.13:

- Doctor passed.
- Eval and freelancer-suite tests: **392 passed**, including the pinned ANY-631 matrix, prompt
  author-direction rules and packaging. The initial sandbox run had 390 passes and one packaging
  failure; packaging and the complete final run passed with access to the existing uv cache and
  `UV_OFFLINE=true`. `LITELLM_LOCAL_MODEL_COST_MAP=True` prevented remote price-map fetching.
- Config validation, architecture validation, documentation validation and generated-document
  drift check passed; diff whitespace check passed.
- No live provider calls or GitHub writes. Full-check/frontend-check were not repeated for this
  product-prompt/eval-only correction; the earlier local environment limitations remain recorded
  above. The preceding review observed green required CI checks on `101bd522`, which does not
  validate these subsequent changes.

Regex groups enforce literal co-occurrence and the configured units, not full semantic relations
inside a sentence; the human criteria remain required for semantic acceptance.

## Live results

Live verification pending: automatic approval review rejected stack startup and the user then
explicitly declined live provider requests. No live attempts or model results recorded.

Proposed thresholds; needs team-lead approval:

- Routine landing reviews and yoga schedule: zero unexpected gaps in five attempts per case.
- HubSpot, Webflow and Trustpilot: five of five required gaps, with zero missing details or
  forbidden gap literals.
- Existing orders: one attempt each; every required gap still present.
- Run the gap set in Russian, English and Spanish. Compare model alternatives only if observed
  failures justify further iteration; keep remaining non-critical polish for a later product pass.
- Record actual model, effort, prompt hashes, environment and per-case baseline/fix counts.

## Out of scope

ANY-771 (gap language), platform-level deterministic A04 number validation, changes to
`compose_persuasive_text`, workflows, output schemas and renderers.

## Risks

Prompt rules do not prove model behavior; only live runs do. Over-correcting can hide real gaps;
required-gap cases guard against this. Examples and thresholds need owner confirmation before
acceptance. Keep this plan active until live evidence and confirmation are complete.
