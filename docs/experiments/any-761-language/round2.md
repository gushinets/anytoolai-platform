# ANY-761 language correction and repeated AC verification

The evaluated language behavior passes on the selected backend configuration: **BD Luna
24/24 and AB Sol 48/48**. These are agent semantic assessments of all authored canonical
fields. Historical QA originals are a non-blocking evidence limitation under the owner's final
scope clarification. Required revision checks will run in CI, as requested. Additional quality observations were retained separately.
This follow-up supersedes the previous candidate's language FAIL; it does not rewrite its evidence.

## Change and scope

Each of the eight product prompts now ends with a check for its own authored fields against
the analysis language selected from the original brief. BD's document prompt explicitly
requires natural names for missing facts and list labels, even when extraction is empty.
Short labels and descriptive units follow that language; source quotations, dates, amounts,
brands, technical identifiers and enums remain permitted exceptions. No language detector,
translation step, runtime schema relaxation or additional dependency was added.

AB Luna still failed language after that correction. Sol/medium was selected using the
same frozen basic/weak RU/EN/ES inputs and prompts, with two repeats per scenario. The choice
is implemented in the backend deployment profile, not only in the evaluation harness:

- `sol_text_generation_v1` resolves to router alias `anytoolai.sol_text`,
  `openai/gpt-6.1-sol`, reasoning `medium`.
- Deployment generation and both activation validators share the explicit AB policy selection.
  Default text routing remains Luna; canonical product sources remain on the fake test policy.
- Tests cover metered/unmetered profiles, actual router resolution, unchanged BD selection,
  unchanged canonical source fingerprint, and rejection of an incorrect AB activation policy.
- This is a repository configuration change, not a production deployment. The isolated
  router was restored and its hash matched the repository router after collection.

## Live comparison and follow-up

[Machine summary and full failure inventory](round2/summary.json) links all seven series by
name. Every run retains its original input, canonical output, action artifacts, provider ledger,
source snapshot, untouched human-review template and separate agent review. All 96 workflow
attempts succeeded; no failed workflow was replaced with a successful manual retry.

| Series | Workflows | Language PASS | Ledger cost estimate, USD |
| --- | ---: | ---: | ---: |
| BD Luna, all four families | 24 | 24 | 0.028596 |
| AB Luna Draft, basic/weak | 12 | 12 | 0.005006 |
| AB Luna Check, basic/weak | 12 | 9 | 0.009920 |
| AB Sol Draft, same basic/weak | 12 | 12 | 0.085958 |
| AB Sol Check, same basic/weak | 12 | 12 | 0.175916 |
| AB native Sol profile Draft, mixed/override | 12 | 12 | 0.105714 |
| AB native Sol profile Check, mixed/override | 12 | 12 | 0.207158 |

Luna costs less but fails the language requirement. Its rejected Check outputs are
RU-basic--1 (`brief`, `delivered text`), RU-weak--1 (`brief`, `deliverables`) and EN-basic--1
(Spanish rationale for English input). These are authored explanations, not permitted source
quotations. Sol passed 24/24 on the matched comparison before selection. Its 24 mixed/override
runs then used the native backend profile **without a collector model override**; every call
in their ledger names `gpt-6.1-sol`. The default router alias was still Luna.

Total: **96 attempts, 277 physical calls, USD 0.618269 estimated**. All physical calls succeeded.
BD RU-weak--1 extract used semantic attempts 1 and 2: the normal structured-validation retry
accounts for the extra call. This is not a manually substituted workflow. The ledger estimate
is not a reconciled provider bill. Configured/requested effort is medium; provider-confirmed
effort remains unknown.

All 96 canonical outputs passed action/artifact identity, AB verbatim list propagation,
actual-model and ledger completeness checks. Agent inspection covered 1,346 authored fields.
The 16 captured prompt/workflow/input-output-schema files remained byte-identical across
these series and matched the working tree. Backend policy/router changes between comparison
and native-profile validation are intentional and recorded.

## Verification against the original acceptance criteria

