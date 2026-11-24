# Acceptance Builder Draft risks and client questions (ANY-894)

## Status

- State: active
- Owner: agent
- Linear: ANY-894
- Created: 2026-11-23
- Last updated: 2026-11-24
- Review date: 2026-11-30
- Next action: Product-owner review of the corrected Draft v1 series (36/36).
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

## Second review fixes

1. Keep the Draft workflow, scenario and schema at v1. Accept both complete payload shapes in the
   public Draft schema. The active workflow always writes both issue and question lists.
2. Pass the A04 taxonomy to A05 in Acceptance Builder and Brief Decoder to validate category values
   before composing the final result.
3. Record which builds can reopen drafts after the preview is rolled back.

### Rollback boundary

The old Acceptance Builder API validates results against a closed schema that only has
`extracted`. Returning to that API with the same database makes Drafts saved by this change
unavailable, even when both new arrays are empty. A workflow version change cannot resolve this
schema mismatch. If the preview must roll back after accepting Drafts, retain its database and
use a build with the compatible Draft result schema to serve them. If the original API must be
restored, use the verified pre-release backup in a separate database and retain the candidate
database for recovery of results saved after the backup. See the
[Draft result rollback procedure](../../../infra/deployment/vps-release-runbook.md#rollback-acceptance-builder-draft-results).

The current schema accepted both captured historical results and all 18 enriched results. The
pre-change schema rejected all 18 enriched results. The Result API regression replayed the
historical payload under workflow v1. The A05 regression returned an unknown category on the
first provider response and verified that the next semantic attempt produced a valid result.

Backend validation passed with 2,458 tests and six skips. Config, architecture, docs and
generated-doc checks also passed.

## Third review

Validate text at its producing atom while a retry can repair it. Preserve subject, value and
qualification through Draft extraction, risk detection and question generation. Exercise the four
source briefs in Russian, English and Spanish, with three independent live Draft v1 sessions
per input. Retain the original captures for regressions and assess the candidate against the
source commitments, open decisions and contradictions.

Draft v1 now requests A01 field types matching its actual list and language constraints.
Brief Decoder opts in for its nonblank strings and nonempty lists. Existing generic extraction
types keep their previous meaning. A04 checks issue descriptions and optional evidence, and
A05 checks question text and rationale. The end-to-end regressions run a bad response followed
by a good one through the worker and read the published Draft through the result API. A second
bad response exhausts the configured retry budget and publishes no artifact.

The old EN series (3/3) and ES series (2/3) explicitly date the shop launch. Keep their raw
outputs as negative evidence. The new controls also catch missing contract terms, nonnumeric
invented requirements and linked questions that do not elicit a language decision.

For the isolated live stack, use the existing collector with
`run --suite draft-risks --scenario acceptance_builder.draft_v1 --project <compose-project>
--api-url <local-api> --out <new-directory>` in `scripts/agent/brief_language_eval.py`.
It defaults to three sessions per input, stores the runtime ledger and raw outputs, and produces
a review sheet bound to each result. Grade each result against the source and record the exact
unsupported or missing claim in the notes before running the collector's `report` command.

### Verification on the third-review candidate

- The backend, API, action, product and collector suite passed (2,948 tests, with 21
  PostgreSQL cases deselected). The three Acceptance Builder web suites passed all 88 tests.
  The focused acceptance controls passed again after tightening milestone and asset checks.
  Config, architecture, documentation and generated-doc checks passed.
- The repository full-check stopped after 4,283 passing backend checks and three infrastructure
  failures: two production Compose discovery tests and the activation marker access test for
  the unprivileged service account. These are the same local failures recorded above.
- The fresh Draft v1 live series completed all 36 independent sessions on the working tree
  based on `6ebfcfb3`. Every result was read through the Result API. The ledger recorded
  99 successful calls to `gpt-6.1-sol` under `sol_text_generation_v1`. Each session used
  an isolated local SQLite database.
- Source-based acceptance passed 27/36. The vague brief failed in all nine attempts. A01
  put appearance preferences or customer acquisition into acceptance criteria. All nine
  combined-feasibility cases kept delivery tomorrow, advertising on Friday and store
  launch undated, and asked which work must be ready. All nine contradictions elicited a
  language decision and preserved email submission. All nine complete briefs retained the
  agreed terms and generated zero issues and questions.
- The automated check passed 21/36. In six of the passing feasibility cases (three English
  and three Spanish), the question asked which parts must be ready for delivery without
  using a phrase matched by the priority check. The evidence records the automated verdict,
  source-based assessment and excerpt separately for each session.

### Draft extraction and feasibility evaluation follow-up

Use Draft-specific A01 field instructions to distinguish an agreed, verifiable condition from a
deliverable, preference or business aim. Replay the previous B and C results and verify that a
delivery-status question cannot pass for a scope choice. Repeat the same 36 live sessions.


The same 12 inputs produced 36 new Draft v1 results on the same live model and policy.
The worker recorded 99 successful provider calls. The result API served all 36 artifacts.
Source-based review and the automated acceptance checks both passed 36/36. The first
third-review series remains the negative control: the updated gate rejects its nine
vague drafts and accepts its six previously misclassified feasibility questions.
In all nine fresh vague drafts the website remains a deliverable and both criteria
and assumptions are marked missing. The combined-risk questions ask what must be ready
for delivery. All nine contradiction cases and nine complete controls passed again.

## Fourth review

Keep Draft v1 readable with its stored-artifact schema. Enforce portable nonblank authored
text during generation and publication, and label incomplete historical text in Recap and Copy.
Bind the scope decision to the evaluated brief, combined risk, question and review rubric.
Derive CLI filters from the selected suite. Verify retries, historical reads, review mutations
and collection manifests, then assess a fresh 36-session RU/EN/ES matrix.

The revised source-based rubric and product checks passed for all 36 fresh sessions on the
working tree based on `8366fc2a`. Each cell represents three distinct sessions. The API and
worker used isolated SQLite databases and the live backend policy `sol_text_generation_v1`.
All 99 calls to `gpt-6.1-sol` succeeded. Each published result was retrieved through the
Result API and accepted by the browser parser. Recap and Copy retained the findings and questions.

| Brief | RU | EN | ES | Decision checked |
| --- | --- | --- | --- | --- |
| Vague website | 3/3 | 3/3 | 3/3 | Website is a deliverable. Design approval and required features are open. |
| Store feasibility | 3/3 | 3/3 | 3/3 | The linked question asks which work must be ready at delivery tomorrow. Advertising starts Friday. |
| Conflicting languages | 3/3 | 3/3 | 3/3 | The client chooses Russian-only or bilingual delivery. The email form requirement is preserved. |
| Complete landing page | 3/3 | 3/3 | 3/3 | Agreed terms survive, including the form test, deadline, budget and revisions. No issues or questions. |

The archive in `tests/fixtures/acceptance_builder_eval/any-894-review-4-live.evidence.json`
contains the inputs, raw results, session ledgers, runtime fingerprints and digest-bound review
sheets. The previous 36-session grounding series also passes the updated offline controls.

All 138 focused evaluator and product acceptance checks passed. The API regressions covered
A01/A04/A05 correction, retry exhaustion, publication rejection and reopening both stored
shapes. A recovered A05 response was fetched from the API and passed through the actual
TypeScript Recap and Copy projections. The 36 Acceptance Builder web tests passed.

The local full-check recorded 4,294 backend passes, 12 skips and three environmental failures.
The two production Compose discovery tests passed against an isolated copy of the candidate
without local environment files. The activation-marker test requires non-interactive sudo
to run as nobody, which this host does not provide.
The complete frontend-check passed, including lint, type checking, 1,145 web-mirror tests,
the generated API contract check and the production builds.

### Fifth review

Restore historical A04/A05 read constraints and use the publication schema when an atom or
workflow produces a new result. Pin the authored-text boundary across schema, action and
browser validation, including Draft and Brief Decoder activation and formatted A07/A10 output.
Exercise saved results through the Result API, semantic retries, final publication, and web
presentation. Bind the contradiction control to a reviewed delivery-language choice and
verify manifest reads with an explicit UTF-8 encoding.

The root schemas for A04 and A05 match the historical v1 definitions. API tests reopen
saved artifacts across the seven registered workflows that publish these schemas. Empty
strings and malformed historical objects still fail the read contract. For new outputs,
the action retry loop, finalizer, and workflow publication use the write constraints.
A Draft containing only invisible acceptance criteria opens as incomplete and does not emit
a viewed activation. Brief Decoder checks the question text for activation. The Atom Lab
form now evaluates schema patterns in Unicode mode, including supplementary-plane characters.

The pinned character set comes from Unicode 17.0 White_Space, Cc, Cf and
Default_Ignorable_Code_Point. Tests compare Python and browser behavior with the published
Draft schema over every code point. Shared examples cover meaningful text with joining
characters, including Persian and emoji.

| Live control | RU | EN | ES |
| --- | --- | --- | --- |
| Vague business website | 3/3 | 3/3 | 3/3 |
| Store scope, budget and delivery | 3/3 | 3/3 | 3/3 |
| Conflicting language requirements | 3/3 | 3/3 | 3/3 |
| Complete brief | 3/3 | 3/3 | 3/3 |

All 36 new Draft v1 sessions returned results via the API. All 99 production-provider calls
on gpt-6.1-sol succeeded. The evidence includes the actual runtime fingerprints and review
sheets. One executor call was line-wrapped after collection, with identical Python syntax
trees. The six database-dependent tests skipped in the broad Python run also passed on a
temporary PostgreSQL 18 instance alongside the Result API and workflow-runner tests (84 passed).

The broad Python suite passed 2,970 tests. The full frontend check passed, including
349 Chromium cases for Atom Lab, 1,148 web-mirror tests, contract drift and production
builds. The manifest selections passed with Python UTF-8 mode disabled under the C locale
on Linux.

### Sixth review

Validate collected output against the planned scenario before enumerating review fields.
Current Draft evidence requires both issue and question arrays, plus a successful
`detect_issues` ledger entry. Only a confirmed empty issues list permits skipping
`generate_questions`. Use explicit opt-in when replaying historical output contracts.
Exercise malformed records through the CLI and regrade both 36-run archives.

The evaluator now reports incompatible output as FAIL and continues through the manifest.
A valid Draft with missing A04 evidence stays PENDING. CLI regressions cover all four
families, malformed arrays, an incomplete review directory, conditional A05, and a
collection run that saves the incompatible output and diagnostic. Separate tests replay the
historical Draft shapes through the archival path.

All 164 evaluator and product acceptance tests passed. Regrading the original review sheets
with the updated report command returned 36 PASS for review four and 36 PASS for review five.
Every family and language pair scored 3/3 in each archive. The captured files retained their
original bytes, and the regrade used the saved results and ledgers without new provider calls.

### Seventh review

Expose the existing historical Acceptance Builder contract through a report-only option
for unversioned ANY-761 archives. Mark new manifests with the current evidence contract.
Test the archive and current paths side by side, then rerun both saved Draft risk reports.

Require a pre-cutover restore rehearsal whenever the rollback path depends on a dump.
The ANY-894 rollback to the pre-change API requires this rehearsal even when the Alembic
revision matches. Use the existing isolated restore procedure and keep migration rehearsal
conditional on a schema change.

The same legacy Draft is FAIL in the default report and PASS in the explicit archive mode.
CLI regressions also cover archived Draft and Check documents, incomplete review decisions,
missing document steps, review digest mismatch, and rejection of current manifests and
Draft risk evidence in archive mode. The report leaves the original archive files intact.

All 173 evaluator and acceptance tests passed. The unchanged fourth and fifth review matrices
passed again in the default report, with 72 PASS, 0 FAIL, and 0 PENDING. Each case and language
combination scored 3/3 in each archive. The regrade used the saved outputs and provider ledgers.
