# ANY-761 language regression evidence

Latest result: **language PASS on the selected evaluated configurations — BD Luna 24/24,
AB Sol 48/48**. The completed 96-run correction/comparison is documented in the
[current follow-up report](round2.md), with [separate machine evidence](round2/summary.json).
AB model selection is now implemented in its backend deployment profile; default routing
for other products stays Luna. Historical QA originals are a non-blocking evidence limitation per the owner; required
revision checks are delegated to CI.
Additional observations were retained without correction, as requested.

## Previous candidate and corrected scope interpretation

The sections below describe the earlier 162-run candidate and its AC scope correction.
Its language FAIL is retained historical evidence, superseded for the new selected candidate
by the follow-up above. Its 90 PASS / 18 FAIL are the broader experimental rubric, not
18 violations of ticket AC. Original raw records and reviews remain unchanged.

## Acceptance scope correction

ANY-761 requires Russian authored content for Russian source material without another language
request, one product-owned language policy through all LLM steps independent of UI locale,
faithful quotations/identifiers, full canonical regression with fact/verdict checks, and retained
stochastic evidence. It does **not** require every stated budget or date to appear specifically
in `acceptance_criteria`. The product's extraction contract describes conditions the finished
work must satisfy; it does not explicitly classify every commercial term as such a condition.

The broader RU/EN/ES and override matrix remains useful regression evidence under the agreed
implementation plan. Its extra quality expectations must not silently become new ticket AC.
In particular, missing an item from a list is different from losing it from the whole output,
and a defect observed after a change is not proof that the change introduced it.

## Contract and implementation

All eight Brief Decoder / Acceptance Builder prompts use the original brief to select the
language of authored analysis. Explicit analysis-language requests take precedence; language
requested for a deliverable, quotations, technical identifiers and UI locale do not. The three
document steps receive the original brief only for language selection, with structured outputs
remaining authoritative for facts, lists and verdicts.

Acceptance Builder's schemas previously required English missing-list sentences, gap names,
verdict sentences and status labels. The owner approved removing those prose assertions.
Closed output shapes, nonempty content, identifiers, missing-field consistency and the
structured verdict/status relationship remain validated. Free-text agreement with those facts
is now a prompt and semantic-evaluation obligation, not a JSON Schema guarantee.

The language contract is repeated in product prompts without new runtime machinery; a test
requires the shared policy to agree across all eight. Existing English fixtures remain intact.

## Fixture provenance

The corpus contains 36 inputs: three scenarios × four families × RU/EN/ES. Families cover
basic requirements, weak/empty extraction, mixed quotations or deliverable language, and an
explicit different analysis language. Eighteen authored canonical outputs cover basic and weak
cases, including hidden summaries, lists, evidence, rationale and complete document sections.

The Russian basic Brief Decoder input is BD-RU-08 transcribed from the issue; its English and
Spanish inputs are translations. Its known failing sentence is retained in the corpus. All
expected outputs were authored for deterministic tests; they are not captured LLM responses.
The other cases have new `ANY761-...` IDs. Historical BD-RU-10, AB-D-RU-03 and AB-C-RU-01 are
unavailable; the owner approved proceeding with synthetic cases while those originals are pending.

## Validation observed on 2026-11-10

- Managed Python 3.12 doctor passed.
- Initial multilingual tests reproduced schema rejection of Russian/Spanish documents.
- After the schema correction, 206 targeted API/product/evidence tests passed.
- The full Freelancer Suite plus evidence collector tests passed: 326 tests.
- Config, architecture, docs and generated-document checks passed in the full-check run.
- The backend baseline reached 3585 passes, 12 skips and one environment failure:
  `test_activation_marker_is_readable_by_non_root_api_user` requires passwordless
  `sudo -u nobody`; this machine requires interactive authentication. No test was disabled.
- Frontend checks passed separately: lint, typecheck, unit/browser tests, generated API types
  and production builds.

