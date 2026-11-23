# Acceptance Builder Draft risks and client questions (ANY-894)

## Status

- State: active
- Owner: agent
- Linear: ANY-894
- Created: 2026-11-23
- Last updated: 2026-11-23
- Review date: 2026-11-30
- Next action: Product-owner review of the completed Draft iteration.
- Blocker: local repository-wide backend gates have unrelated environment failures detailed below.

## Goal

Show grounded risks, conflicting statements and concrete questions before agreeing acceptance criteria.

## Scope

Acceptance Builder Draft workflow, schema, prompt rules, renderer contract, web parser and
presenter, multilingual fixtures, regression suite, API and browser smoke tests, product docs.
Check retains its original extraction instructions and copy. Draft passes the contradiction
instruction in its A01 field description. This keeps a single extraction prompt.

## Implementation plan

1. Capture pre-change results for the two reported briefs.
2. Detect issues against the original brief and conditionally generate questions.
3. Render structured results in analysis-language order in recap and copy.
4. Exercise fixtures, multilingual controls, live runs and repository checks.

## Validation

The managed Python 3.12 environment passed doctor.

- Both QA briefs returned `analysis_language: ru` on the original implementation at
  `4fa80b28`. Its output lacked risk and question fields. For B it also treated the
  visual preference as a criterion. Both raw outputs are in
  `tests/fixtures/acceptance_builder_eval/any-894-pre-fix.evidence.json`.
- The existing extraction prompt requires checkable conditions. The more specific
  subjective-wish rule belongs to ANY-763. Draft now distinguishes stated assumptions
  from wishes in its input field descriptions.
- The fake certificate control executes extraction and detection, persists A05 as
  skipped and makes two provider calls. A05's happy fixture exists for atom schema
  coverage. The weak fixture executes all three actions.
- Stored v1 Draft results can be reopened through the session URL. The presenter
  displays their original lists and omits the risk assessment. A partially populated
  v2 result is rejected. Check retains its original copy in all seven languages.
- The focused Python product, prompt and evaluation tests passed (203), as did all
  API/worker bundle tests (58), focused web tests (87) and browser smoke tests (11).
  Smoke covered quota, clipboard, mobile layout and handoff replay on PostgreSQL.
- Config, architecture, docs and generated-doc drift checks passed with Python 3.12.
- The first live series surfaced a design-approval gap. The questions asked for style
  examples without asking how the client would approve the design. The revised A04
  and A05 prompts make the approval decision explicit. The three Russian combined-risk
  runs in the initial series passed. One initial B session exhausted transport retries.
- Final live series at `b1ff4c12` passed **18/18** across six briefs, three independent
  sessions each. B asked about both required pages/functions and design approval. The C
  translations in Russian, English and Spanish kept the launch figures grounded. All three
  contradiction runs retained the form criterion and both conflicting quotations. All three
  complete-control runs had empty issue and question lists. The tests revalidate the raw
  results in `tests/fixtures/acceptance_builder_eval/any-894-live-acceptance.evidence.json`.
- The original checkout's full-check stopped in the production stack detection tests.
  Its local production environment file introduces an additional Compose call. Both related
  tests passed in a clean checkout. The activation-marker permission test still failed there
  because the host requires interactive sudo to switch to nobody. The first quick-check also
  collected five stale language-eval expectations before they were updated. All 93 language
  evaluation tests passed after the update.
- The full freelancer product suite passed (1,667 tests), including wheel packaging and the captured live regression.
- Repository-wide frontend-check passed with one workspace and Vitest worker at a time,
  including lint, typecheck, the generated API contract check, 1,141 web-mirror tests
  and the production build. Earlier concurrent runs timed out in the CE-kit ESLint test.

## PR duplication check

SonarCloud attributed all 56 duplicated new lines to the repeated language dictionaries in
the Draft presenter. The product now stores its seven output-language dictionaries in
`outputWording.json`. Each label is keyed by the corresponding schema enum or list field.
The TypeScript presenter checks the catalog shape and selects wording from the analysis language.
All 87 focused web tests and the web typecheck passed after migration.

## Review fixes

1. Select the original closed Draft output schema for stored workflow v1 results. Preserve the
   public schema identity so the client can reopen them.
2. Render detected missing information in Open gaps alongside missing lists. Keep the question
   limit independent of which findings are shown.
3. Verify the result endpoint with historical data and render the saved seven-issue result through
   Recap and Copy.

The API regression returned the stored v1 payload and schema identity verbatim and rejected
the same payload under the current workflow version. The web regression used the captured
English Draft with seven issues and five questions. It verified every missing-information
description in the open recap and clipboard.

Validation passed for 217 focused Python tests, 36 PostgreSQL Result API tests, 1,142 web tests,
11 browser smoke tests, frontend typecheck and lint for the changed files, config and architecture
validation, generated docs, and Acceptance Builder deployment profile generation.
