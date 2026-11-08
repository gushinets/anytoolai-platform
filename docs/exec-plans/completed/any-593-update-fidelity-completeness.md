# Execution Plan: Client Update Writer update fidelity and completeness

## Status

- State: completed
- Owner: agent
- Created: 2026-10-30
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: none for this iteration; archived at the owner's request on 2026-11-06.
- Blocker: no new product defect established; default-model behavior and historical source/effort proof remain unverified.

The 2026-11-06 reconciliation below supersedes the earlier next actions and acceptance scope.
Earlier validation entries are retained as history, not current gate results.

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

## Parent reconciliation — 2026-11-06

### Scope and recommendation

The owner authorized reconciliation of completed implementation and acceptance, with an AC
matrix and a closure recommendation. No product changes, new paid evaluation, model rollout,
or further evaluation-tool development are included. Repository revision:
`9feaa5a7e00a7ea0704668cddaf2d35494f0b148`, branch `feature/ANY-593`.

Recommendation: ANY-593 is ready for the owner's closure decision as the QA parent for this
iteration, based on completed child tasks and the explicitly accepted texts. This does not
certify current default-model behavior or complete technical provenance for the historical
experiment. The parent AC does not explicitly require a production rollout or a particular
default model; the later accepted scope separates those decisions. Do not describe closure
as proof that the default luna model now meets the live criteria.

This follows the agreed iterative product approach: preserve the completed human acceptance
and its caveats, and take model rollout or tool hardening as separately scoped work. No issue
status, GitHub discussion, review thread or remote configuration was changed in this audit.

### Implementation and dependency evidence

Read directly from Linear on 2026-11-06:

| Item | Verified state | Evidence |
| --- | --- | --- |
| ANY-587, non-ASCII prompt serialization | Done | [Dependency](https://linear.app/paveldik/issue/ANY-587); existing Unicode/ASCII rendering regression tests pass locally |
| ANY-622, fidelity | Done; merged 2026-11-01 | [PR #228](https://github.com/gushinets/anytoolai-platform/pull/228), merge `d4905577` |
| ANY-623, completeness | Done; merged 2026-11-02 | [PR #229](https://github.com/gushinets/anytoolai-platform/pull/229), merge `3b62d6c3` |
| ANY-624, live acceptance | Done; merged 2026-11-06 | [PR #258](https://github.com/gushinets/anytoolai-platform/pull/258), merge `e4fb6fa4` |
| ANY-593, parent | In Progress | [Parent](https://linear.app/paveldik/issue/ANY-593); completeness decision in comment `65afeef7-41bd-4a88-8f6e-b6c1cb1bab5d`, created 2026-10-30 |

All three merge commits are present in the current branch history. The current
`packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/client_update_writer/prompts/update_compose_reply.v1.md`
is byte-identical to the prompt at accepted implementation commit `c243cbe3`. Its SHA-256 is
`fcd8e22d2d18fa13ce3d7c2543d83590f40ea9d86e1457984ee28fe964cdf14f`, also printed in the
attached acceptance report. This establishes prompt equivalence, not identity of the whole
runtime or a deployed container.

The prompt preserves included status, quantities, units, counted objects and exclusions;
requires client-relevant facts from raw notes and explicit unknowns; attributes disputed
internal completion claims; distinguishes commercial terms, private business information,
editorial instructions and actual work restrictions. Existing product tests pin these rules.

### Acceptance artifact audit

Read [ANY-624](https://linear.app/paveldik/issue/ANY-624) comment
`726ae489-a762-406b-bbf7-2fe7f3fd8931` and downloaded its attachment
`ANY-624-final-acceptance-270-PASS.html`. File size: 325,893 bytes; SHA-256:
`76422b72925ebbc0a378c88f424e953e24f54906f306a4884c4c8b19240d5265`.
Use the issue attachment for access; its signed download URL expires.

An independent read-only structural audit verified:

- 270 unique answer IDs: 12 main case/language combinations with 20 answers each and six
  variants with five answers each; every row records PASS with reviewer Putilin.
- All 18 displayed inputs, languages, tones and criteria match the tracked fixtures
  `tests/fixtures/client_update_writer_eval/screening.json` and
  `tests/fixtures/client_update_writer_eval/final_variants.json`.
- The four original task inputs match those fixtures verbatim. Confirmation timestamps group
  the report into 25 earlier decisions and 245 later decisions, consistent with the child record.
- All 810 input/output/criteria hashes recompute correctly from those fixtures and the
  complete JSON outputs in the HTML. Every output has nonempty text.
- The report names `openai/gpt-6.1-sol`, medium, and the same prompt hash as the current source.

This checks the attached texts and recorded decisions, not new semantic acceptance of all
270 outputs. One representative output for each original case was also inspected directly.
The 25 accepted seeds plus 245 new results and the 245 successful physical calls/no validation
retries are reported by the child task; raw ledger rows, browser traces and container identity
were not independently reconstructed here. HTML hashes do not prove model or reasoning effort.

### Acceptance criteria

| Criterion | Evidence and result | Boundary |
| --- | --- | --- |
| U01: prepared desktop mockup; next step sends both mockups for comments; no invented site work/day | Accepted 60 answers across RU/EN/ES. `U01-ru-1` explicitly includes agreed structure, prepared Figma desktop mockup, mobile work, photo request and sending both mockups; dispatch date remains unagreed. Current fidelity/completeness rules and regression tests cover it. | Existing human acceptance; no new 60-answer semantic review |
| U03: SKU mismatches and unknown completion date; no invented calculations | Accepted 60 answers. `U03-ru-1` preserves mismatches, unknown count, unchecked cards, unchanged prices pending the authoritative file and inability to estimate completion. | Existing human acceptance; prompt tests establish instructions, not probabilistic adherence |
| U04: do not endorse completion; explain both contradictions and ask about holding release | Accepted 60 answers. `U04-en-1` attributes the internal completion claim, contradicts it with 3/8 failing Safari tests, distinguishes sandbox/live, states the release-rule conflict and asks about holding release; investigation has no ETA. | Historical source/effort proof gaps remain separate from accepted text quality |
| U05: 12 interviews of 20 minutes; transcripts 11/12 by October 5; translation excluded; no payment demand | Accepted 60 answers. `U05-ru-1` preserves total/units, 7/3/2 status, both transcripts, deadline/timezone, contract amount and exclusion. It contains an inferred next step of finishing remaining checks, within the expressly accepted caveat class. | Do not claim every accepted answer is free of inferred wording; the human accepted these caveats |
| Repeats, full outputs and language quality | Attachment contains all 240 main and 30 variant outputs with matching inputs/criteria/hashes; all human decisions PASS. Original three-repeat requirement is exceeded in the accepted series. | No new lexical or semantic review of every answer; 270/270 is the recorded human verdict |

The 61 caveated answers are a subset of the 245 new answers, not extra failures. Accepted
overlapping categories: inferred next actions (49), not-a-payment-request explanations (21),
relative transcript deadline references (11), stronger release-hold wording (2), repeated
price-source requests (2). The child records the reviewer's explicit acceptance. Preserve
these limits rather than describing the corpus as mechanically perfect.

### GitHub review and CI

Read all inline comments including replies: PR #228 has 3 comments, #229 has 4 (2 replies),
and #258 has 29 (11 replies). PR #229 replies confirm the raw-notes completeness correction
and the parent decision. PR #258 replies distinguish corrected source/router/effort and
UI-outcome handling from the seven deferred tool limitations. The latest scope decision in
[ANY-624's execution plan](any-624-update-model-comparison.md) remains applicable. No thread
was resolved or comment posted during this audit.

GitHub reports all three PRs merged with successful required checks. Also checked CI for
the actual current commit `9feaa5a7`, rather than reusing the old `c243cbe3` full-check claim:

| Required current-commit check | Result |
| --- | --- |
| [full-check](https://github.com/gushinets/anytoolai-platform/actions/runs/42207230489/job/127857026758) | success |
| [postgresql-quota-concurrency](https://github.com/gushinets/anytoolai-platform/actions/runs/42207230489/job/127856810500) | success |
| [atoms-proof](https://github.com/gushinets/anytoolai-platform/actions/runs/42207230489/job/127856810797) | success |
| [baseline (windows-latest)](https://github.com/gushinets/anytoolai-platform/actions/runs/42207230489/job/127856810482) | success |
| [compose-smoke-prod](https://github.com/gushinets/anytoolai-platform/actions/runs/42207230489/job/127856810675) | success |

### Local validation and remaining boundaries

- Doctor passed using managed Python 3.12.13 and Node 24.18.0. Optional pnpm/Docker diagnostics
  warned; no frontend or live stack was started for this reconciliation.
- 108 focused tests passed: Client Update Writer product rules, shared author directions,
  commercial terms, work restrictions, and Unicode/ASCII prompt rendering. The standalone run
  uses `LITELLM_LOCAL_MODEL_COST_MAP=True`, as the repository baseline environment does; without
  it, the first standalone attempt failed during LiteLLM import, before test execution.
- Current config, architecture, documentation and generated-document validators passed inside
  the canonical quick-check. The old OpenAPI drift is not present. The first sandboxed bootstrap
  could not reach PyPI; the network-enabled retry built the local packages successfully.
- Canonical quick-check completed with exit 1: 3,377 passed, 12 skipped, 654 deselected,
  one failure in `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`.
  The network-enabled run reached the cross-user assertion, where `sudo -n -u nobody` returned
  `sudo: interactive authentication is required`. This is an unresolved local execution
  prerequisite, not a confirmed Update defect. No test was skipped, changed or suppressed to
  obtain a green result. The corresponding current-commit CI full-check is successful.
- No local full-check or new provider/browser run was performed. Current-commit full-check
  evidence above comes from GitHub CI.
- Documentation validation and whitespace checks passed after this report edit. The repository
  text scan found pre-existing local review-command references in plans for ANY-17, ANY-339,
  ANY-391, ANY-221 and ANY-227; this task adds none and leaves those unrelated documents alone.

`configs/kernel/litellm_router.yaml` still maps `anytoolai.default_text` to
`openai/gpt-6-luna` with medium reasoning. The accepted sol series does not verify this
default. Production deployment state was not inspected. Historical missing source/effort
evidence remains unverified; the accepted human verdict cannot restore it. Supporting tools
remain experimental, with the seven limitations documented in ANY-624's execution plan.

If rollout is requested separately, first identify the intended product/policy scope: the
default router alias is shared. Then verify effective backend model/effort and use the existing
U01/U03/U04/U05 RU/EN/ES criteria against that deployed configuration. A new paid matrix or
runtime change is not a prerequisite invented by this parent reconciliation.

## Archive decision — 2026-11-06

The owner requested moving this plan to completed. Existing acceptance caveats, deferred
tooling limitations and validation results remain recorded above. This archive operation
does not change Linear statuses or certify a default-model rollout.
