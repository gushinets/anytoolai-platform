# ANY-761: Brief Decoder and Acceptance Builder output language

## Status

- State: active
- Owner: agent
- Created: 2026-11-10
- Last updated: 2026-11-10
- Review date: 2026-11-10
- Next action: Required CI and owner review for the reviewed follow-up revision.
- Blocker: Current-revision CI and owner approval pending.
- Current PR: https://github.com/gushinets/anytoolai-platform/pull/265
- Experiment and AC report: [issue comment](https://linear.app/paveldik/issue/ANY-761#comment-2c6c63bc-f1da-4494-9c29-aca4c8310ef1); duplicated in the PR description.
- Raw experiment captures are retained locally outside git; they are not a repository deliverable.

## Goal and actual acceptance scope

Keep all authored result prose in the source brief's language unless the client explicitly
requests another analysis language. UI locale and deliverable language are independent.
Preserve quotations, brands, technical identifiers, facts and structured verdict/status.
Regress full canonical output, including hidden fields, and preserve unsuccessful experimental
outcomes in the published report. A date/budget need not appear specifically in criteria.
Missing historical QA originals are a non-blocking evidence limit per the owner.

## Implementation plan

- [x] Apply one product-owned language policy to every BD/AB LLM step. Each step uses the
  original brief, including BD's final document via the existing open data mapping.
- [x] Keep the existing pre-production AB v1 contract. Require analysis-language metadata;
  remove AB's independent model document and its two A10 calls. Draft uses A01, Check A01+A11.
- [x] Generate AB recap and Copy from the same structured authority and language metadata.
  Preserve upstream items/evidence/rationale; enforce verdict/status and missing-list invariants.
  Do not restore English prose constraints. Wording covers seven app languages, with neutral
  markers for others. Development artifacts without language metadata are unsupported.
- [x] Add RU/EN/ES canonical fixtures and workflow/API/client regressions for weak extraction,
  quotes, mixed input, explicit overrides, hidden fields, Copy and contradictory recap.
- [x] Compare corrected AB Luna with Sol before model selection. Keep Sol/medium for AB through
  backend deployment generation/activation; BD and other products retain default Luna.
- [x] Run bounded synthetic live experiments and real RU-analysis/EN-UI browser/clipboard checks.
  Keep initial FAIL, candidate comparison and final evidence distinct in the published report.
- [x] Publish the complete experiment and remaining caveats in the issue comment and PR,
  rather than committing raw JSON/ledger/screenshot directories.
- [ ] Require CI and owner approval for the reviewed follow-up revision.

## Verification and limits

Latest contract correction: 375 Python tests, 467 web tests, web lint/typecheck passed.
Final read-only review: 286 targeted API/language/profile/activation tests passed. These test
sets overlap; counts are not additive. Earlier canonical frontend-check passed lint/typecheck,
generated API-contract check, builds and frontend/browser tests. Config/architecture/docs/
generated/whitespace checks passed. Full local baseline was delegated to CI by the owner.
The earlier green PR checks belong to head 0f273b8e and do not validate this follow-up.

Final selected language evidence: BD Luna24/24 plus AB Sol48/48 and three additional live AB
browser/clipboard journeys. Changing temporary v2 names back to v1 did not change schema bodies
or prompts: all75 saved AB payloads replayed against current schemas. This was offline contract
replay, not a new live deployment. Full experiment stages, failures, costs, selection rationale
and AC mapping belong in the external report, not this execution plan.

Additional budget/date omissions, BD renovation-budget semantics, mixed HTML judgment and
the earlier no-question runtime failure remain outside the authorized language correction.
Agent semantic assessment is finite; independent human QA and production rollout are unclaimed.
Isolated stack stopped with volumes retained; router restored and checked against the repository.


## Implementation plan — SonarCloud path traversal

The CLI currently interpolates suite case IDs and manifest run keys into filesystem paths.
Use one product-evidence filename boundary in both run/report: permit only the existing ASCII
JSON filename format, resolve it beneath the chosen output directory, and reject escapes before
reading/writing evidence. Preflight all planned run names before Docker/provider calls or output
directory creation. Keep JSON content as data through json.dump, and create evidence files
exclusively so failures/duplicates cannot overwrite captures. Add negative CLI regressions for
POSIX/Windows traversal, absolute names and malformed names, plus a normal run/review/report
round trip and overwrite protection. No prompt/model/output-contract changes or paid live runs.
Verify targeted tests, lint/docs/config checks, commit and push on feature/ANY-761; inspect the
new Sonar result without suppressing or resolving the finding manually.

Path traversal correction validated:96 targeted collector/product tests passed, including
unsafe suite IDs, manifest keys, ordinary review flow, overwrite protection and resolved-path
escapes. Real filesystem symlink checks passed locally for manifest/result/review. Ruff and
config/architecture/docs/generated/whitespace checks passed. No provider calls or product/prompt
changes; full baseline delegated to CI. Commit/push authorized; Sonar reanalysis remains pending.


## Implementation plan — mobile smoke recap states

The first text match now belongs to the collapsed structured recap. Scope the mobile long-token
assertion to the result region's copy paragraph, assert the recap starts collapsed, and verify
page width before and after opening the recap. Assert that the recap token becomes visible so
the expanded-width check cannot pass while content stays hidden. Keep product styling unchanged.
Run lint/typecheck and the complete canonical acceptance-builder-smoke against an isolated fake
provider dev stack, stop that stack with volumes retained, then commit/push on feature/ANY-761.
No new experiment directories or paid model calls.

Mobile smoke correction validated: canonical acceptance-builder-smoke passed11/11 in headless
Chromium against the isolated fake-provider stack, with no skips/retries. The long-token test
checked page width with recap collapsed and expanded and confirmed expanded token visibility.
Smoke-package lint/typecheck and web production build passed. Stack stopped with volumes
retained; no paid model calls or product styling changes. Commit/push authorized.


## Implementation plan — merge main

Merge origin/main into the existing feature branch without rewriting history. Preserve main's
JSON/ICU message catalogs and shared parser guards while retaining ANY-761 recap labels and
analysis-language validation. Keep both runner test additions. Verify web tests, lint/typecheck,
runner/evidence regressions and config/architecture checks before committing and pushing.

Merge verification:922 web tests and49 focused runner/evidence tests passed; web lint/typecheck,
config/architecture/docs/generated checks passed. The broader runner/evidence run had332 passes,
12 environment skips and3 failures: two prod-stack tests consumed the local prod env file and
passed when rerun with an isolated env path; the non-root activation-marker test requires
passwordless sudo unavailable here. The affected helper/test bodies are unchanged from main.
No suppression or unrelated test fix; full CI, browser smoke and paid live evals were not rerun.


## Implementation plan — review round 2 language metadata

Validate AB analysis_language against the case expected_language before a report can PASS.
Use the current contract tag syntax and compare primary language subtags, so es-MX matches es.
Keep authored-prose decisions mandatory. Retained legacy outputs with a document and the
validated generate_document ledger step remain historical evidence; do not retrofit metadata.
Test RU/EN/ES Draft/Check, missing/invalid/wrong tags, regional tags, empty extraction and the
report exit code. Re-evaluate saved captures read-only, compare old/new statuses, preserve
original files and reviews, and record aggregate results here without raw evidence directories.
Run focused checks, commit and push; no live provider calls.

Review round2 verification:73 collector/regression tests and Ruff passed. Doctor, documentation,
generated-documentation and whitespace checks passed. No provider calls or product changes.

Read-only offline recheck found255 saved AB captures:75 current-contract outputs all have valid
metadata matching the case's expected analysis language;180 legacy document outputs retain
their historical ledger/prose evaluation and are not counted as metadata passes. Replayed
original agent reviews and blank independent-human templates against both the pre-fix and
corrected evaluator: all statuses are unchanged. The current-contract agent results remain
73 PASS /2 FAIL: Draft24/24, initial Check22/24, corrected Check24/24, browser3/3. The two
initial Check failures remain failures; this does not supersede the original experiment.
The selected final subset remains Draft24 + corrected Check24 + browser3 PASS.

For72 numbered current-contract API captures, also replayed the complete report command using
temporary copies: agent reviews yielded70 PASS (exit0) /2 FAIL (exit1); all72 blank human
templates remained PENDING (exit1). Three browser records use a nonnumeric attempt identifier,
so their metadata and review_status were checked directly, not through the numbered-run CLI.
SHA-256 comparison confirms all1043 files in the saved evidence tree are unchanged, including
original captures, reviews and reports. No raw evidence was added to git. This is a metadata
and evaluator replay, not a new human prose review or live experiment; full CI is pending.


## Implementation plan — recipe language regression

Preserve the November11 Russian recipe report and its unknown production SHA in the case
provenance. Add the exact RU input plus EN/ES translations as distinct weak-family regressions.
Run three attempts per language on the unchanged selected BD Luna/medium deployment, recording
source SHA, dirty diff and effective worker prompt/config hashes. Review every canonical prose
field, including hidden summary and rephrased document questions; verify actual browser Copy
against the complete document. Retain all outcomes and the original negative report. Add
reviewed canonical fixtures and offline backend/Copy regressions. Do not implement ANY-849,
change prompts/models, or commit raw logs. Summarize results here, verify, commit and push.

### Recipe verification — 2026-11-16

Original November11 report retained in the regression case: Russian input
`Рецепт борща: свёкла, капуста, говядина. Варить два часа.` reportedly produced English
goal/risks and English rephrased questions in the final document. That production SHA is
unknown. These new results do not invalidate the original report. English and Spanish controls
use `Borscht recipe: beetroot, cabbage, beef. Cook for two hours.` and
`Receta de borsch: remolacha, col, carne de res. Cocinar durante dos horas.`

Evaluated runtime source: `bbf3c0d5e6b219afe2be133b634d88dce03c7eea`; working tree changes
were tests/fixtures/this report only. No prompt, provider, schema or application changes.
Isolated profile: brief_decoder, default_text_generation_v1, unmetered; configured alias
anytoolai.default_text selects openai/gpt-6-luna with reasoning_effort=medium. Both API and
worker verified effective deployment fingerprint
`0c3b33970bf9d771bc3d6b48558f332aa2c27dbfdbc5b3e37c43dfc01def65fd`.
Worker configuration/prompt snapshot digest:
`f4270c645d17a52c83216fca01532bb36a6bfa01f9c6ef57f5a283be510dc490`.
Router SHA-256: `dede022d99bc94440ea14f212cc669d939a39b51dbb73e8d0ef83ef5510aa1d2`.
All nine before/after worker snapshots matched. The ledger records gpt-6-luna on every call;
medium is verified configuration, not an independently echoed provider reasoning measurement.

| Source language | Attempts | Full canonical language review | Actual browser Copy |
| --- | --- | --- | --- |
| Russian original | 3 | 3 PASS | 3 exact matches |
| English translation | 3 | 3 PASS | 3 exact matches |
| Spanish translation | 3 | 3 FAIL under strict language review | 3 exact matches |

All nine workflows completed and outputs validate against the current canonical schema.
Reviewed145 authored fields: extraction, issues/evidence, questions/rationale, every document
section and hidden summary. Nine real Chromium journeys used English UI, real local API and
real clipboard permissions; the actual Copy text matched all canonical document sections and
summary byte-for-byte. No responses were mocked. The Russian standalone and document-rephrased
questions remained Russian in all three attempts. Recipe ingredients and cooking duration were
preserved; Russian outputs did not mistake cooking duration for a client deadline.

Preserved supplementary findings: every Spanish summary uses `El brief ...`; attempt1 also
uses `La brief ...` in issue evidence. These authored occurrences are marked FAIL, including
the corresponding Copy criterion. Attempt1 additionally puts `durante dos horas` in deadline.
Do not fold these into a claim of9/9 language success. No prompt/model iteration was attempted;
the authorized Russian regression is covered, and input sufficiency/recipe-as-project UX
remains outside this work in ANY-849.

Nine completed runs made37 successful physical provider calls (one A04 validation retry on
English attempt1), estimated USD0.010665795. A separate initial Russian attempt failed with
HTTP401 before output/Copy; its two failed ledger calls were preserved. After the owner
renewed the local key, the nine-run series used a separate capture location. No failed result
was overwritten. Agent decisions are separate from the original blank human review templates;
full report replay yields6 PASS /3 FAIL, while independent human reviews remain pending.
SHA-256 checks preserved all46 original files in the completed series. Raw capture/ledger/
clipboard/trace files remain local, outside git.

The checked-in Russian canonical fixture is the exact reviewed first live output, not an
authored substitute. It now participates in schema and full fake-provider workflow regressions.
Copy regression verifies that this Russian document is unchanged under RU/EN/ES UI. Translated
inputs are retained for future evals, but no passing Spanish canonical fixture is claimed.

Verification completed:140 Python tests passed (133 collector/product-schema regressions and
7 multilingual API workflows, including the new Russian capture), plus33 targeted BD/Copy web
tests. Initial broad web run had924 passes and one new-test selector error; the selector was
corrected to the existing Russian button label and all33 targeted tests then passed. Web
lint/typecheck, Ruff, doctor, docs/generated and whitespace checks passed. Full CI is not
claimed. The live stack and web server were stopped; database volumes retained.
