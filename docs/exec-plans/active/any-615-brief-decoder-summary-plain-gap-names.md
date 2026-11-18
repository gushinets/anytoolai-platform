# Execution Plan: ANY-615 Brief Decoder Summary Plain Gap Names

## Status

- State: active
- Owner: agent
- Created: 2026-11-16
- Last updated: 2026-11-18
- Review date: 2026-11-18
- Next action: monitor upstream security notices and remove the temporary fork after a verified
  official fix. Required checks on PR #279 own the final clean-environment CI validation.
- Blocker: no dependency-specific blocker found. Local full-check encountered unrelated test
  environment failures, recorded below; clean CI must pass before merge. User accepted ANY-615's
  live wording result; the separate runtime and extraction findings remain in ANY-884 and ANY-885.

## Goal

Brief Decoder summaries name missing information in ordinary words in the document's language,
never as machine field keys. Existing facts, readiness rules and the complete-brief branch stay
unchanged.

## Scope

- Map all six extracted brief fields to readable names in the existing v1 summary prompt.
- Prohibit internal missing-field notation in section titles, content and `summary`, while
  preserving literal identifiers and code formatting from client facts.
- Add Python regression checks for reported leaks, ordinary wording, all five summary fixtures
  (three original English cases and paired RU/ES cases) and the prompt contract, using raw YAML/JSON.
- Check sibling product prompts for the same instruction.

## Out of scope

ANY-849 input guidance, ANY-850 copy controls, schemas, workflows, DSL, UI and dependencies.
No prompt-reference or version changes. The user separately authorized live acceptance on 2026-11-17.
On 2026-11-18 the user additionally requested dependency remediation and a replacement assessment
for the picomatch CI blocker; that investigation is recorded below, separate from product behavior.

## Risks

Prompt-text and fake-provider fixture tests do not prove live model behavior. The authorized
30-run live series below covers B02/B04/B05 in Russian, English and Spanish and the exact noise
input. No raw gap notation was found, but one runtime failure prevents a clean end-to-end PASS.
The current model extracted B04 deliverables, so that historical missing-deliverables branch was
not reproduced by B04; all six missing fields were exercised by the English-fallback noise case.
The leak guard is a fixture regression check, not a runtime filter or a general language detector.
The test contract distinguishes complete source facts from newly generated narration. Only a
complete extracted value copied verbatim within standalone assertion boundaries can establish
source provenance. Identifiers, quote spans and partial text matches alone cannot. Text/line
boundaries, line-start list markers and sentence-ending punctuation (`.`, `!`, `?`) delimit
assertions; colons and semicolons do not detach a source match from a changed surrounding claim.
List syntax covers `-`, `+`, `*`, `•` and numeric markers ending in `.` or `)`, with indentation
and LF/CRLF. Expected EN/RU/ES language comes from test-case metadata, not language inference.
Untranslated internal keys outside copied facts are forbidden in RU/ES; English single-word
names can remain ordinary prose. After round 6, an unverified assertion containing a technical
field marker and an internal key requires review regardless of linking words, order or inline
list position. Sentences, line breaks and masked facts bound scope; internal dots such as v1.0
do not end an assertion. This conservative fixture rule can flag valid technical prose without
source evidence; it does not assert a semantic violation or filter production output. Positive gap completeness uses language-specific fixture words.
Arbitrary paraphrases, fragments, added quotation wrappers and interpretation beyond that contract
remain live-acceptance concerns. It may conservatively flag such valid rewrites for review.

## Implementation steps

- [x] Merge main `06d79037`, preserving both ANY-615 and ANY-762 prompt requirements.
- [x] Round 6: replace adjacency grammar with assertion-level technical-context review;
  preserve whole source facts and test the conservative boundary explicitly.
- [x] Round 6: bind historical ANY-762 evidence to verified source snapshots, not current prompts.
- [x] Round 6: add regressions, run validation and record results.

- [x] Round 5: validate every summary fixture against the product document schema and restore
  fixed English titles in RU/ES fixtures, with title mutation regressions.
- [x] Round 5: recognize bounded technical label phrases, preserving complete source facts;
  cover single-word keys, ordinary prose, assertion boundaries and fixture mutations.
