# Execution Plan: ANY-846 ProposalAI Gap Precision

## Status

- State: active
- Owner: agent
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-12
- Next action: review the completed round 3 changes; live acceptance and example confirmation remain pending.
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
- Gap meaning is decided by the existing review criteria and confirmed decisions, not regexes.
  Remove `unexpected_gap`, `missing_gap_detail`, `gap_must` and `gap_must_not`; reject fixtures
  containing the retired fields with an instruction to migrate the requirements to `criteria`.
- Retain factual failure checks, including empty gaps when `expect_gap` is true. Preserve the
  previous `expect_gap: false` behavior; it is not a newly introduced automatic empty-list gate.
- Without confirmed semantic decisions, otherwise valid runs stay PENDING. All required decisions
  must be yes for PASS; a confirmed no fails the relevant criterion. Suggestions and stale verdicts
  do not count as confirmation. Review must show the task, positioning and response together.
- Each gap case reviews the expected requirement, grounding of every reported gap, and fidelity
  of meaning, numbers, units and relationships. Equivalent wording and spelled-out numbers are valid.
- Grounding review also checks that each provided evidence quote accurately quotes the original task
  and supports the identified requirement. Review displays the evidence beside its gap description,
  explicitly marking absent optional evidence; it does not introduce automatic quote validation.
- Preserve ANY-631 fixtures, case hashes, decisions and acceptance results. The new gap cases have
  changed criteria and therefore require new approvals; old approvals must not silently transfer.
- Searches across ProposalAI, Acceptance Builder, Client Update Writer and Brief Decoder found
  this experience-gap classifier only in ProposalAI; no sibling prompt requires the same change.
- Include Spanish coverage alongside the required Russian and English cases.
- Local regressions exercise the acceptance state transitions using explicit test review decisions;
  they do not simulate model correctness or replace live evidence.

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

Historical implementation: its semantic regex approach is superseded by the approved round 2
contract in Decisions. Prompt and mandatory-domain fixes remain applicable.

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

## Code review round 2

The user approved replacing semantic gap regexes with the existing confirmed-review contract.
The Webflow finding exposed the broader problem: literal matches cannot distinguish contextual
mentions, negation, equivalent number wording or the relationship between a number and a tool.

- Removed semantic gap regex evaluation and its failure flags. Fixtures using either retired
  field now fail with an explicit migration message instead of silently losing their checks.
- Migrated all 15 gap cases to explicit grounding and requirement-fidelity review criteria,
  retaining their individual expected-gap/domain criteria and original task/profile inputs.
- Reused existing PENDING/PASS/FAIL decisions and hash validation. Otherwise valid runs remain
  PENDING until review is confirmed; missing mandatory gaps still fail automatically. CLI review
  now displays the source task and positioning alongside the response.
- Added regressions for the exact contextual Webflow description, negation, spelled-out numbers
  in RU/EN/ES, wrong units/number associations, split requirements and unsupported extra gaps.
  Tests supply explicit review decisions; they do not claim to judge the text semantically.
- Covered missing, suggested, unknown, stale and agent-only decisions, latest confirmed decisions,
  all gap cases' new criteria and the factual missing-gap failure despite positive review.

Validation on managed Python 3.12.13:

- Doctor passed; **147 eval tests passed** and the complete eval plus freelancer-suite run had
  **409 passed**, including packaging. Used `UV_OFFLINE=true` with the existing uv cache and
  `LITELLM_LOCAL_MODEL_COST_MAP=True`; no live provider requests.
- ANY-631 fixtures and decisions were unchanged. Compared against the evaluator at `958398bb`:
  all case hashes and the complete acceptance status/report matched exactly. Its historical FAIL
  remains unchanged; this is compatibility evidence, not a newly passing model acceptance result.
  SHA-256 of the JSON-encoded status/report pair:
  `167b6db69d77884ce9c6acd823af400f425f3ba369a946aed3a397e697bc3d6c`.
- Config, architecture and documentation validation, generated-document drift and diff whitespace
  checks passed. No GitHub writes. Full-check and frontend-check were not repeated for this
  evaluator/fixture-only round; their previously recorded local limitations remain applicable.

Live model behavior, product examples and final acceptance remain unverified. The implementation
deliberately requires confirmed semantic review rather than replacing it with another heuristic.

## Code review round 3

The user authorized the evidence-review correction, regression tests and plan updates with local
checks only. A local reproduction showed a fabricated Photoshop quote hidden by CLI review for
the Webflow case; simulated positive review decisions then allowed suite PASS.

Completed implementation:

- Display each gap description with its evidence, explicitly showing when optional evidence is absent.
- Extend grounding review in all 15 gap cases to assess whether supplied evidence accurately quotes
  the original task and supports the identified requirement. Preserve manual semantic decisions,
  factual failures and the optional evidence schema; add no automatic quote matcher.
- Test evidence visibility before decisions, accurate/mismatching quotes, absent evidence, multiple
  gaps and invalidation of decisions made under the old grounding question.
- Preserve ANY-631 fixtures, hashes and acceptance report. Run local eval/product tests and relevant
  structural/documentation checks, then record results. No live-eval or GitHub writes.

Validation on managed Python 3.12.13:

- Doctor passed. Before implementation, the selected regressions failed on hidden evidence and
  unchanged grounding criteria. After implementation, **165 eval tests passed**; the complete eval
  plus freelancer-suite run had **427 passed**, including packaging.
- CLI tests inspect the displayed evidence before answering, reject the fabricated Photoshop quote,
  accept an accurate Webflow quote with confirmed review, and cover absent optional evidence and
  multiple gaps. All 15 cases invalidate decisions made under the previous grounding question.
- ANY-631 fixtures and decisions remain unchanged. Compared against `2558f08c`, all case hashes and
  the complete acceptance status/report matched exactly, including its historical FAIL. The report
  digest remains `167b6db69d77884ce9c6acd823af400f425f3ba369a946aed3a397e697bc3d6c`.
- Config, architecture and documentation validation, generated-document drift and diff whitespace
  checks passed. Tests used `UV_OFFLINE=true`, the existing uv cache and
  `LITELLM_LOCAL_MODEL_COST_MAP=True`; no live provider requests or GitHub writes.
- Full-check/frontend-check were not repeated for this CLI/fixture change. Previously documented
  local limitations remain; model behavior, product examples and live acceptance remain pending.

## Live results

Live verification pending: automatic approval review rejected stack startup and the user then
explicitly declined live provider requests. No live attempts or model results recorded.

Proposed thresholds; needs team-lead approval. Gap quality is measured by confirmed review criteria,
not the retired regex checks:

- Routine landing reviews and yoga schedule: five of five reviewed results with no spurious gaps.
- HubSpot, Webflow and Trustpilot: five of five reviewed results with the required gap, no
  unsupported extra gaps, and correct meaning, numbers and units.
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
