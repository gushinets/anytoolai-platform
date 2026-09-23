# Execution Plan: ANY-232 Brief Decoder Bundle And Workflow

## Status

- State: active
- Owner: agent
- Created: 2026-09-21
- Last updated: 2026-09-23
- Review date: 2026-09-28
- Next action: re-request review; merge once approved.
- Blocker: none

## Goal

Define the `brief_decoder` Freelancer Suite product bundle as a real product config directory
loaded through `FreelancerSuiteBundle.config_roots()`: workflow `A01 + A04 -> A05`, composed
through A10, using only generic atoms -- no Platform Core changes, no product Python code.

## Scope

### In scope

- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder/`:
  product, scenario, frontend, workflow, action-config, prompt, schema, quota and renderer-contract
  config.
- `FreelancerSuiteBundle.config_roots()` wiring; README and `add-product-recipe.md` root counts.
- Deterministic fake-provider fixtures: happy path, weak input, and empty-issues variants for A01,
  A04 and A10 (eleven fixtures total; see "Implementation steps").
- Tests in `apps/platform-api/tests` (quick-check) and `freelancer-suite/tests` (full-check).

### Out of scope

`apps/web-mirror` page/renderer (ANY-248), Chrome Extension (ANY-240), the Brief Decoder ->
Acceptance Builder handoff (ANY-26), a live-provider action-config variant, any Platform
Core/atom/mapping-DSL change, custom backend endpoints.

## Relevant docs

- `docs/product-specs/add-product-recipe.md`
- `docs/architecture/action-model.md`
- `docs/architecture/workflow-model.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `packages/backend/product-platforms/freelancer-suite/README.md`

## Contracts touched

- API: none (generic `/v1/products/{product}/scenarios/{scenario}/start` runtime only).
- DB: none.
- Config: new product tree under `freelancer-suite`; `FreelancerSuiteBundle.config_roots()`.
- Events: `client.next_action_clicked` via the generic `copy_result` next action only; no
  `analytics.yaml`, no `handoffs.yaml`.
- Frontend: `frontends.yaml` registers one `web_mirror` entry (runtime requirement for any
  scenario start); no page code.

## Design decisions

1. **One scenario, one workflow, four steps, one run.** `brief_decoder.decode_v1`. Per
   `atom-ready-product-inventory.md` Brief Decoder has a single workflow run, so the acceptance
   criterion "any second run receives an explicit user-selected string" is satisfied by having no
   second run; a test pins the single scenario. No mapping path indexes an array.
2. **All four steps are `structured_llm`**, A10 included (no template registry:
   `template_ref` is a string and its meaning lives in the product prompt
   `generate_summary.v1.md`, as in `kernel_demo`). Each step has its own action config, prompt and
   fixtures.
3. **Product decisions no doc specifies** (input, A01 fields, taxonomy, audience):
   - Input: one required trimmed `brief_text` (max 8000).
   - A01 fields, all `required: false`, `strict: false` so a vague brief yields `missing_fields`
     rather than a failed run: `project_goal`, `deliverables`, `deadline`, `budget`,
     `target_audience`, `constraints` (`deadline`/`budget` are strings, worded as the brief words
     them, not `date`).
   - A04 taxonomy: `missing_information`, `ambiguity`, `scope_risk`, `timeline_risk`,
     `budget_risk`, `contradiction`.
   - A05 `target_audience`: "the client who wrote the brief".
4. **A01 -> A04 is order-only** (`action-model.md`): A04 reads the original brief text.
5. **Composed output.** Each step writes its own key of `context.workflow_output`
   (`brief`, `issues`, `questions`, `document`); the result is one closed object validated against
   `brief_decoder.decode_output_v1`. No committed workflow composed output this way before; the
   end-to-end tests are the proof. Fallback if it ever proves brittle: expose only A10's output.
   Because the A01 field list and taxonomy are config-owned, the output schema closes
   `brief.values` with explicit properties and enumerates categories; a test ties the literals in
   `workflows.yaml` to the schema so they cannot drift.
