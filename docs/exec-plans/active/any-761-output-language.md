# ANY-761: Brief Decoder and Acceptance Builder output language

## Status

- State: active
- Owner: agent
- Created: 2026-11-10
- Last updated: 2026-11-10
- Review date: 2026-11-10
- Next action: Commit/push authorized; required revision checks run in CI. Historical originals are non-blocking.
- Blocker: None identified in final code review; required CI checks pending.

## Goal

Keep all authored canonical output in the language of the source brief, unless the client
explicitly requests a different language for this analysis. Preserve facts, quotations and
machine identifiers. UI locale and the language requested for a deliverable are independent.

## Scope and decisions

Apply the same product-owned policy to all eight prompts in Brief Decoder and Acceptance
Builder. Pass `scenario.input.brief_text` to `data.source_brief` in the three document steps.
That field selects language only: documents cannot re-extract facts or revise findings/verdicts.
Keep JSON keys, enums, section IDs and fixed titles unchanged. Localize authored missing-list,
verdict and status sentences; retain extracted list items verbatim. For mixed briefs use the
main language of the client's instructions, ignoring quotations and technical identifiers;
on a tie use the first substantive instruction. Truly language-neutral input defaults to English.

No new dependency, runtime language detector, mapping DSL, frontend translation or
production model change. ProposalAI and Client Update Writer already have explicit policies;
their separate quality work remains outside this fix.

## Implementation steps

- [x] Update eight prompts and three document mappings.
- [x] Add RU/EN/ES inputs, provenance and canonical fixtures, covering hidden summary fields,
  quotations, facts, verdict, weak extraction and skipped questions.
- [x] Exercise real workflow mapping and retain existing English regression assertions.
- [x] Add bounded evidence collection and per-field human review for the three workflows.
- [x] Run repository checks and record acceptance limits (live acceptance FAIL; local full-check environment failure).

## Validation

Use the repository-managed Python 3.12 environment. Run product/API tests, quick-check,
full-check, config/architecture and documentation/generated checks. Live screening, when an
isolated credentialed stack is available: three scenarios × RU/EN/ES × two repeats × three
models (54). Final matrix: four families per scenario × RU/EN/ES × three repeats (108).
Retain failures and actual provider-call evidence; fixtures and prompt text checks do not
prove stochastic language behavior. Browser locale/recap/Copy checks require separate evidence.

## Acceptance limits

The issue contains BD-RU-08's full input and one failing output excerpt. Full historical
BD-RU-10, AB-D-RU-03 and AB-C-RU-01 inputs/outputs are absent from the repository and current
Linear issue/comments/attachments. New synthetic fixtures must not impersonate these originals.

## AC scope correction and remaining closure work

The original AC do not require budget/date to appear specifically in `acceptance_criteria`.
The recorded final 90 PASS / 18 FAIL are outcomes of the broader experimental rubric, not
18 ticket-AC violations. This clarification supersedes that implication in the progress log;
raw evidence and per-run reviews remain unchanged.

- Confirmed literal Russian-source language failures: three final BD outputs (RU-weak twice,
  RU-mixed once), plus one AB Luna screening comparison. Fix the remaining language behavior
  on the backend configuration intended for release. AB final language passes 72/72 on Sol;
  this does not validate unchanged Luna routing.
- Three additional BD failures (two English basic, one English-to-Russian override) belong
  to the agreed language-policy regression, rather than the literal Russian-source AC.
- Four AB Check list omissions retain the values elsewhere in canonical output: additional
  placement observations, not demonstrated AC violations and not mandatory fixes here.
- Six AB whole-output omissions and one BD budget-context drift are fact/semantic concerns.
  Their causation by this change is unproven. Resolve regression status or record owner
  disposition; fix confirmed regressions, without adding general extraction redesign to scope.
- One BD runtime schema failure is a real defect requiring regression/release triage, not
  demonstrated language failure; no canonical output was emitted. Mixed HTML verdict
  variability and optional year/character-count questions remain separate quality observations.
- Closure still needs repeated full-field evidence for the changed candidate, missing
  historical originals (or an explicit owner acceptance of that evidence gap), and existing
  review/repository gates. A new full three-model screening is not itself an additional AC.

