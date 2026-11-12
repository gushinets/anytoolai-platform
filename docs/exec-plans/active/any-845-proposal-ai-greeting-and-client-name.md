# Execution Plan: ProposalAI greeting and client name (ANY-845)

## Status

- State: active
- Owner: agent
- Linear: ANY-845
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-19
- Next action: review and merge, then move to `completed/`; run live acceptance when a provider stack is available.
- Blocker: none for implementation; live provider verification is unavailable in this environment.

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

If in doubt, use the greeting without a name. Write the name exactly as the input gives it (no diminutives, no patronymic invented, no translation or transliteration unless the text language uses another script and the input itself gives that form). In Russian, the name stays in the nominative case (vocative address).

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

## Baseline

- Date: 2026-11-12; checkout: `feature/ANY-845` at
  `36d96ffd3729bc1df7826ab84c7a3c000acc4bfe`.
- Environment: local development checkout. Docker reports no running containers; no live
  provider stack is available. No provider-call ledger or real-model output was collected.
- Provider/model policy: unverified at runtime; no model is inferred from the UI or fake fixtures.
- Reproduction by prompt analysis: Structure requires the first sentence to pitch the freelancer;
  Form says "open with the point"; neutral explicitly says "no greeting by name". No rule
  requires a greeting. This supports the reported omission, but does not establish how often
  a live model omits one. P01 names Анна and reproduces the conflicting neutral-tone instruction.
- Initial system-Python doctor failed because pytest and pydantic were missing. The canonical
  quick-check uses its managed Python 3.12 environment; initial dependency fetching was blocked
  by sandbox DNS. Retried with network access; results are recorded under Verification.
- Live baseline: not verified live. No first-line outputs are claimed.

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

Live verification: **not verified live**. With a deployed provider stack containing this prompt,
run the following with the stack URL, Compose project and scratch output path supplied by the operator:

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
The shared speaker-identity rule stays intact; real-model compliance remains pending live verification.