`LITELLM_LOCAL_MODEL_COST_MAP=True` was used for offline checks to avoid the library's remote
catalog fetch at import. ASGI integration tests ran outside the filesystem/network sandbox
after the local AnyIO test client hung inside the sandbox; the same tests passed outside it.

## Earlier offline browser evidence

All three Russian basic cases passed in headless Chromium with UI locale `en`, mocked API
responses from the authored canonical fixtures, and the existing web application. The submitted
input exactly matched the fixture (no locale injection). Acceptance Builder's recap was opened;
summaries and model prose remained Russian. Clipboard content retained every expected extracted
item and comparison explanation; Brief Decoder's copy exactly matched its canonical document.

The JSON files contain submitted input, visible text and clipboard text. These are **offline
UI evidence**, not live workflow evidence. Existing fixed
English titles, missing-list copy and verdict/status labels remain part of the renderer contract.

- [Brief Decoder](ANY761-BD-RU-basic.json)
- [Acceptance Builder Draft](ANY761-AB-D-RU-basic.json)
- [Acceptance Builder Check](ANY761-AB-C-RU-basic.json)

## Live results

The owner refreshed the credential and authorized continuation. All 162 planned attempts are
retained in [the live evidence directory](live/summary.json), including failed outputs and
field-level decisions. There were 484 physical provider calls, all successful; one workflow
failed final schema validation after successful actions. The ledger estimates **USD 1.2765**
for this matrix; this is not a reconciled provider bill. Two skipped question steps explain
the difference from the maximum 486 logical calls. There were no extra retries of failed
matrix cases to replace their results.

The earlier [expired-key attempt](ANY761-BD-RU-basic--1.json) and its
[original manifest](manifest.json) remain separate. It produced no model output and recorded
two failed provider calls before stopping. It is excluded from the resumed 162-run matrix,
not overwritten or converted to PASS.

### Screening and model selection

All models used configured/requested `medium`: `openai/gpt-6-luna`, `openai/gpt-6.1-sol`,
`openai/gpt-6.1-terra`. Every screening workflow completed. The table counts complete-rubric
agent PASS under the original experimental rubric, including its stricter expectations for
extracted commercial facts. These counts are not ticket-AC pass rates.

| Scenario | Luna | Sol | Terra |
| --- | ---: | ---: | ---: |
| Brief Decoder | 6/6 | 6/6 | 6/6 |
| Acceptance Draft | 0/6 | 6/6 | 0/6 |
| Acceptance Check | 0/6 | 5/6 | 0/6 |

All 24 AB runs on Luna/Terra omitted budget or deadline from extracted criteria. One Luna
Russian comparison also used the untranslated prose word `brief`; 53/54 screening outputs
passed language inspection. Sol retained the facts in 11/12 AB outputs. Before the final
matrix, Luna was selected for BD because all three models passed screening and Luna cost less;
Sol was selected for AB because it retained facts much more reliably. These choices applied
only to the isolated evaluation backend. These results do not establish acceptance on the
unchanged production configuration. Production routing is unchanged; the isolated router was restored to its original
file, with its SHA-256 verified against the repository configuration.

### Final matrix

Each scenario has 36 attempts: four families × RU/EN/ES × three repeats. Language is evaluated
against the requested analysis language, including explicit overrides.

| Scenario/model | Workflow completed | Language PASS | Original experimental rubric PASS (not AC) |
| --- | ---: | ---: | ---: |
| Brief Decoder / Luna | 35/36 | 29/35 emitted outputs | 28/36 |
| Acceptance Draft / Sol | 36/36 | 36/36 | 31/36 |
| Acceptance Check / Sol | 36/36 | 36/36 | 31/36 |
| Total | 107/108 | 101/107 emitted outputs | 90/108 |

