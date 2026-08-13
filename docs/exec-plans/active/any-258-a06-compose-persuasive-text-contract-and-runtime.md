# Execution Plan: ANY-258 A06 text.compose_persuasive_text Contract And Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-08-13 (retroactive — see decision log)
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: none outstanding from this plan's own scope; ready for PR once reviewed.
- Blocker: none

## Goal

Implement the product-neutral `text.compose_persuasive_text` atom (legacy A06 `generate_proposal`)
as a strict, independently runnable JSON-schema contract — `context`/`objective`/optional
`audience`/`angle`/`constraints` in, `text` out — executed through the existing
`StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, without creating a platform
`generate_proposal` action or leaking ProposalAI/anti-AI/non-native product semantics into
platform-owned contracts.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders; `constraints{tone,length,language,format}` as an explicit generic
  object.
- `PersuasiveTextCrossValidator`: `constraints.length` enforcement (with integer-valued-float
  coercion) and `constraints.format` markup checks the static output schema cannot express.
- Product-neutral prompt (`compose_persuasive_text.v1.md`) and
  `kernel_demo.compose_persuasive_text_v1` product-level action config/fake-provider fixture,
  grounded strictly in the caller-supplied `context`.
- Deterministic fake-provider execution through `ActionRunner`, validated output artifact with
  action/provider/artifact event lineage, and a validation-retry proof through
  `StructuredLlmActionExecutor`.
- Focused platform-actions test coverage (schema boundary cases, cross-validator accept/reject
  cases) plus config/architecture/docs/quick-check gates.
- Markup detection consolidated onto the same parser-backed helpers (`_has_markup`/`_has_html_tag`)
  already used by the sibling A07 `ComposeReplyCrossValidator`, so both atoms enforce one
  definition of "markup" instead of two independently-hardened implementations.

### Out of scope

- The sibling A20c atoms (`text.synthesize_angle` / ANY-259, `text.generate_gap_rewrites` /
  ANY-260).
- A real (non-fake) LLM provider adapter for this or any atom.
- Any pre-existing bug in the already-merged A07 `ComposeReplyCrossValidator` not touched by this
  diff (e.g. `max_length` float coercion, `output_format == "markdown"` not being validated at
  all) — noted to the user but intentionally left for a separate ANY-252 follow-up.

## Relevant docs

- `docs/architecture/action-model.md` — `A06 generate_proposal | text.compose_persuasive_text`
  mapping row, with the explicit note that `generate_proposal` must never become a platform action
  type.
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none directly (action-runner atom; no workflow/scenario wiring required by this ticket).
- DB: none (existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config: `configs/kernel/schemas/compose_persuasive_text_{input,output}.schema.json` (now
  strict), `configs/kernel/products/kernel_demo/{prompts,action_configs}.yaml` (new
  `compose_persuasive_text_v1` entries), new prompt
  `configs/kernel/products/kernel_demo/prompts/compose_persuasive_text.v1.md`,
  `tests/fixtures/provider/fake_provider_outputs/kernel_demo.compose_persuasive_text_v1.json`
  (new; grounded strictly in the fixture's `context` input).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: none.

## Implementation steps

- [x] Design the input/output JSON schemas (`context` object, `objective` required non-empty,
      optional `audience`/`angle`, `constraints{tone,length,language,format}`); close outer
      schemas with `additionalProperties: false`.
- [x] Write the product-neutral prompt `compose_persuasive_text.v1.md`.
- [x] Add the `kernel_demo.compose_persuasive_text_v1` product-level action config and prompt
      registration.
- [x] Add the deterministic fake-provider fixture.
- [x] Add `PersuasiveTextCrossValidator` and register it in the production composition root
      (`apps/platform-worker/.../composition.py`) and in the test-side `_build_runner`/workflow
      builder helpers.
- [x] Add ActionRunner and `StructuredLlmActionExecutor` retry tests with full event lineage.
- [x] Add focused schema/cross-validator boundary tests (missing/unexpected properties,
      enum/range violations, malformed output).
- [x] Harden markup detection through six rounds of `/code-review` (allowlist gaps, false
      positives, format-cross-checking, float-length coercion, two quadratic-regex fixes,
      missing third cross-validator registration site).
- [x] Post-merge (`1283e1c`, merging main's ANY-252/ANY-254): fixed the resulting docs staleness
      (`config-registry.md` alphabetical reorder) and verified no cross-validator registration was
      silently dropped by the merge (unlike the ANY-254 case).
- [x] Consolidate A06's standalone regex-based markup detector onto A07's shared parser-backed
      `_has_markup`/`_has_html_tag` helpers, and drop the `format == "markdown"`
      decorative-token requirement to match A07 (team-lead review #1; also closes the seventh-pass
      `/code-review` finding that the two independent detectors disagreed on identical input).
- [x] Ground the fake-provider fixture's persuasive text strictly in its `context` input instead of
      inventing unsupplied facts, and remove a dead/unreachable A04 taxonomy re-check left over as
      merge residue in `DetectIssuesByTaxonomyCrossValidator` (team-lead review #2).
- [x] Regenerate generated action/config documentation (`generate-docs --check`).
- [x] Add this execution plan (retroactive — see decision log) and fill in the PR description's
      placeholder sections (team-lead review #2).
- [x] Final `quick-check` pass.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -k "persuasive_text or compose_persuasive" -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check`
- [ ] `python scripts/agent/runner.py postgresql-check` — not run in this environment (no local
      Postgres available); Postgres-gated tests collect correctly. Same pre-existing sandbox
      limitation noted on ANY-252/ANY-253/ANY-254.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-11 | Implemented `PersuasiveTextCrossValidator` with its own regex-based HTML/Markdown detector rather than reusing A07's helpers | A07 (`ComposeReplyCrossValidator`) lived on an unmerged sibling branch at the time, so no shared implementation was available to reuse in-tree |
