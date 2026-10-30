# Execution Plan: Client Update Writer update fidelity

## Status

- State: active
- Owner: agent
- Created: 2026-10-30
- Last updated: 2026-10-31
- Review date: 2026-10-31
- Next action: Complete automated validation; live acceptance follows in ANY-624.
- Blocker: quick-check reports stale docs/generated/openapi.json before reaching baseline pytest.

## Goal

ANY-622: For client-facing facts included in the update, preserve the readiness/agreement
status, quantities with units and counted objects, identifiers and scope exclusions stated in
the freelancer's input. Fidelity does not require exhaustive inclusion or authorize disclosure
of internal details or author directions. Add no unstated work, steps, results or findings.

## Scope

In scope: the Update v1 prompt and a Python regression test pinning its instruction.
Completeness (ANY-623), live acceptance (ANY-624), model selection, speaker identity,
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

## Validation

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

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-10-30 | Doctor passed; fidelity rule and regression test added | Run validation |
| 2026-10-30 | 67 tests passed; validators passed; quick-check stopped at stale OpenAPI | Resolve generated-artifact drift separately, then rerun quick-check |
| 2026-10-31 | Replaced the blanket transfer instruction with fidelity of included client-facing facts; updated regression coverage for disclosure and length precedence | Run product tests and repository checks |
| 2026-10-31 | Doctor and all 224 Freelancer Suite tests passed; config, architecture and docs validation passed; quick-check still stopped at local OpenAPI drift | Live acceptance stays in ANY-624 |

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
