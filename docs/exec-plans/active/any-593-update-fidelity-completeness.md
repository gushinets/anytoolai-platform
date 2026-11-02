# Execution Plan: Client Update Writer update fidelity and completeness

## Status

- State: active
- Owner: agent
- Created: 2026-10-30
- Last updated: 2026-10-31
- Review date: 2026-10-31
- Next action: Live acceptance ANY-624; rerun blocked packaging and generated-doc checks.
- Blocker: PyPI DNS prevents wheel build; docs/generated/openapi.json remains stale.

## Goal

ANY-622: For client-facing facts included in the update, preserve the readiness/agreement
status, quantities with units and counted objects, identifiers and scope exclusions stated in
the freelancer's input. ANY-623 additionally requires every client-facing result, blocker,
request and next step mentioned in raw progress notes, even without addressing the client,
with explicit unknowns, within the length limit. Neither rule authorizes
disclosure of internal details or author directions. Add no unstated work, steps, results or findings.

## Scope

In scope: the Update v1 fidelity and completeness rules and Python regression tests pinning them.
Live acceptance (ANY-624), model selection, speaker identity,
author directions and call-to-action composition remain separate work. Existing terms and
exclusion rules from ANY-625/626/628 remain intact.

## Relevant docs

- `docs/architecture/config-model.md`
- `docs/architecture/llm-runtime.md`
- `docs/agent/coding-conventions.md`

## Contracts touched

Only the product-owned Update prompt text changes. API, DB, events, frontend, schemas,
provider policies and prompt reference/version remain unchanged.

## Implementation steps

- [x] Inspect the Update prompt, callers and neighboring product prompts for this pattern.
- [x] Add one fidelity rule after the existing factuality rule.
- [x] Add a normalized prompt-content regression test using the product's existing approach.
- [x] Run doctor, product tests, quick-check and documentation validation; record the gate failure.
- [x] Confirm ANY-623 completeness with the user and replace the contradictory ANY-622 caveat.
- [x] Pin client-facing inclusion, concrete requests, findings, totals and unknowns in a regression test.
- [x] Validate ANY-623 changes and record results, including environment failures.
- [x] Remove both explicit-address qualifiers; distinguish raw progress notes from private details.
- [x] Record the confirmed completeness decision in parent ANY-593 (comment ID
  `65afeef7-41bd-4a88-8f6e-b6c1cb1bab5d` on
  [ANY-593](https://linear.app/paveldik/issue/ANY-593/client-update-writer-update-ne-iskazhat-status-edinicy-i-sleduyushij)).

## Validation

- Review fix: 80 focused product, author-direction and speaker-identity tests passed;
  doctor, config/docs validation and `git diff --check` passed. Live generation was not run.
- ANY-623: 224 Freelancer Suite tests passed, including completeness, fidelity, author-direction
  and speaker-identity coverage. One packaging test failed because isolated `uv build` could not
  download `setuptools>=68` from PyPI (DNS failure); reproduced with the runner's writable cache.
- ANY-623: doctor, config and documentation validation, and `git diff --check` passed.
- ANY-623: `generate-docs --check` initially hit a LiteLLM import error while fetching its remote
  model-cost map. With `LITELLM_LOCAL_MODEL_COST_MAP=True`, it reached `DOCGEN001` for the existing
  stale OpenAPI file. No generated files or runtime dependencies were changed.
- Doctor passed using the IDE-configured Python 3.14.4 environment; no runtime pins changed.
- Product tests and shared author-direction/speaker-identity tests: 67 passed.
- Config, architecture and documentation validators passed inside quick-check.
- quick-check failed at generated-artifact validation: `DOCGEN001` reports stale
  `docs/generated/openapi.json`. Baseline pytest was not reached. No API code changed in this
  task; the unrelated generated file was left untouched.
- `git diff --check` passed.

The test checks the configured instruction, not generated-text behavior. Live acceptance
belongs to ANY-624: three repetitions each of U01 (RU), U03 (RU), U04 (EN) and U05 (RU).
Additional multilingual evaluation and model comparison are separate follow-up work, not
additional exit criteria for ANY-624.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-30 | Implement only ANY-622 on the current branch | ANY-623 introduces a separate completeness requirement |
| 2026-10-30 | Keep the existing prompt version and runtime | This is a product instruction correction, with no new execution contract |
| 2026-10-31 | Separate disclosure, inclusion and fidelity | Preserving included facts must neither leak internal data nor require exhaustive reporting |
| 2026-10-31 | Keep ANY-624's exact cases, languages and repetition count | Broader evaluation must not silently expand a separate task's acceptance contract |
| 2026-10-31 | User explicitly authorized ANY-623 implementation in chat after the completeness question | Require all client-facing results, blockers, requests and next steps; supersede the ANY-622 non-exhaustive caveat; Linear was not updated |
| 2026-10-31 | Require relevant facts mentioned in raw notes regardless of direct client address | U03's SKU findings and unknown count are progress facts; private details retain the disclosure rule |
| 2026-10-31 | Recorded the user-confirmed completeness decision in parent ANY-593, comment `65afeef7-41bd-4a88-8f6e-b6c1cb1bab5d`; reread and verified | Review P2 acceptance condition is now recorded; live acceptance remains in ANY-624 |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-10-30 | Doctor passed; fidelity rule and regression test added | Run validation |
| 2026-10-30 | 67 tests passed; validators passed; quick-check stopped at stale OpenAPI | Resolve generated-artifact drift separately, then rerun quick-check |
| 2026-10-31 | Replaced the blanket transfer instruction with fidelity of included client-facing facts; updated regression coverage for disclosure and length precedence | Run product tests and repository checks |
| 2026-10-31 | Doctor and all 224 Freelancer Suite tests passed; config, architecture and docs validation passed; quick-check still stopped at local OpenAPI drift | Live acceptance stays in ANY-624 |
| 2026-10-31 | ANY-623 completeness rule and regression test added; fidelity rule now delegates inclusion to completeness; doctor passed | Run automated validation; live acceptance stays in ANY-624 |
| 2026-10-31 | ANY-623: 224 tests passed, packaging blocked by PyPI DNS; config/docs validators and diff check passed; generated-doc check confirmed existing OpenAPI drift with the local model-cost map | Live acceptance in ANY-624; rerun blocked checks separately |
| 2026-10-31 | Review P1: removed both direct-address qualifiers, pinned raw-note inclusion and private-detail disclosure boundaries; 80 focused tests and config/docs checks passed | P2 remains blocked by unavailable Linear tools; GitHub thread reads also failed due to connectivity |

## Open questions

None for ANY-622.

Round 2 lint check found three pre-existing E501 lines in the product test file. The added
test's long string was split; no new E501 violation remains. Unrelated lines were left intact.

## Follow-up debt

Prompt adherence is nondeterministic; automated prompt-content checks cannot establish live
fidelity. The longer instruction may affect adherence to neighboring rules; verify in ANY-624.
If live failures warrant broader atom evaluation, compare prompt/model alternatives using
RU/EN/ES sets and luna, terra and sol under the owner's evaluation policy. This requires its
own follow-up scope and evidence; it is not part of ANY-624's required twelve generations.
