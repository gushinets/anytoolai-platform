# Execution Plan: Client Update Writer update fidelity

## Status

- State: active
- Owner: agent
- Created: 2026-10-30
- Last updated: 2026-10-30
- Review date: 2026-10-30
- Next action: Complete automated validation; live acceptance follows in ANY-624.
- Blocker: quick-check reports stale docs/generated/openapi.json before reaching baseline pytest.

## Goal

ANY-622: Update preserves the readiness/agreement status, quantities with units and counted
objects, and scope exclusions stated in the freelancer's input. It adds no unstated work,
steps, results or findings.

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
belongs to ANY-624: U01/U03/U04/U05 with repeats in RU/EN/ES, comparing luna with terra/sol
on failures rather than relying solely on further prompt changes.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-30 | Implement only ANY-622 on the current branch | ANY-623 introduces a separate completeness requirement |
| 2026-10-30 | Keep the existing prompt version and runtime | This is a product instruction correction, with no new execution contract |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-10-30 | Doctor passed; fidelity rule and regression test added | Run validation |
| 2026-10-30 | 67 tests passed; validators passed; quick-check stopped at stale OpenAPI | Resolve generated-artifact drift separately, then rerun quick-check |

## Open questions

None for ANY-622.

## Follow-up debt

Prompt adherence is nondeterministic; automated prompt-content checks cannot establish live
fidelity. The longer instruction may affect adherence to neighboring rules; verify in ANY-624.