The report's AC mapping and closure checklist govern the current conclusion. No new fixes,
provider calls, model changes or additional approval requests are part of this report correction.

## Progress log

- 2026-11-10: Confirmed all eight prompts and three mappings; existing neighboring language
  policies reviewed. Managed Python doctor passed. No local Docker Compose stack is running.
  Original QA evidence requested from the user; implementation can proceed independently.

- 2026-11-10: Current output schemas contradict the earlier analysis: root-level conditions
  require English narrative phrases. User approved removing these prose checks while retaining
  closed shapes and structured verdict/status invariants. English fixture consistency tests
  remain; multilingual canonical tests cover the same contract without a language dictionary.
- 2026-11-10: User approved proceeding with synthetic cases until historical originals arrive,
  and explicitly authorized the planned live evaluation and provider token costs.
- 2026-11-10: 206 targeted checks and 326 full product/collector checks passed. Three offline
  browser checks passed with English UI and Russian canonical fixtures, including recap and Copy.
  Backend full-check reached 3585 passes and one existing sudo-dependent environment failure;
  frontend verification passed separately. The first live workflow failed on an expired
  key and collection stopped; the owner will update the key. The worker is stopped while waiting.
  See [evidence and limits](../../experiments/any-761-language/README.md).

- 2026-11-10: Self-review retained existing structured schema invariants, checked all product
  consumers and found no PR for this branch. Hardened evidence completeness against missing
  action steps and added a negative test. New Python files pass Ruff; diff whitespace checks
  and final docs/generated checks pass. Existing local-skill references in other tickets'
  execution plans were left outside this change.

- 2026-11-10: Owner refreshed the live credential and requested continuation. The isolated
  Brief Decoder stack was rebuilt and verified; the first resumed Luna workflow completed
  successfully. Screening evidence is collected separately from the expired-key failure.

- 2026-11-10: Screening completed: 54/54 workflows, no runtime failures. Agent semantic
  inspection found BD 18/18 satisfactory; AB fact retention passed 11/12 on Sol and 0/12
  on Luna/Terra (omitted explicit deadline/budget). One Luna RU comparison also used the
  untranslated prose word "brief". All Check verdicts correctly rejected missing JSON.
  Final configuration selected before collection: Luna/medium for BD, Sol/medium for AB;
  36 + 72 runs, including three real browser journeys. Prompts stay frozen and production
  routing stays unchanged. These are agent assessments, not independent human acceptance.

- 2026-11-10: AB final matrix completed: 72/72 successful workflows; 72/72 agent language
  assessments pass, 10/72 fail extraction fact completeness (five Draft, five Check). Both
  real AB browser journeys passed input/recap/Copy checks with English UI. Every basic and
  weak Check was rejected as expected; all narrative statuses matched structured comparison.
  Mixed HTML descriptions produced variable verdicts across repeats, recorded as a separate
  judgment-quality limitation. Final BD 36-run collection is next; no product code changed
  during acceptance review and no failed evidence was replaced.

- 2026-11-10: Completed all 162 planned attempts (54 screening + 108 final), 484 physical
  provider calls, estimated ledger cost USD 1.2765. Final matrix: BD 28/36 agent PASS,
  Draft 31/36, Check 31/36. BD has six language failures, one budget-context error and one
  final-output schema failure after successful provider calls. AB has ten extraction
  fact-completeness failures. Language passes in 101/107 emitted final outputs; one failed
  workflow has no canonical output and remains unassessed for language. All 161 emitted
  screening/final outputs passed action/canonical, list, model and ledger consistency checks.
  All prompts/workflows/schemas stayed frozen. Three real browser journeys passed, including
  recap/Copy with English UI. The original expired-key attempt remains separate. Router
  restoration was verified by hash; production configuration is unchanged.
- 2026-11-10: Acceptance is FAIL, not ready for owner acceptance. Agent semantic reviews are
  separate from still-empty independent human review templates. Mixed Check verdicts vary
  when only an HTML delivery description is supplied. Original historical QA and CI for the
  uncommitted revision remain unverified. No additional source fixes or failed-case retries
  were made during this report-only acceptance continuation. Full findings and artifacts are
  in the linked evidence report above.