- [x] Round 5: run Brief Decoder/Freelancer tests and documentation checks; record evidence.
- [x] Run doctor and validate this plan.
- [x] Add and exercise the regression tests, then update the prompt.
- [x] Run quick-check, validate-configs, validate-docs and full-check (baseline blockers below).
- [x] Record evidence and leave live acceptance pending.
- [x] Narrow the prompt prohibition and preserve source-provided identifiers.
- [x] Match known internal keys case-insensitively and check every copied text field.
- [x] Add source-identifier and document-location regressions; run focused validation.
- [x] Check all configured keys in technical notation and preserve ordinary prose.
- [x] Exempt exact source literal occurrences only; remove the document-wide key whitelist.
- [x] Add the full syntax/source-boundary matrix and fixture mutations; record validation.
- [x] Replace quote-based exemptions with complete copied-fact provenance.
- [x] Verify bare client facts, genuine source claims about missing database fields, and new gap claims.
- [x] Run regression checks and record the round 3 evidence and remaining limits.
- [x] Recognize line-start list prefixes without allowing changed inline assertions.
- [x] Check neighboring field/key words across punctuation within the same assertion.
- [x] Declare fixture languages and test translated gaps plus copied facts in EN/RU/ES.
- [x] Record round 4 regression and validation results.
- [x] Run all 30 authorized live scenarios, preserve outputs/failures and inspect generated text.
- [x] Record the failed noise scenario and separate extraction-completeness observation.
- [x] Obtain user acceptance/follow-up decision; separate findings tracked as ANY-884/ANY-885,
  without claiming 30/30 end-to-end PASS.

## Decision log