6. **A04 -> A05 contract mismatch.** A04 `issues` may be empty; A05 `issues` has `minItems: 1`.
   Guard as in `kernel_demo.detect_questions_v1`: A04 seeds `questions: []`, A05 has
   `when: steps.detect_issues.output.issues`, A10 reads `?steps.generate_questions.output.questions`.
   An empty question list is a valid, non-activating result.
7. **Quota**: `quotas.yaml` (3 runs per guest, lifetime, per product), mirroring `proposal_ai`.
   Not required by the ticket; motivated by four provider calls per run. The limit is a starting
   value.
8. **`renderer_contract.yaml`** is product-owned and never read by `ConfigLoader`; it names the
   four parts (brief, issues, clarifying questions, summary document) and is asserted against
   `workflows.yaml`/`scenarios.yaml` by the product's own test.

## Implementation steps

- [x] Exec plan (this file).
- [x] Product config tree.
- [x] `FreelancerSuiteBundle.config_roots()` wiring + README / recipe root counts.
- [x] Eleven fixtures (4 happy, 4 weak, 3 empty-issues variants: A01's `extract_brief`, A04's
      `detect_issues`, and A10's `generate_summary`, grounded in a dedicated clean-brief input --
      see round #3 and round #6 below).
- [x] Tests: `apps/platform-api/tests/test_brief_decoder_bundle.py`,
      `freelancer-suite/tests/test_brief_decoder_product.py`.
- [x] Verification (below).

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py validate-docs` / `generate-docs --check`
- [x] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-21 | Single run, no second-run input | Inventory says one workflow run; AC is conditional |
| 2026-09-21 | Guard A05 with `when` + seeded `questions: []` | A05 input requires >= 1 issue; precedent `detect_questions_v1` |
| 2026-09-21 | Composed per-key `workflow_output` | Delivers all four renderer parts; fallback is A10-only output |
| 2026-09-22 | Round #1 code review fixes (10 of 14 findings; #5 documented as inherited) | See review round below |
| 2026-09-23 | Root-caused the no_issues scenario instead of re-patching a 3rd time: the actual problem across rounds #3/#6 was reusing `BRIEF_TEXT` for a "clean brief" scenario the happy-path fixtures already contradict, not any single fixture's content | Added `CLEAN_BRIEF_TEXT` (round #7); each prior round had fixed a real but narrower symptom |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-21 | Config tree, fixtures, wiring and both test suites written; new tests green | Code review |
| 2026-09-22 | Round #1 code review: fixed 10 of 14 findings (see below); re-ran quick-check/full-check, both green | Code review round #2 |
| 2026-09-23 | Round #2 code review: fixed 5 of 7 findings (dedup onto shared test helpers, see below); re-ran quick-check/full-check, both green | Open PR |
| 2026-09-23 | PR #141 opened; description filled in from the template | Address PR inline comments |
| 2026-09-23 | Fixed a PR inline comment: `generate_summary.v1.md`'s `next-steps` instruction claimed "work can start" for any empty `data.questions`, regardless of `data.issues`/`data.brief.missing_fields`; moved the readiness claim to `summary` and made it depend on all three. Updated the `.no_issues` fixture's `next-steps` text to match | Code review round #3 |
| 2026-09-23 | Round #3 code review (self-review, posted as blocking inline PR comments): fixed all 3 findings (see below); re-ran quick-check/full-check, both green | Code review round #4 |
| 2026-09-23 | Round #4 code review (self-review): fixed the 1 blocker and the 1 documentation finding (see below); re-ran quick-check/full-check, both green | Update PR description, code review round #5 |
| 2026-09-23 | Round #5 code review (self-review): 0 blockers; fixed 2 non-blocking documentation findings (see below); re-ran quick-check/full-check, both green | Code review round #6 |
| 2026-09-23 | Round #6 code review (self-review): fixed 2 blockers (no_issues fixture set genuinely inconsistent; A05 prompt overclaimed an unenforced invariant) plus reaffirmed one out-of-scope gap as follow-up debt; re-ran targeted tests, all green | Update PR description, code review round #7 |
| 2026-09-23 | Round #7 code review (self-review): round #6's no_issues fix was still ungrounded (ran against BRIEF_TEXT, not a clean-brief input); added CLEAN_BRIEF_TEXT and fixed the missing metadata.kind=list requirement; re-ran quick-check/full-check, both green | Update PR description, re-request review |
| 2026-09-23 | Round #8 code review (self-review): 2 blockers (whitespace-only canonical strings; A05 prompt's one-per-issue overclaim) fixed with a sweep of every prompt claim vs. real enforcement; re-ran quick-check/full-check, both green | Re-request review |
| 2026-09-23 | Round #9 code review (self-review): 1 blocker (`questions.maxItems: 10` vs the real cap of 5) fixed and pinned to the workflow; re-ran quick-check/full-check, both green | Re-request review |

## Code review round #1 (2026-09-21)

14 findings; all re-verified directly (including live `ruff`) before fixing. Fixed:

1. **Critical.** A01's shared cross-validator accepts an empty string/array as a value, but
   `decode_output_v1` requires `minLength: 1`/non-empty arrays -- a brief that yields one could
   pass A01 then still fail final `output_schema_ref` validation after 3 more paid calls.
   `extract_brief.v1.md` now explicitly tells the model an empty string or empty array is not an
   extracted value (treat as missing), and `decode_output_v1` now also requires `minItems: 1` on
   `deliverables`/`constraints` (previously only strings were closed this way) so the two array
   fields hold the same "found or omitted, never empty" contract as the four string fields.
2. Recording adapter only asserted the call *sequence*, not payloads -- a swapped mapping between
   steps could leave every fixture output valid. `test_brief_decoder_bundle.py`'s adapter now
   captures the full `ResolvedProviderRequest` and the happy-path test asserts each step's
   resolved input payload (parsed back out of the rendered prompt) against the actual upstream
   data, not just the call-id sequence.
3. The empty-issues test reused the happy-path A10 document fixture, which narrates 3
   issues/questions that don't exist in that run. Added a dedicated
   `brief_decoder.generate_summary_v1.no_issues.json` fixture consistent with `issues: []` and
   the happy A01 brief's own `missing_fields`, and the test now asserts against it.
4. Added input-schema edge-case coverage: trailing/leading newline, trailing space, the exact
   8000-char boundary (valid), and a legal internal newline (valid) -- mirrors `proposal_ai`'s
   own coverage.
6. Added `test_quota_policy_ref_resolves_to_the_declared_lifetime_product_quota`, mirroring
   `proposal_ai`'s.
7. Closed by the same `minItems: 1` fix as #1.
8. The field-list drift test compared names only; a field's A01 `type` changing (e.g.
   `target_audience` from `string` to `array_of_strings`) wasn't caught. Now also asserts each
   field's declared JSON-schema type/items-type matches its A01 spec `type`.
9. Our inlined copies of the kernel A04/A05/A10 output shapes had no sync test against the kernel
   schemas they were copied from (cross-file `$ref` isn't supported). Added a structural
   drift test comparing property/required sets and per-property types (deliberately excluding
   `category`'s enum, which we narrow to our own taxonomy).
10. `renderer_contract.yaml`'s `canonical_field: document` pointed at an object with no
    serialization rule, unlike sibling contracts' plain-string `text`. Added
    `canonical_field_composition` describing how `sections` + `summary` become copy-ready text,
    pinned by a test.
11. Invalid-input test now also asserts `provider_calls_table` count is 0 for the job (DB-level
    evidence, not just the adapter's own call list), mirroring `proposal_ai`'s pattern.
12. Fixed inaccurate comments: `quotas.yaml` said "four provider calls" (constant) when the `when`
    guard makes it "up to four"; `workflows.yaml` said "each step writes its own key" when
    `detect_issues` writes two.
13. Fixed all `ruff` E501/import-order findings across the touched files (ruff isn't in
    quick-check/full-check/CI, but the fix was cheap and correct).
14. Updated `docs/product-specs/mvp-b-handoff-note.md`'s stale "ANY-227 ... the first real
    [product root]" line to name all three implemented roots.

Documented as an accepted, inherited platform gap, not fixed here:

5. Guest quota is consumed on scenario *start*, before input-schema validation runs in the
   worker -- an invalid `brief_text` (e.g. a trailing newline) still burns one lifetime run. This
   is the same gap ANY-227 documented and explicitly left unfixed for ProposalAI (round #1,
   finding #1: "Guest quota consumed before input-schema validation" --
   `docs/exec-plans/completed/any-227-b02a-proposalai-bundle-and-workflow.md`), inherent to
   `ScenarioRuntimeService.start_session`/quota-then-validate ordering. Fixing it needs a Platform
   Core change, which this ticket's non-goals explicitly exclude ("any Platform Core/atom/
   mapping-DSL change"). `apps/web-mirror` (ANY-248, out of scope here) can still add
   client-side trimming to avoid triggering it in practice.

## Code review round #2 (2026-09-23)

No correctness bugs -- reuse/altitude/dead-code findings only, all re-verified before fixing.

Fixed (reopened drift already closed once for ANY-227/ANY-414's own sibling files):

1. `test_brief_decoder_bundle.py` had its own local `app` fixture and hand-rolled `_request`
   helper -- a third independent copy of exactly what `conftest.py` already extracted into
   `platform_api_app_factory`/`request_platform_api` once `test_proposal_ai_bundle.py` and
   `test_client_update_writer_bundle.py` duplicated it. Migrated to the shared fixtures.
2. `test_brief_decoder_product.py` reimplemented `_load_validate_architecture_module()`/
   `FORBIDDEN_TOKENS`/`_load_yaml()` instead of loading the shared `_test_support.py` ANY-414
   already extracted for the same reason. Migrated to it.
3. `_RecordingProviderAdapter` was a fourth independent `FakeProviderAdapter` subclass,
   overlapping three pre-existing ones (`test_composite_workflow_matrix.py`'s pure recorder,
   `test_client_update_writer_bundle.py`'s force-every-call-to-`.weak_input`,
   `test_proposal_ai_bundle.py`'s force-one-fixed-key). Added `tests/support/fake_provider_recording.py`'s
   `RecordingProviderAdapter`, a strict generalization of all three (recording plus an optional
   per-`action_config_id` fixture-key-suffix map), and migrated this file to it. The three
   pre-existing call sites are *not* migrated -- out of scope for this ticket, left as follow-up
   debt below.
6. `_KERNEL_DRIFT_CASES` + `_resolve()` were generic path-tuple machinery for exactly 3 fixed
   comparisons. Inlined into 3 explicit calls to a shared `_assert_same_shape()` helper.
7. `_expected_output()`'s `questions: bool = True` parameter was dead code (nothing ever passed
   `questions=False`; the no-issues test already built its expected output inline). Removed.

Reaffirmed as already-documented, already-accepted platform debt (not re-fixed; a second
occurrence, strengthening the signal to fix once at the platform/contract level rather than
per-product):

4. The A04-\>A05 `when`-guard is a product-level workaround for a real atom-contract mismatch
   (A04's own output allows empty `issues`; A05's own input requires `minItems: 1`).
   `kernel_demo.composite_analyze_and_clarify_v1` has the same unguarded gap (see this plan's
   earlier risk notes and follow-up debt) -- worth fixing once at the A05 contract level (e.g.
   `minItems: 0`) instead of every composing product re-deriving the same guard. Out of scope for
   a single product ticket.
5. Guest quota consumed before input-schema validation (round #1 finding #5) -- Brief Decoder is
   now the second of three products to inherit this platform gap after ProposalAI/ANY-227.
   Unchanged conclusion: needs a `ScenarioRuntimeService.start_session` ordering fix, out of scope
   here.

## Code review round #3 (2026-09-23, self-review posted as blocking PR inline comments)

3 blocking findings, all confirmed against current code and fixed:

1. `decode_output_v1`'s `questions[].category` was an open string (`minLength: 1`), not closed
   over the A04/A05 taxonomy, even though `generate_questions.v1.md` requires it to reuse the
   referenced issue's category and the A05 cross-validator never checks it. Closed it to the same
   6-value enum as `issues[].category`, and extended
   `test_config_owned_literals_agree_with_the_output_schema` to pin it against the workflow's
   taxonomy literal (not just `issues[].category`).
2. `document.sections` accepted any array of >=1 arbitrarily-shaped sections, even though
   `generate_summary.v1.md` mandates exactly 4 sections with fixed ids/titles/order and A10 has
   no cross-validator. Narrowed it with `prefixItems` (4 fixed per-position `$defs` entries, each
   pinning `id`/`title` via `const`) plus `minItems: 4`/`maxItems: 4`/`items: false` -- this
   package's first use of `$ref`/`$defs`/`prefixItems`, verified directly against jsonschema
   4.26 (this repo's version) before committing: same-document `#/$defs/...` refs resolve with a
   plain `jsonschema.validate()` call, no `$schema` declaration needed. Added mutation cases
   (arbitrary section id, a missing section, reordered sections) to
   `test_output_schema_accepts_the_fixtures_and_rejects_open_shapes`.
3. The `.no_issues` A10 fixture still claimed "ready to start work" even though its own run's A01
   fixture has a non-empty `missing_fields` (`target_audience`) -- directly contradicting the
   round-#3-adjacent prompt fix (readiness requires "no issues *and* nothing missing"). Rewrote
   the fixture's `summary` to state the brief is not fully ready and name the missing field, and
   added an assertion in `test_no_issues_skips_question_generation_and_still_produces_a_consistent_document`
   that the summary names the missing field and doesn't claim unqualified readiness.

## Code review round #4 (2026-09-23, self-review posted here per request instead of GitHub)

1 blocker, confirmed and fixed; 1 non-blocking documentation finding, also fixed:

1. **Blocker.** `renderer_contract.yaml`'s `clarifying_questions` part still described an empty
   `questions` list as "no clarification needed" -- a readiness claim directly contradicting
   `generate_summary.v1.md`'s own rule (round #3 fix: empty `questions` alone never implies
   readiness) and the deterministic `.no_issues` fixture, which pairs an empty `questions` list
   with a summary that says the brief is *not* ready. Reworded the part's description to a
   neutral "no clarifying questions were generated" and made explicit that only
   `summary_document` makes a readiness call, weighing `data.issues`,
   `data.brief.missing_fields`, and `data.questions` together. Added an assertion to
   `test_renderer_contract_agrees_with_workflow_and_scenario` pinning that the
   `clarifying_questions` part never says "no clarification needed" again.