The failed BD workflow has no canonical output, so its language decisions remain unknown.
Every emitted canonical output across screening/final matched its action artifacts; AB lists
matched extraction verbatim. All 161 emitted outputs passed mechanical evidence-completeness
and actual-model checks. Agent inspection covered 2,580 authored fields. All 20 captured
prompt/workflow/schema files and registries had identical hashes across series and matched the
working tree. Deployment activation, provider-policy and quota files vary with the enabled
product; evaluated router models also vary. These deployment differences are captured, not
claimed to be identical source files.

### Confirmed language failures and planned regression failures

1. **BD still changes language in six final outputs, at multiple steps.** Russian input
   `Нужно что-нибудь хорошее.` twice produced English missing-field names in summary/sections.
   An English BD-RU-08 translation first produced Russian extraction and then, in a separate
   repeat, Russian questions/rationales. Russian analysis requested for an English brief left
   `thousand characters` in an extracted constraint; a Russian mixed case added `Deliverables:`
   to document prose. These are authored words, not JSON keys or source quotations. See the
   [weak-input review](live/final-bd-luna/ANY761-BD-RU-weak--1.agent-review.json),
   [extraction review](live/final-bd-luna/ANY761-BD-EN-basic--1.agent-review.json) and
   [question review](live/final-bd-luna/ANY761-BD-EN-basic--2.agent-review.json).
   Of these six, **three directly violate the Russian-source AC**: RU-weak repeats 1/2 and
   RU-mixed repeat 3. The two EN-basic failures and EN-to-RU override failure violate the
   implemented language policy and planned regression expectations; they are not three
   additional instances of the literal Russian-source AC.
2. **AB Luna has a confirmed Russian-source language failure in screening.** The authored
   comparison evidence says `В brief нужны PDF и JSON`; `brief` is neither a quotation nor
   a JSON key here. See the [screening review](live/screen-ab-c-luna/ANY761-AB-C-RU-basic--1.agent-review.json).
   Final AB language inspection passed 72/72 on Sol. That supports the evaluated Sol candidate,
   not acceptance of the unchanged Luna configuration. No production model switch was made.

### Fact-preservation observations requiring disposition, not ten automatic AC failures

1. **AB omits commercial facts from ten final extractions.** Five Draft outputs omit
   `500 EUR`, sometimes also `15 November`; five Check outputs omit those values from criteria.
   In four of those Check outputs the comparison/recap still contains the values, so this is
   not total canonical loss in all ten cases. One Check output loses the exact budget across
   the canonical result. The document faithfully copies already-incomplete extraction; the
   earliest observed omission is the shared extract step. See the
   [Draft example](live/final-ab-d-sol/ANY761-AB-D-RU-mixed--3.agent-review.json),
   [Check omission with retained comparison facts](live/final-ab-c-sol/ANY761-AB-C-RU-override--1.agent-review.json)
   and [original rubric failure inventory](live/summary.json).

   **Four Check cases are placement-only observations, not demonstrated AC violations:**
   RU-override--1, ES-mixed--1, EN-override--2 and ES-basic--3. The values survive elsewhere
   in the canonical output. No requirement to move or duplicate them into criteria is added.

   **Six cases are whole-output fact-retention concerns:** all five Draft failures and
   Check EN-override--1. They are relevant to the AC's instruction to check facts, but are
   not proven regressions caused by this language change. No frozen pre-change comparison
   exists. Before declaring the fact-preservation check satisfactory, determine whether the
   change loses previously retained facts, or record the existing extraction limitation and
   its owner-approved disposition. Do not require a general extraction redesign for ANY-761
   solely from these observations.
2. **One BD output asks about the wrong budget.** Russian article brief with Spanish-analysis
   override asks `¿Qué presupuesto aproximado tienen previsto para la reforma?` and adapts the
   article to renovation scope, instead of clarifying the fee for writing the commissioned
   article. The error is copied into next steps. See the
   [semantic review](live/final-bd-luna/ANY761-BD-RU-override--1.agent-review.json).
   This is a semantic-quality concern relevant to fact preservation; its relationship to
   the change is also unverified. It is not a failure of Russian-language output, since
   Spanish was explicitly requested. Apply the same regression/disposition check as above.

