# Execution Plan: ANY-615 Brief Decoder Summary Plain Gap Names

## Status

- State: active
- Owner: agent
- Created: 2026-11-16
- Last updated: 2026-11-17
- Review date: 2026-11-17
- Next action: review the recorded live findings and decide follow-up scope; collection is complete.
- Blocker: live acceptance is not fully green. Noise attempt 3 failed final output validation
  (`key-details.metadata.kind = paragraph`, schema requires `list`); 29/30 API results completed.

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
names can remain ordinary prose. Positive gap completeness uses language-specific fixture words.
Arbitrary paraphrases, fragments, added quotation wrappers and interpretation beyond that contract
remain live-acceptance concerns. It may conservatively flag such valid rewrites for review.

## Implementation steps

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
- [ ] Obtain user acceptance/follow-up decision; do not claim 30/30 end-to-end PASS.

## Decision log

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