| Original AC | Current finding |
| --- | --- |
| Russian source without another request produces Russian authored content everywhere | PASS on selected configuration: BD RU basic/weak/mixed, AB RU basic/weak/mixed, including hidden summaries, extraction, questions and comparison explanations. All canonical fields were inspected, not just visible text. |
| One product-owned language policy through every LLM step, independent of UI | Present in all eight prompts; three document mappings retain the original source. Mixed and explicit override checks pass. Existing English-UI browser/Copy evidence is retained; frontend and mappings were not changed in this round. |
| Preserve brands, technical identifiers, source quotes and machine keys/enums | Checked; `Acme`, `Ready to ship`, actual source-language quotations and literal dates/amounts remain allowed. No new confirmed language correction defect recorded for this AC. |
| Full canonical regression including historical QA; check facts and verdict | BD-RU-08 passes RU basic 2/2 this round. Full output and document/comparison consistency checked. Two additional whole-output fact/semantic observations below remain; causation by this change is unproven. BD-RU-10, AB-D-RU-03 and AB-C-RU-01 originals remain unavailable. |
| Stochastic evidence supplements retained failures | Completed bounded 96-run follow-up; rejected Luna and old matrix failures retained. No isolated successful retry is used to erase failures. |

The agreed multilingual/override regression also passes on the selected configurations:
**72/72** across all four families, three languages, two repeats, three scenarios. This is
regression evidence supporting the implementation plan, not 72 separate ticket acceptance
criteria or proof of universal model reliability.

## Additional observations retained without correction

- BD EN-basic--2 asks about the renovation budget used by article guidance rather than the
  fee for writing the article. Same class as the previous candidate; language is English
  throughout. Its broader rubric decision stays FAIL; language decision stays PASS.
- Native AB Draft RU-mixed--1 omits budget/date from the whole canonical output. Same class
  as the earlier matrix, not demonstrated to have been introduced by the language correction.
  The repeat retains both; that success does not erase the observation.
- Native AB Check EN-mixed--1 omits those values from criteria but retains them in comparison
  and recap: placement-only observation, no demonstrated violation of the original AC.
- Mixed HTML descriptions still produce variable judgments about whether the claimed file
  is enough evidence. Every document preserves its structured comparison statuses/verdict.
- The previously retained BD no-question final-schema failure was not fixed. This matrix
  did not reproduce it and does not establish that the no-question branch is corrected.
- Earlier additional findings and rejected Luna fact omissions remain in their original
  records. No broader extraction, budget semantics, judgment or schema fixes were made.

The `.agent-review.json` files retain the original broader rubric, so their FAIL counts must
not be read as language-AC counts. Separate human `.review.json` files remain unfilled. The
summary exposes language results separately and lists additional observations explicitly.

## Checks and remaining closure work

Doctor, 326 product/collector tests and 64 focused language/collector checks passed.
The full profile/runner run had only the known sudo-dependent environment failure. Canonical
quick-check passed config/architecture/docs/generated gates and reached 3,596 passing tests,
12 skips and 655 deselections, with two failures: the known sudo test and a YAML regression
test that incorrectly treated the newly added Sol policy as part of the default policy.
The YAML test now bounds each policy separately and covers both policies. After that fix,
all 140 ConfigLoader/profile/activation targeted tests passed. The full quick-check was not
repeated after this test-only correction; no fully green baseline or CI result is claimed.
Docs/generated and whitespace checks passed; Ruff has no findings on changed lines.
The temporary Compose stack was stopped with volumes retained. No browser server was started
in this round. CI for the uncommitted revision is unverified.

Browser journeys were not rerun in this round: no renderer, public output shape or workflow
mapping changed. The previous three real English-UI Russian-input recap/Copy journeys remain
UI-contract evidence, not new-model browser evidence.

There is no demonstrated language failure left in the selected configuration's tested corpus.
The owner explicitly confirmed that absent historical originals are not a closure blocker
and delegated quick-check verification to CI before authorizing commit and push. Historical
coverage remains accurately marked as unavailable; no original regression is claimed.
Additional observations remain unfixed as requested, for later product iterations. This report does not close the ticket or claim
independent human acceptance, CI success or a production rollout.