### Additional runtime and judgment observations

**One BD workflow fails final schema validation.** With no issues, the question step is
   skipped. The document emits `sections[3].metadata.kind = paragraph`, while the product
   schema requires `list`. All three executed actions and provider calls succeeded. The
   [original failed record](live/final-bd-luna/ANY761-BD-EN-mixed--3.json) is retained with no
   canonical output; a [read-only diagnostic reconstruction](live/final-bd-luna/ANY761-BD-EN-mixed--3.diagnostic.json)
   reproduces the exact error. The reconstruction is not an emitted successful result. The
   existing structural invariant was not weakened, and this case was not rerun. This is a
   real runtime defect and an unassessed language result, not a confirmed language-AC failure.
   Its pre-existing/change-induced status is unknown; triage it under the repository's
   regression/release requirements rather than inventing an additional ANY-761 language AC.

All basic and weak AB Check cases returned `does_not_meet` as expected; document explanations
preserved structured statuses/verdicts. Mixed HTML descriptions showed a separate judgment
limitation: the same Russian input produced `partially_meets`, `does_not_meet`, and `meets`
across repeats, depending on whether claimed delivery was treated as sufficient proof. No
actual HTML was supplied. Language success does not establish general acceptance-judgment
quality. This variability does not itself prove a changed verdict caused by the patch or a
document/comparison mismatch. Optional questions about the year or whether spaces count are
recorded as polish. These observations remain visible for separate product-quality work.

### Live browser and acceptance criteria

Three real Chromium journeys used English UI, exact Russian fixture inputs and the live local
API, without response mocks. AB recap was opened and inspected; hidden summaries were also
read in canonical evidence. Copy matched BD's full document and retained AB extracted lists
and comparison explanations. These journeys are the first Russian basic repeats within the
108-run final matrix, not additional workflows. JSON captures and screenshots:

- [BD journey](live/final-bd-luna/browser/ANY761-BD-RU-basic--1.json),
  [screenshot](live/final-bd-luna/browser/ANY761-BD-RU-basic--1.png).
- [Draft journey](live/final-ab-d-sol/browser/ANY761-AB-D-RU-basic--1.json),
  [screenshot](live/final-ab-d-sol/browser/ANY761-AB-D-RU-basic--1.png).
- [Check journey](live/final-ab-c-sol/browser/ANY761-AB-C-RU-basic--1.json),
  [screenshot](live/final-ab-c-sol/browser/ANY761-AB-C-RU-basic--1.png).

| Acceptance criterion | Evidence / decision |
| --- | --- |
| All authored Russian content remains Russian | FAIL: three final BD RU outputs retain English prose; one AB Luna screening output also fails. AB final language passes on Sol only. |
| Product-owned language policy through every LLM step; independent of UI | Implemented in eight prompts/three document mappings; real English-UI journeys pass. Policy text alone does not prove compliance. |
| Preserve brands, technical identifiers and verbatim quotes; do not translate keys/enums | Structural identifiers and quoted `Ready to ship` are retained; no separate confirmed blocker recorded for this AC. |
| Check facts and verdict throughout canonical output | Checked, with unresolved regression concerns: six AB whole-output omissions and one BD budget-context error. Four placement-only AB omissions do not establish an AC failure. Basic/weak verdicts and document/comparison consistency pass; mixed-case variability is a separate limitation. |
| Full canonical regression including historical QA | New fixtures and full-field live review present; BD-RU-08 input passes final RU basic 3/3. BD-RU-10, AB-D-RU-03 and AB-C-RU-01 originals remain unavailable. |
| Stochastic evidence supplements retained failures | Completed 54 + 108 attempts, all failures retained; no successful retry substitutes for a failed attempt. |

### What remains for closing ANY-761