2. **Non-blocking.** The fixture count in this plan and the PR description still said "nine"
   after round #3 added a second `.no_issues` variant (bringing the total to ten); this plan's
   `Status` header was also stale (`Last updated`, `Next action`). Fixed both here; the PR
   description is updated separately.

## Code review round #5 (2026-09-23, self-review)

0 blockers; the round #4 fix held up under a full re-review of the whole product contract. 2
non-blocking findings, both fixed:

1. `renderer_contract.yaml`'s `clarifying_questions` part pointed readers at `data.issues` and
   `data.brief.missing_fields` -- A10's own *input* paths (`generate_summary.v1.md`'s `data.*`),
   not the paths this contract actually describes (the final composed artifact's `issues` and
   `brief.missing_fields`). Confusing for whoever builds the ANY-248 renderer against this file,
   though nothing in code reads this prose. Reworded to the artifact's own paths.
2. This plan's `Status.Next action` still said "round #4" after round #4 was already addressed,
   and the PR description still said "Two rounds of code review fixes" with four (now five)
   rounds recorded here. Fixed both.

## Code review round #6 (2026-09-23, self-review)

2 blockers, both confirmed against current code and fixed:

1. The `.no_issues` end-to-end scenario reused the happy path's A01 fixture, which still has
   `missing_fields: ["target_audience"]`. That made the deterministic path certify "no A04
   issues, no A05 questions, but a known gap (`target_audience`) that nothing generated a
   question for" -- and `detect_issues.v1.md`'s own taxonomy includes `missing_information`,
   which the same source text plausibly should have surfaced as an A04 issue if it were truly
   the clean-brief scenario this path is meant to exercise. Added a dedicated
   `brief_decoder.extract_brief_v1.no_issues.json` with `missing_fields: []` and rewrote the
   `.no_issues` A10 fixture to match a genuinely complete, ready brief; the end-to-end test now
   redirects all three steps (`extract`, `detect_issues`, `generate_summary`) to their
   `.no_issues` fixtures and asserts the readiness claim the other way (ready, not "not ready").
