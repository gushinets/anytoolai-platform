# Execution Plan: ANY-219 Composite Atom Workflow Proof

## Status

- State: completed
- Owner: agent
- Created: 2026-08-19
- Last updated: 2026-08-26
- Review date: 2026-08-19
- Next action: none — PR #81 merged (`6afca1b`, ANY-219 A21a2). Moved to `completed/` as part of
  the ANY-24 closeout.
- Blocker: none

## Goal

Prove that MVP-A1's generic action types compose through real, config-declared multi-step
workflows over the production-shaped API -> session -> job -> worker path — not merely run
independently (that's ANY-218's 11/11 standalone proof) and not as one artificial 11-step chain.
Deliver 3 composite `kernel_demo` workflows that together cover all 11 atom action types, each
proven end-to-end (real DB, real artifact/event-log lineage, real per-step provider-request
dependency proofs) and live-smoke-tested via `dev-smoke`.

## Scope

### In scope

- 3 composite workflow configs in `configs/kernel/products/kernel_demo/workflows.yaml`:
  `composite_analyze_and_clarify_v1`, `composite_evaluate_match_v1`,
  `composite_shape_and_write_v1` — covering all 11 atom action types across their steps, no
  action type repeated across workflows — plus their corresponding `scenarios.yaml` entries.