1. **Correct the demonstrated language behavior on the intended backend configuration.**
   BD must localize authored missing-field names and labels for Russian weak/mixed input.
   Cover the extract/question/override failures in the already-planned language regression
   as well, so the correction does not merely move the failure to another language or step.
   For AB, either correct and validate the intended Luna configuration or explicitly select
   and validate another backend model; the Sol-only success is not evidence for Luna.
   This is an outcome requirement, not a prescribed prompt edit or model switch.
2. **Record fresh repeated evidence for the changed candidate**, inspecting all canonical
   prose, quotes, facts and verdict, including hidden fields and UI/Copy where affected.
   Retain the current failures; one successful retry does not erase them. A new full
   three-model screening is not an added ticket requirement; size verification to the change.
3. **Complete the missing historical regression evidence** for BD-RU-10 and the original
   AB-D-RU-03 / AB-C-RU-01 controls when supplied. BD-RU-08 already passes final RU basic 3/3.
   Permission to use synthetic cases did not turn them into the missing originals. If the
   originals remain unavailable, closure needs an explicit owner decision accepting that
   evidence gap rather than a claim that the original QA regression passed.
4. **Resolve the fact/regression uncertainty, not a new list-placement requirement.**
   Compare relevant pre-change behavior or otherwise establish causation for the six full
   AB omissions and BD budget-context drift. Fix any confirmed regression from this change;
   document and obtain owner disposition for pre-existing or unresolved quality limitations.
   Similarly triage the runtime failure before treating release validation as complete.
   None of this mandates moving budget/date into `acceptance_criteria` or perfecting AB's
   general extraction and judgment behavior in this ticket.
5. **Finish the existing review/repository gates for the chosen revision.** Independent
   review and CI are workflow/plan obligations, not newly discovered product AC. The local
   sudo-dependent check remains an environment limitation, not a language defect.

The mandatory product correction is the remaining language behavior. Historical evidence and
regression disposition are closure checks, not evidence that every quality observation needs
a code change here. This keeps the agreed iterative approach across products without hiding
confirmed failures or unverified facts.

Agent decisions are in `.agent-review.json`; separate `.review.json` templates remain unfilled
for independent human review. The canonical `report` command therefore still returns
PENDING/FAIL for the original experimental rubric, not a ticket-AC verdict or a falsely green
human gate. CI for the uncommitted revision is unverified;
the local full-check environment failure described above remains. No source changes were
made during this acceptance run. The next step is owner review of these findings and a scoped
correction decision, followed by fresh evidence for any changed behavior. The ticket remains
active and unaccepted; no GitHub/Linear writes or production rollout were performed.
Final documentation/generated checks and diff whitespace validation passed. The temporary web
server and isolated Compose stack were stopped after collection; PostgreSQL volumes and saved
evidence were retained.

## Reproduce collection

Start the isolated product stack with the repository runner after configuring a valid local
credential. Select models only in the isolated backend configuration; the collector never
changes the router. Use a new output directory for each series:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True .quick-check-venv/bin/python scripts/agent/brief_language_eval.py run \
  --api-url http://127.0.0.1:18782 --project anytoolai-e986bbcb \
  --scenario brief_decoder.decode_v1 --family basic --repeats 2 --out <new-directory>
```

Discover the current worktree's URL/project with the runner instead of copying those values
to another checkout. For the final matrix omit `--family` and use three repeats. Repeat for
`acceptance_builder.draft_v1` and `acceptance_builder.check_v1` with that product enabled.

Review every prose field, separating verbatim quotes from authored explanations, and every
fact/verdict criterion in the generated `.review.json` files. Record the reviewer and notes;
leave unknown decisions `null`. `report --out <directory>` fails closed on missing runs,
missing evidence, stale reviews or any FAIL/PENDING. Configured effort and requested ledger
effort are evidence, not provider confirmation; `confirmed_reasoning_effort` remains null.