- 2026-11-17, user acceptance: ANY-615 accepted for gap wording; live findings moved to
  [ANY-884](https://linear.app/paveldik/issue/ANY-884) (section metadata) and
  [ANY-885](https://linear.app/paveldik/issue/ANY-885) (source language requirement extraction).
- 2026-11-17, review round 5: both regression gaps reproduced and fixes authorized. Reuse the
  product document schema as the structural contract. Expand the finite technical-label grammar
  instead of matching arbitrary intervening words; copied-fact provenance remains unchanged.
- 2026-11-16: use "technical field labels" in the prohibition so the obsolete raw-name
  instruction is absent even from negative examples.
- 2026-11-16: sibling scan found no matching raw-key instruction in ProposalAI or Client Update
  Writer; Acceptance Builder already maps missing entries to readable names. Scope stays local
  to Brief Decoder.
- 2026-11-16, review round 1: replace the overly broad snake-case ban with a closed set of
  internal keys, allowing literal occurrences from extracted values. Ordinary field names such
  as "budget" stay valid prose. Explicit technical missing-field labels remain forbidden.
  The source-key whitelist used here is superseded by review round 2 below.
- 2026-11-16, review round 1: the real copy function includes section titles as well as content
  and summary. All of those fields need fixture checks; frontend behavior stays unchanged.
- 2026-11-16, review round 2: replace the source-key whitelist with a per-occurrence syntax
  contract. Scan every configured key. Bare underscore keys, quoted/code identifiers and keys
  adjacent to a technical field marker are checked; ordinary single-word names remain prose.
- 2026-11-16, review round 2: source exemptions require an identical single-line literal span
  (matching backtick runs or ASCII single/double quotes). Preserve case, whitespace and delimiters;
  the exemption cannot authorize other occurrences. Whole code expressions and quoted messages
  are source facts too. Check raw extracted values, avoiding artificial quote characters
  introduced by JSON encoding. Mask verified spans with a non-whitespace barrier, so checking
  the rest cannot accidentally join words into a new technical label.
  This quote-based exemption is superseded by review round 3.
- 2026-11-16, review round 3: formatting cannot determine whether text represents a client fact
  or a brief gap. Keep extracted values separate and require a complete verbatim source fact
  within standalone assertion boundaries before exempting it. Inspect all remaining narration.
  A copied database-field fact stays valid with or without quotes; a different assertion about
  a missing brief field cannot inherit that source proof.
- 2026-11-17, review round 4: retain complete-fact provenance, with explicit list structure and
  expected document language. Technical labels are adjacent lexical words across punctuation,
  bounded by sentences, lines and masked facts. Replace ASCII-only grounding tokenization with
  Unicode words so Russian fixture facts are checked rather than silently ignored. Language
  metadata is test-owned; no runtime schema or language-detection dependency is introduced.

## Validation

### Live acceptance results (2026-11-17)

**29/30 end-to-end runs completed; one failed.** The targeted gap-wording check passed on all
30 generated documents, including the unpublished document recovered from the failed job's
persisted workflow state. This is not a fully green acceptance or authorization to close the issue.

Evidence: [complete inputs, outputs, ledger and agent assessment](any-615-live-acceptance.evidence.json).
The artifact retains exact source text, labelled translations, session/result IDs, all 120 physical
provider-call records, runtime hashes and the failed job's persisted state. Review is by the agent,
not independent human sign-off. Raw results were not edited, and no failed run was replaced.

| Input | Attempts | API results | Gap wording in generated documents |
| --- | ---: | ---: | --- |
| B02, EN/RU/ES | 9 | 9 | 9 pass; source CSV identifiers preserved |
| B04, EN/RU/ES | 9 | 9 | 9 pass; current extraction includes deliverables |
| B05, EN/RU/ES | 9 | 9 | 9 pass; separate fact omission below |
| `asdf ::: 12345 !!!`, unchanged | 3 | 2 | 3 pass; third document unpublished |

- Source revision: `1c79e1751110048d9ab369ee521dc72312a49730`, including merged ANY-761 language
  policy. Checkout/worker prompt and config hashes were checked before and after the series;
  generated live action bindings are recorded separately. Deployment fingerprint:
  `f59847e9394c77298ae92bf6f8d21a3a8c544df9cced8091a43d1b2582a54b8b`.
- Real local API → worker → Provider Gateway → OpenAI path, using the standard live profile.
  All 120 provider calls succeeded, with actual provider/model recorded as `openai`/`gpt-6-luna`,
  no fixture results and no retries. Reasoning `medium` is verified configuration, not returned
  provider reasoning telemetry. No model/prompt tuning or comparison runs were performed.
- **Estimated cost: USD 0.05809896**, below the authorized USD 2 cap; 199,655 input and 72,885
  output tokens. A local worker-only `LITELLM_LOCAL_MODEL_COST_MAP=True` override avoided a
  LiteLLM catalog-fetch import failure before collection. Cost comes from the bundled catalog
  and provider-call ledger, not a billing invoice. No production configuration changed.
- Inspected all **270 title/content/summary fields** across the 30 generated documents. The
  existing fixture lexical guard also reported zero flags; it was supplementary to reading the
  actual missing-field meanings and source facts. Valid Spanish synonyms were not rejected for
  differing from fixture stems. Machine keys inside structured JSON remain intentional.
- Authored EN/RU/ES content and summaries follow the input language. Fixed section titles remain
  English as explicitly required by the current template/schema. Noise has no language marker
  and used the English fallback; this does not establish RU/ES all-six-missing-field coverage.
  B02 retains `account_id`, `booked_at`, and `amount_eur`, including legitimate code formatting.
- The original October 2026 dates were retained. Past-deadline findings are expected at the
  November evaluation date. The first run's collection duration includes collector recovery;
  use individual provider timestamps/latency rather than that duration for performance analysis.

#### Findings and acceptance boundary

1. **LIVE-01 — noise attempt 3 produced no API result.** All four actions succeeded, but
   `document.sections[1].metadata.kind` was `paragraph`; the final schema requires `list`.
   Job error: `workflow_output_validation_failed`. Local validation of the preserved payload
   reproduces exactly this one schema error. The document uses ordinary gap wording but cannot
   count as an end-to-end success. See `runs[29].failure_diagnostics` in the evidence.
2. **LIVE-02 — separate extraction-completeness issue.** In B05 EN attempt 1, ES attempt 2 and
   RU attempt 3, the explicit requirement for Russian-language voice-over is absent from both
   extracted values and the final document (3/9 B05 runs). Original `brief_text` remains intact.
   This is outside ANY-615's gap-naming change; full extraction fidelity is not accepted here.

The finite wording pass is sufficient evidence for this iteration of ANY-615's prompt change,
but the runtime failure and separate completeness observation need a user follow-up decision.
No code fixes were made during acceptance. Browser rendering/clipboard and ANY-849 invalid-input
guidance were not tested. No GitHub/Linear write, push or issue closure was performed.

Fresh validation on the merged revision: **532 Brief Decoder tests passed**. The 29 API payloads
validate against the product output schema; the remaining persisted payload reproduces LIVE-01.
Documentation and whitespace checks passed. Full-check was not repeated for evidence/plan-only
changes; older validation records below are historical, not current CI status.

### Live acceptance plan and preparation history (2026-11-17, authorized)

- Freeze the current revision and prompt hashes. Run the real Brief Decoder four-atom workflow
  through the local HTTP API, worker, Provider Gateway and PostgreSQL call ledger. Use the standard
  live deployment profile, `openai/gpt-6-luna`, reasoning `medium`, without prompt/model tuning.
- Retain original QA inputs for B02/B04 (EN) and B05 (RU); explicitly label translated RU/EN/ES
  variants. Three attempts per case/language (27), plus three exact `asdf ::: 12345 !!!` attempts.
  Noise has no expected language: the input contract has no language selector, so do not inject
  a language instruction and misrepresent it as the original noise case.
- Preserve complete input/output, session and result IDs, prompt/config hashes, provider calls,
  tokens, estimated cost and failures. Inspect all section titles/content and summary for raw
  gap notation, missing-detail wording, language and preservation of actual client identifiers.
  Keep costs bounded at USD 2 estimated; stop on unknown cost or unfinished runtime work.
- This is backend live acceptance; browser/clipboard behavior is not exercised by these API runs.
  Report unrelated quality defects separately rather than silently changing the prompt mid-series.
  Record a reproducible evidence artifact and result; do not write to GitHub/Linear or close issues.
- Preparation completed: the standard live stack is running on isolated ports 8015/5455 with
  verified API/worker deployment fingerprints. All ten frozen inputs satisfy the product schema;
  original QA payload hashes match, and translated inputs are labelled. Automatic approval review
  rejected the first collector launch before execution because paid calls and external disclosure
  of these specific texts require explicit consent. Requested OpenAI transmission approval with a
  USD 2 estimated-cost cap. No model calls had occurred at that preparation stage.
- Explicit consent subsequently received for the prepared QA texts and all 30 OpenAI runs. The
  branch had meanwhile merged main at `1c79e175`, including ANY-761's language policy. Hash checks
  caught the stale worker before any provider call. Rebuilt against this current revision; the
  evidence evaluates the combined current prompt, not isolated pre-merge ANY-615.

### Initial implementation

- Doctor: system Python 3.14 lacks pytest/pydantic; the managed Python 3.12.13 doctor passes.
  Optional pnpm reports a local database warning under the sandbox.
- Regression before the prompt edit: 12 selected cases passed, the new prompt test failed on
  the obsolete raw-name instruction as expected.
- After the edit: all 43 Brief Decoder product tests passed, including all three summary
  fixtures. The leak guard rejects the QA strings and accepts ordinary English, Russian and
  Spanish wording; these are deterministic tests, not multilingual model evals.
- Quick-check: initial dependency bootstrap needed network access; the network-enabled run
  completed with **4,137 passed, 3 failed, 12 skipped, 717 deselected**. Existing baseline
  selection/skips were unchanged. Config, architecture, docs and generated-doc checks passed.
  Failures in unchanged `tests/test_runner.py`:
  - `test_prod_stack_running_reflects_compose_ps_output`: local production environment-file
    discovery adds a Compose config query, whose mocked response is a container ID, not JSON.
  - `test_prod_stack_running_propagates_timeout`: the same discovery reaches the 60-second
    config query instead of the mocked 10-second stack query.
  - `test_activation_marker_is_readable_by_non_root_api_user`: passwordless sudo to `nobody`
    is unavailable (`interactive authentication is required`).
- Standalone validate-configs: system Python lacks SQLAlchemy; rerun through the managed
  Python 3.12 interpreter passed. Standalone validate-docs passed after adding Review date.
- Full-check with `PYTEST_ADDOPTS=-x`: **313 passed, 1 failed, 717 deselected**; stopped at
  `test_prod_stack_running_reflects_compose_ps_output`, the same baseline failure. Frontend and
  subsequent product stages were not reached. No failures were ignored or marked expected.
- Independent full Freelancer product suite: **273 passed**, including wheel packaging, using
  the managed interpreter and `UV_CACHE_DIR` pointing to the repository's writable cache.
  The initial standalone attempt had 272 passed and one packaging failure using the default
  cache under the sandbox; using the same cache as the canonical runner resolved it.
- Collected sanitized failure context with the repository runner. Final validate-docs and
  whitespace checks passed. No live provider or PostgreSQL acceptance run was performed.

### Review round 1

- Reproduced all three findings before the fix: valid source identifiers were rejected,
  capitalized keys were missed, and an injected leaking title passed all three fixture checks.
- The prompt now limits the restriction to internal missing-field notation and explicitly
  preserves literal identifiers and code formatting from extracted client facts.
- The test detector uses the closed set of underscore-containing configured field names plus
  `missing_fields`, case-insensitively. Only extracted values can supply source exemptions;
  an exemption cannot cover a different key or a matching substring inside a longer identifier.
- Added 37 regression cases: capitalization, source identifiers (including names that collide
  with internal keys), exemption boundaries, and mutations of every title/content/summary field
  across all three summary fixtures. The prompt test also pins the narrowed prohibition.
- Full Freelancer product suite: **310 passed**, including packaging. The sandbox run had
  309 passed and a build dependency failure; a network-enabled rerun passed all tests.
- Brief Decoder API bundle slice: **21 passed** outside the sandbox with
  `LITELLM_LOCAL_MODEL_COST_MAP=True`, using the fake provider. The initial sandbox attempts
  encountered LiteLLM metadata-fetch import errors and then stalled at the first scenario;
  the stalled process was stopped before the bounded external rerun.
- Managed Python 3.12 doctor, validate-configs, validate-architecture, validate-docs and
  generated-document checks passed. Full-check with `PYTEST_ADDOPTS=-x` again stopped at
  `test_prod_stack_running_reflects_compose_ps_output`: **313 passed, 1 failed, 717 deselected**.
  This is the same local environment-file/mocked Compose mismatch documented above; subsequent
  frontend and product stages were not reached. Product tests were run separately in full.
- Live model acceptance remains pending. No schema, workflow, runtime, frontend or fixture JSON
  changes were needed.

### Review round 2

- Confirmed both findings through the actual fixture assertion: all four single-word keys in
  code-formatted technical sentences passed in EN/RU/ES, and a source column named
  `target_audience` hid the bare missing-field use while the field remained in `missing_fields`.
- Replaced the model, not just the examples: every configured key is scanned per occurrence;
  single-word names remain ordinary prose unless used in a literal or adjacent to a field marker.
  Exact source literal spans are masked independently before inspecting the remaining text.
  A copied identifier cannot authorize a bare or differently quoted/cased occurrence elsewhere.
- Raw extracted string values supply source evidence. JSON-created quotation marks, keys of
  dictionaries, `missing_fields`, and quote fragments in separate values cannot grant permission.
- Regression matrix covers all keys, EN/RU/ES technical contexts, delimiters, case, whitespace,
  ordinary prose, code expressions, quoted error messages, mixed allowed/forbidden occurrences,
  and mutations of real summary fixtures. All copied titles/content/summary checks remain active.
- Before implementation, the first expanded matrix had **118 failed, 137 passed** against the old
  guard. Final full Freelancer product suite: **494 passed**, including packaging; the suite grew
  by 184 cases. Managed Python 3.12 doctor, config, architecture and documentation validators pass.
- This round changes tests and plans only. API/full-check were not repeated: the prior API slice
  passed and the unchanged local full-check blockers are recorded above. No live provider run,
  GitHub comment, review-thread resolution or push was performed.
- Boundary remains explicit: this is a bounded single-line literal/adjacent-label syntax check,
  not a Markdown parser or semantic judge of an exact quote's use. Live B02/B04/B05 and noisy-input
  acceptance must still verify actual generated language and meaning.

### Review round 3

- Read the inline thread replies and reproduced both findings. The first expanded regression
  matrix against the previous implementation had **111 failed, 171 passed**; four failures were
  an overly strict test precondition for ordinary single-word names, corrected in the final tests.
- Replaced token provenance with whole-fact provenance. Extracted string values and individual
  list items remain separate. Only a complete, verbatim value in standalone statement boundaries
  is excluded from the internal-notation scan; bare and quoted identifiers use the same rule.
  An identifier taken from a rename request cannot authorize a new missing-field claim.
- Genuine client facts describing missing database fields remain valid, including EN/RU/ES;
  the presence of words like "field" or "missing" does not override verified source provenance.
  Changed prefixes/suffixes, partial names, separate source fragments and new gap assertions
  remain checked. Repeated facts and adjacent fact/gap statements are covered.
- Fixture mutations exercise both reported cases through the actual summary assertion, including
  complete facts from scalar values and list items while `target_audience` is still missing.
  Existing checks of every copied title, content and summary remain active.
- **307 Brief Decoder tests and 537 full Freelancer product tests passed**, including packaging;
  43 cases added since round 2. Config, architecture and documentation validation passed;
  `git diff --check` is clean.
- Ruff found pre-existing findings in the unchanged schema-version test (E501, PLR2004), also
  reproduced against HEAD. The long ANY-615 test string was wrapped; no lint suppressions added.
- Only tests and plans change in this round. API/full-check were not repeated: the prior API
  slice passed, and full-check's existing environment blockers remain documented above.
  No live provider evaluation, GitHub write or push was performed.

### Review round 4

- Confirmed all three findings after reading PR inline replies: punctuation hid single-word
  technical keys, list prefixes rejected real deliverables, and RU/ES raw keys passed. Also
  confirmed that the previous positive gap check incorrectly required English `audience` in a
  Russian gap sentence. All reproductions used the actual fixture assertion.
- Before implementation, the new punctuation/list fixture regressions had **67 failed, 1 passed**;
  the numbered `1. ` item already passed via the old sentence boundary. The new guard handles
  line-start list markers and independent adjacent claims without granting token-level exemptions.
- Full translated RU/ES extract/summary fixture pairs pass the same contract as English cases.
  New tests cover all copied titles, content and summary; all four single-word keys; copied
  English client facts inside RU/ES lists; genuine source statements about missing database
  fields; invalid new gap statements using the same identifiers; localized positive completeness;
  indentation, LF/CRLF, sentence/line boundaries and punctuation on either side of field markers.
- Final **532 Brief Decoder tests and 762 full Freelancer product tests passed**, including
  packaging and the schema checks for all four new fixture files. The suite grew by 225 cases.
  Missing project goals must be named separately from the target audience in RU/ES; regression
  mutations verify both rejection of the incomplete wording and acceptance after naming the goal.
  Managed Python 3.12 doctor, config, architecture and documentation validation passed;
  `git diff --check` is clean.
- Ruff reports only the same two pre-existing findings in the unchanged schema-version test
  (E501, PLR2004). No new findings or suppressions. The unrelated pre-existing literal review
  command references in other tickets were not edited.
- Changes are limited to tests, deterministic fixture data and plans. API/full-check were not
  repeated for this test-only change; historical results remain above. No live model run,
  GitHub write or push was performed. Live acceptance remains required before closure.

### Review round 5

- Read all PR inline comments and replies and reproduced both findings at `ffa82ef9`. All five
  summary fixtures passed the old fixture assertion, but the product document schema rejected
  four fixed titles in each RU/ES fixture. Eight added gap sentences (`field name` and
  `field identifier` for the four single-word keys) also passed the actual weak-fixture assertion.
- Restored the fixed English titles in RU/ES, retaining localized contents and summaries. Every
  summary fixture now validates against the existing product document schema with its `$defs`;
  title values/order and metadata rules are not duplicated in the test. Forty title mutations
  exercise rejection across all five fixture variants and every section.
- Extended the bounded label grammar: existing field nouns may be followed by `name`,
  `identifier`, `label` or `key`; `schema key` and `internal key` are also recognized. Plurals,
  case and punctuation are covered. Sentence/line boundaries, unrelated words and masked facts
  cannot be crossed. This is not a general semantic classifier for arbitrary paraphrases.
- Complete copied facts are still masked before label recognition. EN/RU/ES fixture mutations
  first accept a real client database-field fact, then reject an independently appended brief-gap
  assertion using the same identifier. Ordinary English, substring boundaries and existing list
  and provenance regressions remain green.
- The initial expanded selection had **96 failing regressions** against the previous guard.
  Final: **717 Brief Decoder tests and 1001 full Freelancer product tests passed**, including
  wheel packaging; 185 cases added. The first sandbox suite had 1000 passed and a wheel-build
  subprocess failure; the full rerun outside the sandbox passed with no skips or suppressions.
- Managed Python 3.12 doctor, documentation and whitespace checks passed. Ruff still reports
  the same pre-existing E501/PLR2004 in the unchanged schema-version test, reproduced on HEAD;
  its formatting suggestions are also confined to unchanged lines. No new lint finding.
- Changes are limited to tests, two summary fixtures and plans. No prompt/schema/runtime/UI
  changes, paid live calls, GitHub/Linear writes, commit or push. API/full-check were not repeated
  for this fixture/test-only change. The accepted live evidence is retained unchanged; separate
  production findings remain in ANY-884 and ANY-885.


### Review round 6 (2026-11-18)

- User explicitly requested both updating from main and fixing the repeated model defect.
  Read PR inline threads, including the reopened `field name is budget` reproduction. Merged
  `06d79037` as `951a6312`; resolved the summary-prompt conflict by retaining both ANY-615's
  gap wording/client-fact rules and ANY-762's deadline/budget-status requirements.
- Replaced before/after adjacency patterns and optional label suffixes with whole-assertion
  technical context. Source facts are masked first, as before. Every known key in an unverified
  assertion with a technical field marker requires review; no enumeration of linking verbs,
  modifiers or list separators. All keys in an inline list are covered, in either order.
- Kept punctuation/line/masked-fact boundaries and identifier word boundaries. Internal dots in
  versions or identifiers do not sever context. Ordinary English without a technical marker is
  accepted. A source identifier elsewhere cannot exempt a new gap assertion.
- Explicitly changed the old unsupported assumption that unrelated intervening words prove
  safety: e.g. `Choose a field name after confirming the budget.` now requires review unless
  it is a complete copied source fact. This is a conservative test contract, not a claim that
  every flagged sentence is semantically wrong. Unknown marker vocabulary and cross-assertion
  meaning remain outside this deterministic guard; live semantic review stays necessary.
- Added mutations covering all single-word keys, nine linking/order/modifier forms, EN/RU/ES,
  every copied document location, inline lists, and complete source facts. The initial expanded
  selection against the old implementation had **49 failures, 169 passes**. Final suite contains
  **837 Brief Decoder tests** (120 more than round 5); all **1416 Freelancer product tests passed**,
  including the new ANY-762 suite and wheel packaging.
- Integration initially exposed a historical-evidence test in ANY-762 comparing a captured
  worker hash to the current summary prompt: 1011 tests passed and that assertion failed. Bound
  those historical checks to frozen copies of the three reviewed source files instead. Each
  copy was recovered from `06d79037` and its SHA-256 exactly matches the existing worker ledger.
  Current prompt-contract checks remain active; neither historical evidence nor hashes were
  rewritten. Old live results are not represented as acceptance of the merged prompt.
- Managed doctor, config, architecture, documentation and whitespace validation passed. Ruff
  reports only the same pre-existing E501/PLR2004 in the untouched schema-version test.
- No new paid calls, GitHub/Linear writes or push. The merge commit is local; round 6 corrections
  are prepared for review. Full-check and browser/API journeys were not repeated. The earlier
  live acceptance, ANY-884 and ANY-885 remain separate from this deterministic fix.

### Picomatch replacement assessment (2026-11-18)

The user requested a replacement that unblocks CI without waiting for an upstream release or
suppressing Trivy. Evaluated an isolated archive of `cda3a03d`; the working dependency files
remain unchanged. A scoped fork is a different supplier, not a new upstream release.

Proposed temporary addition to the existing workspace overrides (retain the PostCSS override):

```yaml
picomatch: "npm:@ryotsu/picomatch@4.0.7-a"
```

Regenerate `pnpm-lock.yaml` with pnpm 10.34.1. The trial changed only this override and the
lockfile's picomatch resolutions: no parent upgrades, new runtime dependency chains or scanner
changes. All three original versions disappear from the dependency graph. All nine consumers
(visualizer, fdir, tinyglobby, unimport, unplugin-utils, unplugin, Vite, Vitest and WXT) resolve
the same fork. Their resolution/API checks cover callable matchers, arrays, ignores, dotfiles,
`scan`, RegExp-returning `makeRe` and Windows separators.

Verified artifact and security evidence:

- Candidate source: [secured-picomatch commit 3ab5a76](https://github.com/ryotsu-kankichi/secured-picomatch/commit/3ab5a7627d480259e3d9ca67fbc14c125d374f0e).
  All 10 published files match that commit byte-for-byte. npm registry signatures and
  provenance verification passed; the attested commit and tarball digest match. No runtime
  dependencies or install hooks. Preserve the exact version and pnpm integrity hash.
- Reviewed the real parser changes. Supported single-branch wildcard repetitions lose the
  redundant quantifier; unsupported complex forms become literal patterns. This changes
  executable code, not just the package name. The fork also incorporates upstream changes
  to POSIX bracket negation, punctuation classes, newlines and adjacent globstars.
- `+(*a)` against 80 `a` characters followed by `!` exceeded a two-second subprocess limit
  on each original version (2.3.2, 4.0.4, 4.0.7). The fork completed 42 attack cases covering
  default, Windows and capture options in about 0.11 seconds. Its full Mocha suite passed:
  **2004 tests**. These checks establish bounded evidence for this CVE, not proof that every
  possible glob or option is safe; explicitly disabling its safeguard remains unsafe.
- Trivy **0.76.1**, same database and unchanged CI flags
  `fs --scanners vuln --include-dev-deps --severity HIGH,CRITICAL --exit-code 1`:
  clean original checkout exits **1** with three picomatch findings; clean trial checkout
  exits **0**, with **zero High/Critical findings** across all seven lockfiles. No ignore
  rule, severity downgrade, dev-dependency exclusion or invented upstream version.
- `wxt build --analyze` passed, exercising the visualizer consumer that previously used 2.x.
  Canonical `frontend-check` exited **0**: frozen install, lint, typecheck, tests, generated
  API-type drift check and all workspace builds, including Next and WXT. **2009 tests passed**:
  55 shared-ui, 423 ce-kit, 1118 web-mirror, 349 Atom Lab browser cases and 64 Node tests.
  Node emitted timer-overflow warnings during web tests; no test failed or was suppressed.

Alternatives rejected: `zeromatch@1.0.0` does not preserve the RegExp-returning `makeRe`
contract used by Vite, and its published optional binaries only list Windows x64.
`@flupkejs/picomatch@1.3.0` lacks `scan`, array-pattern and ignore-option support required by
the consumers. Neither is a safe alias. Updating parent packages retains vulnerable upstream
picomatch. A local patch keeping the upstream identity does not remove the current
version-based Trivy finding.

Adoption limits: the fork has one maintainer and a short history. Future advisories filed
against upstream `picomatch` may not match the scoped package name, so manually track upstream
security notices and remove the override once an official fix passes these checks. The fork
does not preserve all capture/extglob semantics, and switching the visualizer from 2.x to 4.x
is a compatibility change. The visualizer also embeds a separate old matcher in its optional
browser analysis templates; an npm alias cannot rewrite bundled JavaScript. This is a remaining
code-derived risk for the developer report, not evidence of a defect in the shipped application.
Normal extension build does not enable analysis. Do not describe this trial as replacing every
embedded matcher or as blanket security certification.

No dependency changes applied to the working branch, GitHub writes, commit or push. Native
Windows execution, the backend/full-check suite and a fresh GitHub Actions run have not been
performed for this isolated dependency trial. Documentation and whitespace checks pass.
The repository-wide terminology check found pre-existing local-command references in unrelated
ANY-17, ANY-339, ANY-391, ANY-221 and ANY-227 plans; those files were left unchanged.

### Picomatch replacement adoption (2026-11-18, authorized)

The user explicitly approved applying `@ryotsu/picomatch@4.0.7-a`, regenerating the lockfile,
updating this plan, running full-check, committing/pushing to `feature/ANY-615`, and checking
PR #279 CI. No PR comments or reviews are part of this step.

- Added the exact workspace alias and its temporary maintenance/removal condition. Regenerated
  the lockfile using pnpm 10.34.1; it matches the isolated trial byte-for-byte. Kept the existing
  PostCSS override and all parent versions. No Trivy rules or workflow changes.
- Managed Python 3.12 / Node 24 doctor passed. Trivy 0.76.1 scanned a clean tracked-file copy
  containing the applied dependency files with the unchanged CI flags: exit **0**, no
  High/Critical findings. The earlier provenance, source and bounded attack checks remain
  applicable to the identical pinned artifact. Frozen installation and all nine consumer
  resolution/API checks also passed in the actual working checkout.
- Canonical local full-check ran and stopped in its backend baseline: **4251 passed, 3 failed,
  12 skipped, 720 deselected**. Two existing runner tests
  (`test_prod_stack_running_reflects_compose_ps_output` and
  `test_prod_stack_running_propagates_timeout`) accidentally consume the local production env
  file; both pass when the supported `ANYTOOLAI_PROD_ENV_FILE` override points to a nonexistent
  test-only path, matching clean CI. The third,
  `test_activation_marker_is_readable_by_non_root_api_user`, cannot switch to `nobody` because
  this host lacks passwordless sudo. No production env file, sudo policy, test or gate was
  changed. This is not a successful local full-check result.
- The full frontend check, 2009 tests and WXT analysis already passed on the identical candidate
  lockfile during the isolated assessment. The unrelated backend failures do not invalidate
  that evidence. Required CI will run full-check on the pushed commit in its clean environment;
  inspect the checks attached to the exact PR head before declaring the CI blocker resolved.
- The fork's maintenance, advisory-name and optional visualizer-template limitations from the
  assessment remain accepted constraints; this change does not claim to rewrite bundled code.