2. `generate_questions.v1.md` stated as unconditional rules that `priority` follows the
   referenced issue's `severity` and `category` reuses its `category` -- but the shared A05
   cross-validator (`platform-actions`, out of scope to change here) only checks
   `source_issue_index` bounds, `max_questions`, valid `priority`/`category` values, and
   ordering; it never compares a question's `priority`/`category` against its referenced issue's.
   A schema-valid output that violates the stated correspondence would still become a canonical
   artifact. Softened the prompt to `kernel_demo.generate_clarifying_questions.v1.md`'s own
   precedent wording -- a guideline with an explicit "unless materially different" escape hatch,
   not an unenforceable strict claim -- rather than expanding shared A05 validation, which this
   ticket's non-goals exclude.

Reaffirmed as a real, out-of-scope architectural gap the review also raised: if any
`brief.missing_fields` makes the summary claim "not ready" (round #3's own rule), the product has
no way to turn that specific gap into an actionable clarifying question -- A05 only ever derives
`questions` from A04's `issues`, never from A01's `missing_fields`. Wiring A01's missing fields
into A05 (e.g. synthesizing pseudo-issues before the guard) would be a real workflow-topology
change beyond this ticket's declared workflow (`A01 + A04 -> A05`, composed through A10) and its
non-goals; noted as follow-up debt below rather than done unilaterally.

## Code review round #7 (2026-09-23, self-review)

2 blockers, both confirmed against current code and fixed -- root-caused this time rather than
patched again (see decision log):

1. Round #6's `.no_issues` fixture fix was itself only half the fix: the end-to-end test still
   sent `BRIEF_TEXT` -- the same ambiguous, target-audience-free text the happy-path A04 fixture
   already flags with 3 issues (ambiguity, timeline risk, scope risk) for this exact input -- to
   a scenario whose A01/A04/A10 fixtures claim a clean, complete brief. The fixtures were
   internally consistent with each other but not grounded in what was actually sent; nothing
   stopped the fake-provider path from proving only that mutually exclusive results can be
   returned for the same input, not that a clean brief behaves correctly. Added `CLEAN_BRIEF_TEXT`,
   a dedicated brief that states every A01 field explicitly and closes every ambiguity/scope/
   timeline/budget question `BRIEF_TEXT` leaves open, rewrote the `.no_issues` A01/A10 fixtures to
   be a faithful extraction of it, and asserted the resolved `source_text` payload against it
   (mirroring the happy-path test's own input-payload assertions).
2. `generate_summary.v1.md` unconditionally requires `metadata.kind = list` on `key-details` and
   `next-steps`, but `decode_output_v1` left `metadata` optional on every section and, when
   present, open to any of 5 `kind` values -- a canonical artifact with `next-steps` missing
   `metadata` entirely, or `key-details.metadata.kind = "table"`, would validate. The `.no_issues`
   A10 fixture's own `next-steps` section was missing `metadata` altogether, an instance of
   exactly this gap. Added a dedicated `listSectionMetadata` `$defs` entry (`kind: const "list"`,
   required) and made `metadata` required on both `keyDetailsSection` and `nextStepsSection`.
   Fixed the fixture and added 4 mutation tests (missing/wrong-kind on each of the two sections).

## Code review round #8 (2026-09-23, self-review)

2 blockers, both confirmed and fixed; the second was the same class as round #6's, so this round
swept *every* prompt rule against what the runtime actually enforces instead of fixing only the
reported line:

1. Free-form canonical strings (`brief.values` strings and array items, `issues[].description`/
   `evidence`, `questions[].question`/`rationale`) were `minLength: 1` only, so a whitespace-only
   value validated -- A01/A04/A05 and their validators don't reject it either. Added
   `pattern: "\\S"` to all 10 (A10 strings already had it) plus 6 whitespace mutation tests, and
   `extract_brief.v1.md` now says "empty or whitespace-only".
2. `generate_questions.v1.md` promised "one [question] per actionable entry in `issues`", but the
   shared A05 cross-validator checks neither uniqueness of `source_issue_index` nor coverage --
   its own kernel test accepts the same index twice. Softened to guidance ("prefer one per
   actionable issue... not a guarantee"). Sweep result: every other structural rule in the four
   prompts (taxonomy membership, missing-vs-present fields, question count/order, exactly four
   sections with fixed ids, `metadata.kind = list`) is enforced by an atom validator or this
   product's schema; the remainder is behavioral guidance (tone, no invention), not a
   structural claim.

Also made `Status.Next action` round-agnostic so it stops going stale every round.

## Code review round #9 (2026-09-23, self-review)

1 blocker, confirmed and fixed: `decode_output_v1`'s `questions.maxItems` was 10 (copied from the
kernel A05 output schema's own ceiling), but this workflow never passed `max_questions`, so A05's
cross-validator capped every run at its default of 5 -- a 6-10 question artifact validated
against the canonical schema although no run can produce one (and stored results are re-validated
against this schema, not A05's validator). Set `maxItems: 5`, made the cap explicit in the
workflow (`max_questions: literal:5`) instead of relying on A05's implicit default, and added a
config test tying the schema's `maxItems` to that literal plus a 6-question mutation test and a
resolved-payload assertion. Sweep of the remaining numeric bounds: `sections` (exactly 4) and
`brief_text` (`maxLength` 8000) are product-owned and consistent; nothing else is capped.

## Open questions

None blocking. The input/field/taxonomy choices in decision 3 are product decisions a reviewer may
want to change; they drive the output schema and all eleven fixtures.

## Follow-up debt

- `kernel_demo.composite_analyze_and_clarify_v1` has the same missing empty-issues guard; not
  fixed here (out of scope).
- Brief Decoder -> Acceptance Builder handoff is ANY-26.
- Guest quota consumed before input validation (round #1 finding #5) -- inherited platform gap,
  same as ProposalAI's; needs a Platform Core fix, out of scope for any product ticket. Brief
  Decoder is now the second product to inherit it (round #2 finding #5).
- A04's empty-`issues` output vs. A05's `minItems: 1` input is a real atom-contract mismatch that
  every composing workflow (`kernel_demo`, now Brief Decoder) re-derives its own `when`-guard
  around; worth fixing once at the A05 contract level (round #2 finding #4).
- The three pre-existing `FakeProviderAdapter` test subclasses
  (`test_composite_workflow_matrix.py`, `test_client_update_writer_bundle.py`,
  `test_proposal_ai_bundle.py`) are not migrated to the new shared
  `tests/support/fake_provider_recording.RecordingProviderAdapter`; only this ticket's own test
  uses it so far (round #2 finding #3).
- No product-level way to turn an A01 `missing_fields` gap into an actionable A05 clarifying
  question -- `questions` is derived only from A04's `issues`. A brief can be "not ready" per
  `generate_summary.v1.md`'s own rule with nothing in `questions` addressing why. Fixing this
  would change the workflow's own topology (e.g. synthesizing pseudo-issues from
  `missing_fields` ahead of the A05 guard) beyond this ticket's declared `A01 + A04 -> A05`
  shape; out of scope here (round #6 finding).