| 2026-08-11 to 2026-08-11 | Hardened the regex detector through six `/code-review` rounds instead of switching to a real parser immediately | Kept the diff minimal per-round while the true fix (a shared parser-backed detector) waited on A07 actually merging into `main` |
| 2026-08-13 | Consolidated onto A07's shared `_has_markup`/`_has_html_tag` (markdown-it-py-backed) helpers and deleted the ~130-line regex allowlist machinery, after `main` merged and made the shared helpers available | Team-lead review #1: the two independent detectors diverged on identical input (e.g. spaced `*emphasis*`); one canonical definition removes the divergence and the six rounds of allowlist maintenance debt at once |
| 2026-08-13 | Dropped the `constraints.format == "markdown"` decorative-markup-token requirement | Team-lead review #1: the prompt only says "format accordingly," not "must contain a decorative construct"; a plain paragraph is valid Markdown, and the sibling A07 validator doesn't require this either |
| 2026-08-13 | Rewrote the fake-provider fixture text and its matching `test_action_runner.py` assertion to reference only `product`/`deadline` facts actually present in the test's `context` input | Team-lead review #2: the previous fixture text asserted a "discounted rate," "this quarter," a team, and a "rollout" not present anywhere in the input, contradicting the prompt's grounding rule and locking invented claims in as expected behavior |
| 2026-08-13 | Deleted the dead `isinstance(taxonomy, list) or not taxonomy` re-check in `DetectIssuesByTaxonomyCrossValidator` (A04) | Team-lead review #2: `_optional_membership_set` already guarantees a non-empty list whenever it returns non-`None`, making the second check unreachable; it was merge residue unnecessarily touching A04 code from an A06 PR |
| 2026-08-13 | Added this execution plan retroactively, after implementation and two team-lead review rounds had already landed | `AGENTS.md:69-76` requires an execution plan under `docs/exec-plans/active/` for any non-trivial work before coding; team-lead review #2 flagged that no such plan existed, mirroring the same gap found and closed the same way on ANY-252/ANY-254 |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-11 | Implemented strict input/output schemas, prompt, `kernel_demo.compose_persuasive_text_v1` config/fixture, `PersuasiveTextCrossValidator`, and initial ActionRunner/retry tests | Address six rounds of `/code-review` markup-detection findings |
| 2026-08-11 | Hardened HTML/Markdown detection through six `/code-review` rounds (allowlist expansion, false-positive fixes, format-cross-checking, float-length coercion, two quadratic-regex fixes, third registration site) | Commit and open PR |
| 2026-08-13 | Merged `main` (ANY-252/ANY-254), fixed resulting doc staleness, verified no cross-validator wiring was silently dropped | Address team-lead review #1 |
| 2026-08-13 | Consolidated markup detection onto A07's shared parser-backed helpers, dropped the markdown decorative-token requirement, removed dead/duplicate test spy-gateway classes | Address team-lead review #2 |
| 2026-08-13 | Grounded the fixture/test in its actual input context, removed the dead A04 taxonomy re-check, added this execution plan and filled in the PR description | Confirm `quick-check` is green end-to-end |

## Open questions

- None outstanding.

## Follow-up debt

- None outstanding for this atom. Two pre-existing bugs were found in the already-merged sibling
  A07 `ComposeReplyCrossValidator` while verifying markup-detection parity (not introduced by this
  diff, out of scope here): `constraints.max_length` lacks the integer-valued-float coercion this
  ticket added for A06's `length`, and `constraints.output_format == "markdown"` is never
  validated at all. Flagged to the user; not fixed here.