- `apps/platform-api/tests/test_composite_workflow_matrix.py` — DB-backed matrix proof (sibling of
  ANY-218's `test_atom_runtime_matrix.py`): step order, artifact/event-log lineage,
  `scenario_session_id` correlation, and per-step provider-request dependency proofs (does a
  dependent step's *actual rendered prompt* carry the source step's real mapped output, not just
  that both steps ran).
- `scripts/agent/kernel_demo_smoke.py` / `tests/test_kernel_demo_smoke.py` — composite coverage
  checks wired into `dev-smoke`/`prod-smoke`, alongside ANY-218's atom coverage checks.

### Out of scope

- Adding array-indexing (or any other structural extension) to the workflow mapping DSL
  (`packages/backend/platform-core/.../workflows/mappings.py`) — considered and explicitly
  declined (see Decision log); out of scope for a composite-workflow-*config* ticket.
- Freelancer/MVP-B product-specific workflows.
- Web mirror, Chrome Extension, or browser automation — this ticket is backend/CLI proof only
  (MVP-A1), same boundary as ANY-218.

## Relevant docs

- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/architecture/action-model.md` (Wave 1 action types table + the "kernel_demo composite
  workflow mapping notes" section added by this ticket's review passes)

## Contracts touched

- Config: 3 new composite `workflow_id`s + matching `scenario_id`s in `kernel_demo`.
- Schema: `kernel.schemas.score_match_output_v1` gained a required `overall_rationale` field (see
  Decision log) — the only schema change; no other action's input/output contract changed.
- Tests: `test_composite_workflow_matrix.py` (new), `test_kernel_demo_smoke.py` (extended),
  targeted regression tests across `platform-core`/`platform-actions`/`platform-api` wherever a
  hand-built fixture/literal needed to track the `overall_rationale` schema change.

## Implementation steps

- [x] 3 composite workflow + scenario configs covering all 11 atom action types.
- [x] `test_composite_workflow_matrix.py`: step order, lineage, correlation, and per-step
      dependency proofs against a real Postgres instance.
- [x] `kernel_demo_smoke.py` / `test_kernel_demo_smoke.py`: composite coverage checks, wired into
      `dev-smoke`.
- [x] 20 rounds of code review passes plus 4 team-lead reviews addressed. The two mapping-DSL
      workarounds those passes converged on (`overall_rationale` on `score_match_by_rubric`, and
      leaving `extract -> detect_issues` order-only) and why are documented once, in
      `docs/architecture/action-model.md`'s "kernel_demo composite workflow mapping notes" section
      — not repeated here.
- [x] This exec plan filed, per CLAUDE.md's "before coding" requirement for non-trivial work —
      filed retroactively (19th review pass flagged its absence). Per-pass findings and resolutions
      are summarized below in the Progress log; the durable engineering rationale lives in
      `docs/architecture/action-model.md`.

## Validation

- [x] `python scripts/agent/runner.py quick-check` — green after every review-pass fix.
- [x] `python scripts/agent/runner.py validate-configs` / `validate-architecture`.
- [x] `python scripts/agent/runner.py postgresql-check` — green after every review-pass fix
      touching DB-backed tests.
- [x] Live `dev-up` -> `dev-smoke` -> `dev-down`: 11/11 `kernel_demo` atoms + 3/3 composite
      workflows passing, re-run after every change to `kernel_demo_smoke.py` or the composite
      workflow configs.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-18 | `score_match_by_rubric` gets a new required `overall_rationale` output field so `score_multidimensional_axes` can chain a real synthesis string, instead of bypassing it and chaining `compare_and_classify.rationale` directly. | See `docs/architecture/action-model.md`'s "kernel_demo composite workflow mapping notes" for the mapping-DSL reasoning. User explicitly chose this over extending the DSL when presented with both options (AskUserQuestion, team-lead-3 review). |
| 2026-08-18 | `extract -> detect_issues` in `composite_analyze_and_clarify_v1` stays order-only (`?scenario.input.taxonomy` / `?scenario.input.context`), not chained through a synthetic field. | Every synthesis-field attempt (`notes` on `extract`'s output) regressed something else: `detect_issues`' category-must-be-in-taxonomy contract when fed field names, `scenario.input.context` support, generation cost on 6 unrelated workflows, and `retry_extract_v1`'s single retry slot. Reverted after landing (17th/18th review passes) once the full cost was visible; documented as the ticket's own stated fallback ("clarify if adjacent consumption is not intended") rather than re-attempted a fourth time. |
| 2026-08-19 | Engineering rationale for why `overall_rationale` exists lives in `docs/architecture/action-model.md`, not in the JSON schema's `description` keyword. | `description` is serialized verbatim into the LLM system message on every provider call (`_schema_guidance_message` doesn't strip it) — internal engineering context there is a permanent token-cost regression, not documentation. |
| 2026-08-19 | `extract -> detect_issues` staying order-only re-confirmed (4th review round to raise it); instead of a 4th mapping attempt, `test_composite_workflow_matrix.py`'s `expected_step_dependencies` for `composite_analyze_and_clarify_v1` gets a comment explaining the missing dependency entry. This exec plan no longer cites gitignored `plans/ANY-219.md` as a required source. | Fetched the actual Linear ticket ANY-219 AC text directly, confirming `detect_issues`'s scenario-mapped inputs satisfy it; nothing changed since the 3 prior reverted mapping attempts. The gitignored file's substance was already duplicated in this file's Decision/Progress logs and `action-model.md`, so removing the references cost nothing and satisfies CLAUDE.md's "repo is the source of truth" rule. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-18 | Composite workflow configs, matrix test, and smoke-check coverage implemented and merged onto `feature/ANY-219`; 15+ code review passes and 2 team-lead reviews addressed iteratively (dead-code removal, PLR0911 lint-budget refactors, coverage-check hardening, docstring accuracy). | Await further review. |
| 2026-08-18 | Team-lead-3 review found the two composite workflows didn't prove real adjacent-artifact consumption for two step pairs; resolved `score_match_by_rubric -> score_multidimensional_axes` via the `overall_rationale` schema addition (user-approved), attempted the same pattern for `extract -> detect_issues`. | Await further review. |
| 2026-08-18 | Seventeenth pass found the `extract -> detect_issues` fix (a `taxonomy` mapping from `missing_fields`) was semantically wrong — it forced `detect_issues`' `category` field to a raw field name — and the composite matrix's dependency proof for it was vacuous (empty-array fixture). Replaced with a new `notes` field on `extract`'s output instead. | Await further review. |
| 2026-08-18 | Eighteenth pass found the `notes` field itself regressed `scenario.input.context` support, added unused-field generation cost to 6 other workflows, and added retry risk to `retry_extract_v1`. Reverted `notes` entirely; `extract -> detect_issues` returned to order-only with an inline comment explaining why. | Await further review. |
| 2026-08-19 | Nineteenth pass found the `overall_rationale` schema `description` gets serialized into every LLM call (permanent token-cost regression), the order-only comment had grown into permanent change-history prose describing an already-reverted attempt, and no exec plan existed for this non-trivial ticket. Fixed: removed the schema `description`, trimmed the workflow comment to a one-line pointer, added the "kernel_demo composite workflow mapping notes" section to `docs/architecture/action-model.md` as the durable, non-serialized home for the reasoning, and filed this exec plan. | Await further review. |
| 2026-08-19 | Twentieth pass found 5 gaps in the docs added by the nineteenth pass: a markdown heading inserted mid-section (an A11 bullet ended up under the new H2 instead of under A11), a "Follow-up debt" entry that said "None tracked." while describing real debt in the same breath, and the DSL-array-indexing reasoning restated in 3 places with no single source of truth. Fixed 3 of 5: reordered the misplaced A11 bullet, rewrote the debt entry without the self-contradicting prefix, and trimmed this file's Implementation-steps bullet and first Decision-log row to point at `action-model.md` instead of restating its reasoning. Declined 2: filing this plan retroactively can't be undone into "before coding," and `overall_rationale`'s required-not-optional cost tradeoff was already explicitly decided (AskUserQuestion, team-lead-3) with no new alternative offered here. | Await further review. |
| 2026-08-19 | Team-lead-4 review re-raised `extract -> detect_issues` order-only (P1) and flagged the exec plan's tracked-doc dependence on gitignored `plans/ANY-219.md` (P2). P1: verified against the actual Linear ticket ANY-219 AC text directly (not just repo docs) — `detect_issues`'s scenario-mapped inputs satisfy the AC's "mapped scenario" branch, and the matrix already proves `extract`'s output composes downstream via `generate_report`; declined a 4th mapping attempt (no new information since the 3 prior reverted attempts), but added a comment at `test_composite_workflow_matrix.py`'s `expected_step_dependencies` — the exact site the finding said "encodes the exception" silently. P2: confirmed the substantive rationale for all 5 `plans/ANY-219.md` references was already duplicated in tracked prose; stripped the references instead of committing the 161KB working-notes file. | Await further review. |

## Open questions

- None.

## Follow-up debt

- The mapping DSL still cannot index into an array (`docs/architecture/action-model.md`'s
  "kernel_demo composite workflow mapping notes" has the detail). The two workarounds landed by
  this ticket — a top-level synthesis scalar, or staying order-only — are not a substitute for
  real DSL array-indexing support if a future workflow hits the same gap and the need becomes
  recurring rather than a one-off.
