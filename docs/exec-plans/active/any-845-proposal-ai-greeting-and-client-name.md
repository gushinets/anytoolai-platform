# Execution Plan: ProposalAI greeting and client name (ANY-845)

## Status

- State: active
- Owner: agent
- Linear: ANY-845
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-19
- Next action: address review round 2, then collect separate live evidence for the expanded matrix.
- Blocker: review round 2 requires an unambiguous name-inflection rule and complete tone/name coverage.

## Goal

Every ProposalAI tone starts with a greeting, and the client is named only when the order names
them unambiguously.

## Decision

**R1. Every tone starts with a greeting.** The text starts with a short greeting line in the language of the text, ending with punctuation, followed by an empty line. After that comes the opening paragraph ("why you fit" + one case). The greeting is not a self-introduction and not a retelling of the task.

**R2. Client name: use it only when it is unambiguous.** Use the client's name only when `context.task_text` explicitly gives it as the name of the person who placed the order or who will read the proposal. Examples: "Анна, владелица студии…", "Client: John", "Меня зовут Анна, ищу…", a client message signed "Анна". Never use:
- a name from `context.freelancer_positioning` (that is the freelancer),
- a name the freelancer gives as their own in `task_text`,
- a third party (the client's customer, a colleague, a manager mentioned in passing),
- a company, brand or product name,
- a name when it is unclear whose it is, or when several people are named and none is clearly the addressee.

If in doubt, use the greeting without a name. Preserve the client's identity and supplied name
components. In Russian, normalize an explicitly inflected name to nominative only when that form
is unambiguous: «Заказ от Анны Ивановой» → «Здравствуйте, Анна Иванова!». Otherwise omit the name
if its nominative is ambiguous; keep the supplied spelling in other cases. Do not invent a
patronymic or surname, use a diminutive, translate or transliterate unless the input gives that
form for the other script. This clarification was approved in review round 2 on 2026-11-12.

**R3. Greeting formulas per tone (no time-of-day greetings like "Добрый день/вечер", "Good morning": the send time is unknown).**

| Tone (UI) | RU with name | RU without name | EN with name | EN without name | ES with name | ES without name |
|---|---|---|---|---|---|---|
| `warm` (Дружелюбный) | `Здравствуйте, Анна!` | `Здравствуйте!` | `Hi Anna,` | `Hi,` | `Hola, Ana:` | `Hola:` |
| `neutral` (Ясный и деловой) | `Здравствуйте, Анна.` | `Здравствуйте.` | `Hello Anna,` | `Hello,` | `Hola, Ana:` | `Hola:` |
| `firm` (Уверенный и по делу) | `Анна, здравствуйте.` | `Здравствуйте.` | `Hello Anna,` | `Hello,` | `Hola, Ana:` | `Hola:` |

Forbidden in every tone: "Dear Sir or Madam", "Уважаемый/Уважаемая…" (marks gender), "Hi there", "Привет" (too familiar), a placeholder name, or a greeting longer than one line.

**R4. Expected openings (examples for the prompt doc and the eval criteria).** Brief: "Анна, владелица студии йоги, ищет дизайнера для лендинга в Figma…".

- `warm`, with name: `Здравствуйте, Анна!` ⏎⏎ `Лендинг для студии йоги, где важна удобная запись, мне близок: в Figma я делаю лендинги для небольших сервисных компаний…`
- `neutral`, with name: `Здравствуйте, Анна.` ⏎⏎ `Мой опыт лендингов в Figma для небольших сервисных компаний подходит под этот проект…`
- `firm`, with name: `Анна, здравствуйте.` ⏎⏎ `Делаю лендинги в Figma для небольших сервисных компаний, этот проект в моём профиле.`
- Without a name (brief "Нужен сайт для моего бизнеса…"): `warm` → `Здравствуйте!`, `neutral` → `Здравствуйте.`, `firm` → `Здравствуйте.`, each followed by the same type of opening paragraph.
- Ambiguous name (brief "Ищу дизайнера. Пишите Марине, она мой менеджер."): no name, `Здравствуйте.` (Марина is a third party).

## Initial implementation baseline

- Date: 2026-11-12; checkout: `feature/ANY-845` at
  `36d96ffd3729bc1df7826ab84c7a3c000acc4bfe`.
- At initial implementation, no local containers were running and no live stack was started.
  No provider-call ledger or real-model output was collected then. The later review found configured
  credentials and cached images; inferring unavailability from absent containers was insufficient.
- Provider/model policy: unverified at runtime; no model is inferred from the UI or fake fixtures.
- Reproduction by prompt analysis: Structure requires the first sentence to pitch the freelancer;
  Form says "open with the point"; neutral explicitly says "no greeting by name". No rule
  requires a greeting. This supports the reported omission, but does not establish how often
  a live model omits one. P01 names Анна and reproduces the conflicting neutral-tone instruction.
- Initial system-Python doctor failed because pytest and pydantic were missing. The canonical
  quick-check uses its managed Python 3.12 environment; initial dependency fetching was blocked
  by sandbox DNS. Retried with network access; results are recorded under Verification.
- Initial live baseline: not performed. This initial evidence gap is superseded by the
  versioned live runs below; it is not retrospectively presented as a pre-edit production run.

## Scope

- Edit ProposalAI `compose_persuasive_text.v1.md` in place, including structure, greeting/name
  selection and tone rules; retain the shared speaker-identity rule verbatim.
- Add Python prompt-rule and eval heading regression tests.
- Add `greeting_cases.json` in the existing ProposalAI eval fixture directory. Cover the specified
  Russian and English cases plus Spanish, following the repository's multilingual eval rule.
- Keep pinned `qa_cases.json`, `terms.json` and existing fake-provider responses unchanged.
- Checked all four atom products for the conflicting wording: only ProposalAI forbids greeting
  by name. The shared speaker-identity bullet is not itself changed for this product-specific rule.

## Out of scope

Client Update Writer prompts, the ANY-629 bullet, a client-name form field, time-of-day greetings,
a sign-off, post-processing, model-policy changes and runtime/DSL changes.

## Implementation plan

1. Record the baseline and R1–R4 decision.
2. Update the product prompt without changing Terms, Closing, Language or the JSON contract.
3. Pin the new instructions and verify punctuated greetings pass the existing heading check.
4. Add independent multilingual fixtures for named, unnamed and misleading-name inputs.
5. Run the checks below, record results and leave live acceptance explicitly pending if no stack
   is available. Prepare the decision summary for human review.

## Verification

- Managed Python 3.12.13 doctor: passed. Direct system-Python config validation lacks SQLAlchemy;
  use `.quick-check-venv/bin/python` for the explicit runner commands below.
- Focused tests: **161 passed**, covering ProposalAI product behavior, all four copies of the
  speaker-identity rule, punctuated greetings and the eval fixture contract.
- Freelancer Suite: **262 passed** on the first run; its packaging test initially failed under
  sandbox restrictions, then **1 passed** when rerun with build-cache/network access.
- `validate-configs`, `validate-docs`, and `generate-docs --check`: passed. No generated files changed.
- Terms, Closing, Language, the speaker-identity/form rules and the JSON answer rule were compared
  to the baseline and remain unchanged. Both pinned acceptance inputs remain byte-identical.
- All 12 new fixture regexes accept their expected greeting plus blank line and reject missing
  greetings or a missing blank line. Greeting criteria are non-critical human questions.
- Initial quick-check: **3576 passed, 1 failed, 12 skipped, 657 deselected**. The failure is
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`: this environment
  requires interactive authentication for `sudo -n -u nobody`. No related code was changed.
- Post-change full-check: its quick-check stage completed with **3587 passed, 1 failed,
  12 skipped, 657 deselected**, with the same sudo-dependent failure. The command stopped there;
  product and frontend checks were therefore run separately as recorded here. The existing skips
  and deselections are not evidence of live/database acceptance. Sanitized failure context was
  collected with the repository runner.
- Separate frontend-check: lint, typechecks, unit/browser tests (including 349 Atom Lab browser
  tests) and generated API-contract checks passed. The Next.js build failed prerendering `/404`
  with "<Html> should not be imported outside of pages/_document". No frontend source changed.
  Next.js automatically added `@types/node` during that build; its package/lockfile edits were
  restored and installed dependencies reset with `pnpm install --frozen-lockfile`, so this ticket
  introduces no dependency changes.
- An intermittent LiteLLM import error occurred while its remote cost-map fetch failed under
  sandbox DNS restrictions. The affected focused and generated-doc checks passed using the existing
  `LITELLM_LOCAL_MODEL_COST_MAP=True` option; no dependency or application changes were made.
- Repository hygiene found pre-existing local-skill mentions in unrelated ANY-17, ANY-339,
  ANY-391, ANY-221 and ANY-227 execution plans. They are outside this ticket and remain untouched.

Focused verification:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True .quick-check-venv/bin/python -m pytest \
  packages/backend/product-platforms/freelancer-suite/tests/test_proposal_ai_product.py \
  packages/backend/product-platforms/freelancer-suite/tests/test_prompt_speaker_identity_rule.py \
  tests/test_proposal_ai_eval.py
```

Live verification is now recorded below. To repeat it with a provider stack containing the tested
prompt, use the stack URL, Compose project and new scratch output path supplied by the operator:

```bash
.quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py run \
  --api-url "$API_URL" --compose-project "$COMPOSE_PROJECT" \
  --orders tests/fixtures/proposal_ai_eval/greeting_cases.json \
  --series any-845 --repeats 3 --out "$RUNS_PATH"
```

Then inspect every first line against R3, confirm no heading violation, answer the human criteria,
and run the existing P01–P05 regression cases. Record SHA, environment and provider-call ledger
policy/model evidence at that time. Static tests and fake-provider runs do not prove model compliance.

## Decision summary

Every tone starts with one punctuated greeting line, followed by an empty line and the pitch.
Use a client name only when the task identifies the client unambiguously; otherwise omit the name.
Never address the freelancer, a third party, a company, brand or product as the client.
Use the fixed RU/EN/ES formulas per tone; omit time-of-day, gendered or overly familiar greetings.
The shared speaker-identity rule stays intact; the selected greeting/name cases now have real-model evidence.

## Live acceptance after review round 1

On 2026-11-12 the owner explicitly authorized live runs on `36d96ff` and `08ede358`, recording
results and closing the acceptance finding, with results posted in PR #272 and Linear ANY-845.
The baseline was reconstructed from the exact old commit; it is not historical production evidence.

- **Baseline:** 12/12 scenarios completed, **0/12** required greeting openings. Анна/P01 was run
  in all three tones, plus the unnamed screenshot input, three repetitions each.
- **Fixed greeting set:** 36/36 completed and **36/36** required greeting/name openings across
  12 RU/EN/ES cases. All use a punctuated greeting line, blank line and relevant pitch.
- **Regression:** P01, P02, P04 and P05 each completed and passed agent assessment of their criteria.
  No P03 exists in the existing fixture. Terms, exclusions and speaker identity were preserved.
- The actual ledger confirms `default_text_generation_v1`, OpenAI, `gpt-6-luna`; the running worker
  router records reasoning `medium`. There were **106 physical provider calls** across 52 scenarios,
  with total ledger-estimated cost **USD 0.05047287**. Both local stacks used the same model policy.
- The fixed greeting set has one non-blocking long-dash warning in the body. One short Spanish gap
  description triggers `language_unverified`; the agent confirmed its Spanish language and retained
  the original flag. No unusable or critical automatic finding occurred in the 40 fixed runs.
- All required CI checks passed for implementation commit `08ede358`, including full-check and
  frontend. This is distinct from the initial local environment failures recorded above.
- Raw records preserve `git_dirty=true` due solely to an untracked managed-environment symlink;
  tracked sources were unchanged and runtime prompt hashes matched the exact Git blobs.

Versioned artifacts: [raw runs, ledger, provenance, first-line report and per-case assessments](../../../tests/fixtures/proposal_ai_eval/acceptance/any-845/README.md).

The missing versioned reproduction/acceptance evidence is supplied. This closes the scoped evidence
finding, with the documented non-critical caveats; it does not claim full ANY-631 human/browser
acceptance, validate every future model output, or re-accept unrelated A04 gap-classification quality.
No production deployment or browser run was performed. No prompt, runtime or dependency changes
were needed to resolve this finding.

## Implementation plan — review round 2

Owner authorized both fixes, paid live verification, separate evidence, push, PR/Linear updates
and resolving the findings only after successful verification. Starting checkout is `72b99dd1`,
which already merges ANY-846 gap detection changes; preserve those changes and record both prompt
hashes in the new evidence rather than comparing results as a composer-only change.

1. Preserve client identity/name components, but explicitly allow unambiguous Russian normalization
   to nominative; use no name if the nominative cannot be determined unambiguously. Update R2 and
   its prompt test together. Keep the shared speaker-identity bullet unchanged.
2. Append 11 missing RU/EN/ES × tone × named/unnamed combinations and one explicit inflected-name
   case, for 24 cases total. Keep all previous cases unchanged. Add a small matrix-coverage test
   with the expected greeting for each of the 18 combinations.
3. Run focused tests and repository validators. Commit the implementation so live evidence names
   an exact source version. Run the complete 24-case fixture three times plus P01/P02/P04/P05 once
   through the actual provider, with separate versioned evidence for this round.
4. Assess openings and body criteria, preserving warnings and reviewer attribution. Update the
   PR and Linear only with verified outcomes and resolve each finding when its evidence passes.

Scope: ProposalAI prompt, existing Python tests, eval fixtures and acceptance documentation. No
runtime parser, dependency, UI, model-policy or DSL change. Prior acceptance records stay intact.

### Round 2 local verification

- Managed Python 3.12.13 doctor passed. Focused product, speaker-identity and eval tests: **244 passed**.
- Config, architecture and documentation validation passed. Generated-doc checking uses
  `LITELLM_LOCAL_MODEL_COST_MAP=True` to avoid the known offline LiteLLM metadata import race.
- The original 12 greeting inputs and all round 1 acceptance artifacts remain unchanged.
- Expanded fixtures cover all 18 language/tone/name combinations plus six edge cases, including
  an inflected Russian first name and surname. Live verification is pending on the committed source.

### Round 2 live finding and correction

The first candidate, `a8630c3e`, produced `Hello,` for the English unnamed `warm` case
(`G11-en-noname-warm`, attempt 1), where the fixed rule requires `Hi,`. The explicit inflected
Russian case did produce `Здравствуйте, Анна Иванова!`. The failed series is retained, not accepted.
Further candidate calls were stopped after detection; any in-flight call is accounted for separately.

Correction within the authorized scope: replace the compact slash-separated formulas with one
explicit language/tone/name table and a two-step selection instruction. Absence of a name must
not select a different tone. Keep the existing backend model policy and all 24 inputs. Repeat the
complete matrix and four QA cases on the new committed source, with separate evidence.