- 2026-11-10: Final docs/generated checks and diff whitespace validation passed. Temporary
  web/Compose services were stopped, retaining database volumes and evidence files.
- 2026-11-10: At the owner's request, corrected the acceptance report against the original
  AC. Separated confirmed language failures, planned multilingual regression, four non-blocking
  placement observations, unproven fact/runtime regressions and missing evidence. The machine
  summary now contains the same classification of all 18 original rubric failures. Earlier
  blanket treatment of all ten AB omissions as AC failures is superseded; results are retained.


## Implementation plan — language correction round

Owner authorized correction of remaining language failures only, with corrected Luna versus
Sol comparison for AB. Add a final step-specific language check in the eight product prompts;
explicitly prevent schema keys becoming authored labels/missing-field names in BD documents.
Keep facts, comparisons, structures and runtime unchanged. Run existing product/collector
regression, then frozen-input live evaluation: AB Luna and Sol basic/weak RU/EN/ES twice
(48 attempts); choose by actual language AC and cost, recording additional quality observations
separately. Validate BD all four families RU/EN/ES twice (24 attempts), then AB selected
model mixed/override RU/EN/ES twice (24 attempts). Retain failures and every canonical field;
no automatic replacement retries. Historical originals remain unavailable. Repeat browser
verification only if renderer/mapping changes; current prompt-only work uses existing UI proof.
Total bounded follow-up: 96 workflows; production model change requires evidence-backed choice.


### Evidence-backed backend model selection

Corrected AB Luna passed language 21/24; Sol 24/24 on identical basic/weak RU/EN/ES inputs,
two repeats each scenario. Select Sol/medium for AB only. Existing deployment-profile composition
selects its explicit provider policy; default Luna and fake canonical sources remain intact.
A named Sol backend policy/router alias and profile regression test make the selection reviewable.
This supersedes the earlier no-model-change assumption under the owner's current instruction.
Validate mixed/override through this native product profile, without collector model overrides.


## Language correction round outcome

- Added step-specific pre-return language checks to eight prompts, including natural missing-field
  names/labels in BD documents. No additional quality fixes were made.
- Completed all 96 bounded follow-up workflows. BD Luna 24/24 language PASS; corrected AB Luna
  21/24, Sol 24/24 on matched basic/weak inputs. Selected Sol/medium for AB only. A named backend
  policy/router alias and shared deployment-profile policy selection implement that choice,
  including generation and activation validators. Canonical fake sources and default Luna remain.
- Native AB Sol mixed/override profile verification passed language 24/24 without collector
  model overrides. Selected configuration totals 72/72 language PASS. All 96 emitted outputs
  passed artifact/list/model/ledger invariants; 1,346 authored fields inspected. 277 physical
  calls, including one normal semantic retry; estimated ledger cost USD 0.618269.
- Additional BD budget-context drift and AB whole-output omission remain explicit observations,
  not language failures or additional corrections. Mixed HTML judgments and earlier no-question
  runtime defect remain outside the correction. No schema/renderer/mapping changes this round.
- Current [follow-up report](../../experiments/any-761-language/round2.md) supersedes the older
  candidate's language conclusion, preserving its evidence. Historical originals, independent
  owner review and CI for this uncommitted revision remain pending. No production rollout or
  GitHub/Linear writes performed.

- Final verification: 326 product/collector checks passed; all profile/runner checks passed
  except the known passwordless-sudo environment test. Canonical quick-check passed config,
  architecture, docs and generated gates, with 3596 passed / 12 skipped / 655 deselected and
  two failures: sudo and a YAML test counting across policy boundaries. Corrected that test
  to cover the default and Sol policies separately; all 140 ConfigLoader/profile/activation
  targeted checks then passed. Full baseline not repeated after this test-only correction.
  Docs/generated/whitespace pass; no Ruff findings on changed lines. Stack stopped, volumes
  retained. Human review, historical originals and CI remain unverified.

- Owner final scope decision: missing full historical originals are not a closure blocker.
  Their absence remains an evidence limitation only. Final read-only review found no new
  blocking code defects; 204 targeted language/config/profile/activation tests passed.
  Owner delegated quick-check to CI and authorized commit/push of the current branch.
