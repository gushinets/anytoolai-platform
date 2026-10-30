# Execution Plan: ProposalAI term status rule and six-configuration comparison (ANY-631)

## Status

- State: active
- Owner: agent
- Linear: ANY-631
- Created: 2026-10-29
- Last updated: 2026-10-30
- Review date: 2026-11-05
- Next action: fix the output language defect (ANY-771; the check must cover the gaps block and the
  proposal text) and the 60 s form wait (ANY-777), then repeat the live run and `accept` against
  the approved thresholds (team lead decision, ANY-631 comment, 2026-10-30). ANY-631 acceptance is
  not closed before that. `gpt-6-luna` / `high` stays the preferred model; the switch is ANY-776.
- Blocker: the pass 5 acceptance suite is FAIL under the approved thresholds (three groups of 3
  runs have 2 usable: ANY-771 twice, ANY-777 once). No critical error: the prompt itself is not
  the cause. ANY-631 and ANY-595 statuses stay as they are.

## Goal

ANY-631 live acceptance on `gpt-6-luna`/`medium` (2026-10-28): P01, P02, P05 3/3, P04 2/3. In one
P04 run the client's EUR 300 budget was restated as part of the request but never stated as not
accepted. Team lead decision (ANY-631 comment, 2026-10-29): first a general prompt rule, then a
comparison of six model configurations on one frozen prompt version, choosing the cheapest
configuration that meets the quality and time thresholds below.

## Scope

- `proposal_ai/prompts/compose_persuasive_text.v1.md`: each client term (price or budget, deadline,
  pages or rounds, guarantee) is agreed, proposed or left for discussion, and the text makes that
  status explicit. A proposed term that conflicts with the scope or another term, or that the order
  declines, is stated as not accepted with its exact value and no replacement value. Agreed terms
  (P05) are restated and confirmed. Examples no longer reuse acceptance-case values.
- `client_update_writer/prompts/reply_draft_compose_reply.v1.md`: the same status rule, decided by
  `intent` (same class of problem as ANY-628).
- Prompt-fragment tests in both products. Prompt versions stay `v1` (precedent ANY-628, ANY-629).
- Comparison, prompt frozen for the whole series:

  | Model | Reasoning |
  | --- | --- |
  | `gpt-6-luna` | `medium`, `high` |
  | `gpt-6.1-terra` | `medium`, `high` |
  | `gpt-6.1-sol` | `medium`, `high` |

  - Stage 1: P01, P02, P04, P05 x 5 per configuration (120 runs). Stop and report before stage 2.
  - Stage 2: the two finalists, 15 more runs per case (120 runs, 20 per case per finalist), plus new
    case variants with other amounts, deadlines and wording, including normally agreed terms.
- Runs go through the ProposalAI web form (Playwright on the real form, one manual browser check per
  configuration). Same inputs, tones, application version, response limits and retry rules.
- The model and reasoning are switched locally, never committed; every run records the model and
  reasoning actually used, read back from the running worker and from `provider_calls`.

## Thresholds (fixed before the comparison)

- Usable result: meets every ANY-631 criterion of its case and has no critical error. A gendered
  form the freelancer uses in their own positioning (P01 "Делал") is taken from the input and passes.
- Critical error: an unagreed price or term stated as accepted, an invented commitment or amount, a
  lost mandatory condition (exclusion, revision limit, paid changes, start prerequisite), or a
  promise of excluded work. Disputed answers are checked by hand.
- Admissible configuration: zero critical errors in the series; stage 1 at most one failed run per
  case out of 5; stage 2 at least 19 of 20 per case.
- Time: median from form submit to visible result at most 60 s; p90 reported.
- Choice: the cheapest admissible configuration by cost per usable result. The product model is not
  switched before that decision.

## Report

Per case and per configuration: passed and failed runs with the reason for each failure; critical
errors separately; full cost of each user run (all LLM steps and all physical retries, failed runs
included) from `provider_calls.estimated_cost`, marked as estimated, unknown cost never counted as
zero; cost per usable result (all series costs / usable results); mean and median time, p90,
retries; usage, tariffs and caching conditions; full outputs linked to configuration and run.

## Out of scope

The gaps language defect (ANY-771), Docker dependency cache (ANY-770), changing the product model.

## Risks

- LiteLLM 1.105.1 prices all three models (per 1M tokens, input / output / cached input):
  `gpt-6-luna` 0.10 / 0.50 / 0.01, `gpt-6.1-terra` 1.00 / 5.00 / 0.05, `gpt-6.1-sol` 2.00 / 10.00 /
  0.10 USD. A call it still cannot price comes back as unknown (NaN), never as zero.
- 240+ live runs cost real money; stage 2 starts only after the stage 1 numbers are reviewed.
- Rebuilding the stack downloads all Python dependencies (ANY-770); the model is switched inside the
  running containers instead of rebuilding.

## Validation

- `python scripts/agent/runner.py quick-check`
- Freelancer Suite prompt-fragment tests.
- Live: P04 and P05 x 3 on `gpt-6-luna`/`medium` with the new rule (2026-10-29): P04 3/3, P05 3/3.
- Code review #1 fixes (an explicitly accepted change to an agreed term is stated as accepted; a
  counteroffer is allowed only when the freelancer supplies its exact value), live on
  `gpt-6-luna`/`medium` through the API, 2026-10-29:
  - ProposalAI P04 x 3 (no counteroffer in the input): EUR 300 not accepted, no replacement value.
  - ProposalAI, order "decline EUR 300 and the 48-hour deadline, offer EUR 800 for a smaller 5-page
    first phase" x 3: EUR 300 and 48 hours declined, exactly EUR 800 for 5 pages offered, no other
    amount.
  - ProposalAI, agreed one revision round for USD 400 by 20 November, order "accept a second round
    at no extra cost" x 3: the second round is stated as accepted, USD 400 and the date confirmed.
  - Reply Draft, client "We agreed one revision round; can we have two?", `reply_goal` "Agree to two
    revision rounds" x 3: "Yes, we can have two revision rounds instead of the one we originally
    agreed."
  - Reply Draft, same message, `reply_goal` "Decline the second revision round; one round stays as
    agreed" x 3: the second round is not accepted, the agreed one round stays.
  - These were short API probes on `luna/medium` of a prompt that code review #2 then found still
    inconsistent; they are superseded by the web-form regression of the final prompt on both
    finalists below and are not evidence for the final prompt.
- Code review #2: the status of a client term was defined in five places (a sentence in the limits
  rule, the three-status rule, "Amounts and dates the client states", and the value whitelist and
  "is not your offer" under "Price and terms"), so every fix to one place contradicted another. The
  ProposalAI prompt now has one "Terms" section that is the only rule for terms and their values:
  the first applying rule wins (1 the freelancer's own decision in the positioning or a direction
  in the order, 2 agreed, 3 left for discussion, 4 a conflicting client request, 5 otherwise the
  client's term), and one "Values" rule allows a value only as a client's term or the freelancer's
  own. Reply Draft states the same order with `intent` as the freelancer's decision. A structural
  test keeps the scattered wording from coming back.
- Regression set: `tests/fixtures/proposal_ai_eval/terms.json` (10 orders, rules 1-5, EN/RU/ES,
  including the examples of code reviews #1 and #2), run with
  `scripts/agent/proposal_ai_eval.py run --orders` (the CLI since code review #6).
- Code review #3: the automatic checks themselves were the wrong model. The set only checked that an
  amount was present, so "I accept your USD 150 budget" passed; the language check called every
  non-Cyrillic text English and skipped Spanish, so whole Spanish, Dutch and German answers passed.
  Both are replaced, not patched (the term oracle was replaced again in code review #5, below):
  - Each order lists its terms with the expected status (`not_accepted`, `agreed`, `accepted`,
    `offered`, `open`); the verdict per term is ok, error or unverified (code review #4: a two-valued
    oracle turned every ambiguity into a silent pass). A status marker is an acceptance, a refusal,
    the client's proposal ("proposed", a ceiling), an open term ("will be agreed after the call") or
    an offer, with markers for EN, RU and ES. A negation counts only when bound to the verb: at most
    two words in between and no comma, colon, semicolon or "but", so "I do not code, but I accept
    your budget" is an acceptance. The markers in the value's own clause decide; with none there the
    sentence decides when its markers all point one way, otherwise the mention is unverified.
    `not_accepted` needs an explicit refusal or proposal ("will be agreed later" is not a refusal);
    `agreed` and `accepted` need an explicit confirmation, or for agreed terms one confirmation of
    the whole agreed set; `open` needs an open marker; a missing term is an error.
  - The language is detected from function words for en, es, de, nl, fr, it and pt and from the
    Cyrillic share for ru; a text no language leads clearly is `language_unverified`, a manual read,
    never "ok".
  - Calibrated on 234 real outputs of these orders from the comparison, the regressions and the
    behavioral checks: 200 ok, 16 errors, 18 unverified. Every error is a real failure (a whole
    answer in German or Spanish, a budget restated with no status by the first Terms version, a
    ceiling left "open" instead of stated as the client's proposal); the unverified ones are an
    agreed amount that recurs inside the refusal of a new request, or agreed terms listed without
    any confirmation, and are read by hand. The language check flags every one of the 10 known
    wrong-language answers among 624 outputs and no correct one.
  - The unrelated eval tests that the review #3 change deleted by mistake (numbers across the task
    and the profile, grouped, decimal and scaled amounts, dates, placeholders, identifiers with
    digits, the protocol order set) are restored unchanged.
  - Unit tests assert that the examples of reviews #3 and #4 are errors or unverified, never ok
    ("I do not code, but I accept your USD 150 budget", "Your EUR 300 budget will be agreed later",
    an omitted open fee, "The project will cost USD 400"), that the earlier examples are rejected ("I accept your USD 150 budget and
    the 3-day deadline", "I accept the EUR 300 budget and offer EUR 800", "Бюджет до 80 000 ₽
    согласован и принят. Срок в 2 рабочих дня подтверждаю."), that EN to Spanish, Dutch and German
    and ES to English are wrong-language, and that correct live answers pass.
- Code review #5: the oracle still returned ok for a term the order told the freelancer to decline
  when the text only called it the client's proposal, and for an open fee that dropped its
  condition. Both come from the same wrong shape: a check that can say ok. Replaced (and deleted
  in code review #6, see the acceptance procedure below):
  - `check_terms` has two outcomes only: error (definitely wrong) or needs a human verdict. Every
    client term goes to a human verdict unless it is definitely wrong; nothing passes on markers.
  - The expected status is the decision the order asks for: `declined` (an explicit refusal is
    required; a proposal or "not agreed" is an error), `not_agreed` (the client's term, stated as
    proposed or refused, never accepted), `agreed`, `accepted`, `offered`, and `open` with an
    optional `condition` that must appear in the same sentence as the term (`ceiling-and-scope-en`:
    the final fee is agreed after inspecting the theme; `left-open-en`: after the discovery call).
  - Unit tests assert that the review #5 counterexamples are errors ("La garantía de 10 000
    seguidores también es una propuesta del cliente", "The final fee is proposed, not agreed") and
    that correct answers go to a human verdict, never ok.
  - Re-judged with this oracle, pass 4 had three answers that call a budget the order declines only
    "the client's proposal" (`conflict-decline-es`: 2 on medium, 1 on high), so pass 4's "terms set
    30/30" for high was wrong. Prompt fixes: a declined term is refused in so many words, and calling
    it proposed or not agreed is not a refusal (rule 1); only a direction that accepts, declines or
    counters that very term decides it (rule 1); a statement of agreement covers every term it
    introduces, including the terms listed after it (rule 2, the critical medium failure of pass 4);
    rule 5 applies only to a term the order never calls agreed. The same three points in Reply Draft.

## Results (2026-10-29, prompt `369e0775`, 410 runs through the web form)

Full report and every output: ANY-631 comment and attachment "ANY-631: полные выводы 410 запусков
сравнения". Cost is estimated from `provider_calls.estimated_cost`; the whole series cost about
1.24 USD.

- Stage 1 (P01, P02, P04, P05 x 5): every configuration admissible, zero critical errors.

  | Configuration | Usable | Median, s | p90, s | USD per usable result |
  | --- | --- | --- | --- | --- |
  | luna / medium | 19/20 | 22.5 | 24.5 | 0.0013 |
  | luna / high | 20/20 | 29.1 | 42.1 | 0.0015 |
  | terra 6.1 / medium | 18/20 | 12.0 | 24.5 | 0.0064 |
  | terra 6.1 / high | 20/20 | 15.0 | 29.0 | 0.0070 |
  | sol 6.1 / medium | 20/20 | 14.0 | 16.0 | 0.0090 |
  | sol 6.1 / high | 20/20 | 29.0 | 33.6 | 0.0163 |

- Stage 2 (finalists, 20 per case, plus variants V1-V6 x 5 in EN/RU/ES covering conflicting, agreed
  and open terms): luna / high P01 20, P02 19, P04 20, P05 20, variants 29/30, admissible; luna /
  medium P04 17/20, not admissible.
- Extra: gaps on medium and compose on high (local per-step policy): 77/80, variants 30/30, median
  only 2 s faster than luna / high at the same cost, so per-step policies are not worth a deployment
  profile change.
- Recommendation: `gpt-6-luna` / `high` for ProposalAI (ANY-776). The product model is unchanged.
- The term status rule held on every model: zero critical errors in 410 runs.
- Failures: luna answering a whole English order in Spanish, Dutch or German (luna / medium 5/110,
  luna / high 1/110, ANY-771); the web form giving up after 60 s while the scenario still finished
  (ANY-777); `gpt-6.1-terra` / `medium` returning text without the JSON wrapper (8 of 20 first
  attempts, 2 visible errors); one form error after 33 s with an unknown cause.

## Acceptance audit (code review #1)

Per case and configuration: usable runs, critical errors, time and estimated cost per run. Stage 1
and stage 2 runs of the two finalists are counted together (20 per case).

| Configuration | Case | Usable | Critical | Median, s | Mean, s | Mean USD per run |
|---|---|---|---|---|---|---|
| luna-medium | P01 | 20/20 | 0 | 22.6 | 23.1 | 0.00133 |
| luna-medium | P02 | 19/20 | 0 | 27.1 | 26.7 | 0.00154 |
| luna-medium | P04 | 17/20 | 0 | 20.5 | 20.2 | 0.00096 |
| luna-medium | P05 | 20/20 | 0 | 18.5 | 18.9 | 0.00088 |
| luna-high | P01 | 20/20 | 0 | 33.6 | 35.5 | 0.00185 |
| luna-high | P02 | 19/20 | 0 | 44.2 | 43.9 | 0.00227 |
| luna-high | P04 | 20/20 | 0 | 28.1 | 28.2 | 0.00125 |
| luna-high | P05 | 20/20 | 0 | 22.5 | 24.4 | 0.00115 |
| terra-medium | P01 | 5/5 | 0 | 11.5 | 10.8 | 0.00418 |
| terra-medium | P02 | 4/5 | 0 | 21.5 | 21.0 | 0.01065 |
| terra-medium | P04 | 4/5 | 0 | 11.9 | 11.8 | 0.00406 |
| terra-medium | P05 | 5/5 | 0 | 9.5 | 11.2 | 0.00418 |
| terra-high | P01 | 5/5 | 0 | 11.9 | 12.5 | 0.00494 |
| terra-high | P02 | 5/5 | 0 | 29.0 | 28.3 | 0.01217 |
| terra-high | P04 | 5/5 | 0 | 18.0 | 17.7 | 0.00603 |
| terra-high | P05 | 5/5 | 0 | 11.9 | 12.6 | 0.00486 |
| sol-medium | P01 | 5/5 | 0 | 14.0 | 14.4 | 0.00776 |
| sol-medium | P02 | 5/5 | 0 | 16.0 | 15.6 | 0.00921 |
| sol-medium | P04 | 5/5 | 0 | 16.0 | 16.0 | 0.01130 |
| sol-medium | P05 | 5/5 | 0 | 11.4 | 12.0 | 0.00774 |
| sol-high | P01 | 5/5 | 0 | 29.0 | 27.8 | 0.01463 |
| sol-high | P02 | 5/5 | 0 | 31.1 | 31.2 | 0.01730 |
| sol-high | P04 | 5/5 | 0 | 33.6 | 32.6 | 0.02105 |
| sol-high | P05 | 5/5 | 0 | 18.5 | 19.6 | 0.01202 |
| luna-medium-v | V1 | 4/5 | 0 | 27.1 | 27.9 | 0.00152 |
| luna-medium-v | V2 | 5/5 | 0 | 22.5 | 21.7 | 0.00122 |
| luna-medium-v | V3 | 5/5 | 0 | 20.5 | 21.3 | 0.00121 |
| luna-medium-v | V4 | 5/5 | 0 | 16.0 | 14.8 | 0.00067 |
| luna-medium-v | V5 | 5/5 | 0 | 24.6 | 24.7 | 0.00137 |
| luna-medium-v | V6 | 5/5 | 0 | 22.5 | 21.6 | 0.00115 |
| luna-high-v | V1 | 4/5 | 0 | 25.0 | 26.6 | 0.00166 |
| luna-high-v | V2 | 5/5 | 0 | 27.1 | 29.2 | 0.00178 |
| luna-high-v | V3 | 5/5 | 0 | 24.5 | 21.7 | 0.00140 |
| luna-high-v | V4 | 5/5 | 0 | 18.0 | 18.6 | 0.00098 |
| luna-high-v | V5 | 5/5 | 0 | 27.1 | 30.6 | 0.00178 |
| luna-high-v | V6 | 5/5 | 0 | 27.1 | 28.7 | 0.00148 |
| luna-mixed | P01 | 20/20 | 0 | 28.1 | 29.1 | 0.00165 |
| luna-mixed | P02 | 18/20 | 0 | 35.7 | 36.8 | 0.00211 |
| luna-mixed | P04 | 19/20 | 0 | 27.1 | 29.3 | 0.00146 |
| luna-mixed | P05 | 20/20 | 0 | 22.5 | 23.7 | 0.00113 |
| luna-mixed-v | V1 | 5/5 | 0 | 29.3 | 27.5 | 0.00169 |
| luna-mixed-v | V2 | 5/5 | 0 | 22.5 | 23.1 | 0.00146 |
| luna-mixed-v | V3 | 5/5 | 0 | 20.5 | 22.7 | 0.00141 |
| luna-mixed-v | V4 | 5/5 | 0 | 18.0 | 17.8 | 0.00092 |
| luna-mixed-v | V5 | 5/5 | 0 | 27.1 | 27.8 | 0.00172 |
| luna-mixed-v | V6 | 5/5 | 0 | 29.1 | 32.2 | 0.00187 |

Time runs from form submit to the visible result or visible error. Two terra / medium runs that an early driver version waited out to its 240 s timeout have no user-visible time and are left out of the timing. Run numbers count within a configuration; the session id is unique. A `-v` configuration is the same model and reasoning on variants V1-V6.

Failed runs (session: cause, as recorded in the manual review):

- luna-medium P04 #4 `scenario_session_01793267689044280560_0000000075_af359fdb9f3a412d8c33799fa7156c63`: весь текст на испанском при английском заказе (бюджет при этом отклонён)
- luna-medium P04 #6 `scenario_session_01793273011078900823_0000000112_95ae827e40c9432982eacc275a522913`: весь текст на нидерландском при английском заказе (бюджет при этом отклонён)
- luna-medium P04 #9 `scenario_session_01793273312318190289_0000000172_320b44d65ede422185bee7d4342159c2`: весь текст на испанском при английском заказе (бюджет назван «propuesto, no acuerdo»)
- luna-medium P02 #12 `scenario_session_01793273588129677667_0000000227_b2bd6966a54d4b1ab721c692519fe96f`: текст не на английском
- luna-high P02 #7 `scenario_session_01793275622431794188_0000000127_d6bfb7a97ee64e10ab50dffd5b083b59`: форма показала ошибку через 60 с (лимит ожидания клиента 60 000 мс); сессия на сервере завершилась успешно около 70 с, с повторной попыткой compose
- terra-medium P02 #3 `scenario_session_01793268902366245427_0000000050_51ac6b159c9c4559a8493133554b7680`: compose_persuasive_text дважды вернул текст без JSON-обёртки (malformed_json, обе попытки валидации), сессия failed; форма показала ошибку
- terra-medium P04 #5 `scenario_session_01793269273457414468_0000000095_998338e35f3248cd9328e8a684230c66`: compose_persuasive_text дважды вернул текст без JSON-обёртки (malformed_json, обе попытки валидации), сессия failed; форма показала ошибку
- luna-medium-v V1 #2 `scenario_session_01793274108002520181_0000000332_bff5ec4ba8eb40ee9ef3b3a0a653d404`: текст не на английском
- luna-high-v V1 #2 `scenario_session_01793277038435477678_0000000332_8d97803838ed472fbd5cba108b8a1322`: весь текст на испанском при английском заказе V1 (USD 150 назван «propuesto, no acordado»)
- luna-mixed P04 #6 `scenario_session_01793279334882393721_0000000117_63257aea8d6e4ab280098cd3ef37b8d1`: весь текст на немецком при английском заказе (бюджет при этом отклонён)
- luna-mixed P02 #12 `scenario_session_01793280097551390879_0000000232_01f21f8d10904033a1aaa84fc6a493d4`: весь текст на испанском при английском заказе
- luna-mixed P02 #19 `scenario_session_01793280990371256844_0000000372_533ae3fbdbdf4f96870b6b8e31d52c5f`: форма показала ошибку через 33 с, хотя сценарий завершился за 32 с без повторов и результат отдаётся (HTTP 200); причина на стороне клиента/API не установлена, логи API потеряны при перезапуске

Model and reasoning check: 410 runs, 820 session x step pairs in `provider_calls`; mismatches: 0

How the model and reasoning were verified, so that no configuration was swapped silently:

- Every switch copied an edited router config into the running api and worker containers,
  restarted them and read `model` and `reasoning_effort` back from the worker's own config file;
  the log below is that read-back. The script asserts that the requested and the read-back values
  match.
- Every run must have started after the switch to its own configuration and before the next one.
- Every LLM step of every run is checked in `provider_calls`: `model` must be the configuration's
  model and `gateway_model` the alias of that step (`anytoolai.default_text`; in the mixed
  experiment `anytoolai.default_text_high` for `compose_persuasive_text` only). The reasoning effort
  itself is not stored per call, so it is proven by the alias and the read-back of that alias.

Config switches as read back from the worker (UTC):

- 2026-10-29T09:48:12Z gpt-6-luna medium worker: model: openai/gpt-6-luna reasoning_effort: medium allowed_openai_params: [reasoning_effort]
- 2026-10-29T09:58:03Z gpt-6-luna high worker: model: openai/gpt-6-luna reasoning_effort: high allowed_openai_params: [reasoning_effort]
- 2026-10-29T10:11:26Z gpt-6.1-terra medium worker: model: openai/gpt-6.1-terra reasoning_effort: medium allowed_openai_params: [reasoning_effort]
- 2026-10-29T10:27:14Z gpt-6.1-terra high worker: model: openai/gpt-6.1-terra reasoning_effort: high allowed_openai_params: [reasoning_effort]
- 2026-10-29T10:35:31Z gpt-6.1-sol medium worker: model: openai/gpt-6.1-sol reasoning_effort: medium allowed_openai_params: [reasoning_effort]
- 2026-10-29T10:42:41Z gpt-6.1-sol high worker: model: openai/gpt-6.1-sol reasoning_effort: high allowed_openai_params: [reasoning_effort]
- 2026-10-29T10:54:46Z gpt-6-luna medium worker: model: openai/gpt-6-luna reasoning_effort: medium allowed_openai_params: [reasoning_effort]
- 2026-10-29T11:13:45Z gpt-6-luna medium worker: model: openai/gpt-6-luna reasoning_effort: medium allowed_openai_params: [reasoning_effort]
- 2026-10-29T11:51:54Z gpt-6-luna high worker: model: openai/gpt-6-luna reasoning_effort: high allowed_openai_params: [reasoning_effort]
- 2026-10-29T12:42:40Z gpt-6-luna medium worker: model: openai/gpt-6-luna reasoning_effort: medium allowed_openai_params: [reasoning_effort]
- 2026-10-29T12:55:00Z mixed experiment: detect_gaps -> `anytoolai.default_text` (medium), compose ->
  `anytoolai.default_text_high` (high). The first attempt failed (read-only product configs, the
  stock worker kept running) and ran nothing; the experiment worker took jobs from the second
  attempt on, the stock worker paused, as `gateway_model` per step shows for every run.
- 2026-10-29T13:55:02Z gpt-6-luna medium worker: model: openai/gpt-6-luna reasoning_effort: medium allowed_openai_params: [reasoning_effort]

## Final-prompt web-form regression (code reviews #2 to #4)

Every pass: P01, P02, P04, P05 x 5 and every `terms.json` order x 3 through the ProposalAI web form
on `gpt-6-luna` / `medium` and `gpt-6-luna` / `high` (switch read back from the worker), the stack
rebuilt with the prompt under test. Each pass that changed the prompt was followed by a full rerun.

1. First Terms version (`46dc6a59` before its last fix), 94 runs: P04 broke, 2/5 on medium and 1/5 on
   high. Rule 1 ("the freelancer decides it") took the order's "do not invent a replacement budget" as
   a decision about the budget, and rule 5 let a conflicting budget be restated with no status
   ("Your stated budget is EUR 300"). Fixed: rule 1 applies only to a direction that accepts,
   declines or counters that very term; rule 5 says the client's term is proposed, not agreed. A P04
   x 5 probe on both finalists then gave 10/10 explicit status.
2. `46dc6a59`, 94 runs: every automatic check passed, but reading showed P02 calling the requested
   templates and handover "proposed, not agreed", because the term definition included "a number of
   pages, items". Fixed in `63bb3e49`: the requested work is scope, not a term; a regression order
   for it was added.
3. `63bb3e49`, 100 runs, judged with the review #4 checks and read by hand: P02 still called the
   45-minute handover "proposed, not agreed" (3 runs), because the definition still listed "a
   deadline or duration". Fixed: a term is a condition of the deal (price, payment, delivery date or
   deadline, length of the engagement, limits such as revision rounds, guarantees); what the client
   asks to have delivered, including its size or length, is scope. Also in this pass: 2 whole answers
   in German (ANY-771) and 1 form error after 60 s (ANY-777); no critical error.
4. `26b64ddd`, the shipping prompt, 2026-10-29, 100 runs (P01 x 5 on medium has 4 runs: one form
   page did not load in 30 s and no session started). Judged with the review #4 checks; every flagged
   output and the requested-scope wording of every P02 and `ceiling-and-scope-en` output read by hand.

   | Configuration | P01 | P02 | P04 | P05 | terms set | Median UI, s | p90 UI, s |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | luna / high | 5/5 | 4/5 | 5/5 | 5/5 | 30/30 | 27.1 | 40.2 |
   | luna / medium | 4/5 | 5/5 | 5/5 | 5/5 | 29/30 | 20.7 | 31.1 |

   Every run that is not ok:
   - luna / high P02 #2 `scenario_session_01793297466819954240_0000000027_62c9714b4dbd4770a4da12637d8a5a61`:
     the whole answer in Spanish for an English order (ANY-771).
   - luna / medium `agreed-confirm-ru` #1 `scenario_session_01793296610947619548_0000000102_4747ba9853db451bb71d36968af9d378`:
     critical; the agreed price, deadline and payments are called "client's terms, not yet agreed"
     although the order says the client agreed them (rule 5 applied instead of rule 2).
   - luna / medium P01 #3: the form page did not load within 30 s; no run, not a model result.
   - Read by hand and ok: luna / high `agreed-plus-conflict-es` #2 (the agreed 240 EUR recurs inside
     the refusal of the new request, so the check leaves it unverified).

   The scope fix held: no P02 or `ceiling-and-scope-en` output calls the requested templates or the
   handover proposed or not agreed. P04 states EUR 300 as not accepted in 10/10.

   Re-judged with the code review #5 oracle, pass 4 also had three declined budgets stated only as
   the client's proposal (`conflict-decline-es` medium #2, #3 and high #1), so the terms set was
   27/30 on high and 26/30 on medium, not 30/30 and 29/30.
5. Code review #5 prompt, 2026-10-29/30, 150 runs: first the agreed terms on the current product
   policy `gpt-6-luna` / `medium` (P05, `agreed-confirm-ru`, `agreed-plus-conflict-es`,
   `agreed-change-accepted-en`, `conflict-decline-es` x 10), then the full regression on both
   finalists. Judged with the review #5 oracle; every term-bearing output (124) read by hand, and
   every P01, P02 and P05 output scanned for "proposed / not agreed" next to the requested work.

   | Configuration | Agreed terms x 10 | P01 | P02 | P04 | P05 | terms set | Median UI, s |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | luna / medium | 50/50 | 5/5 | 5/5 | 5/5 | 5/5 | 29/30 | 18.0 |
   | luna / high | not run | 5/5 | 5/5 | 5/5 | 5/5 | 28/30 | 27.0 |

   The agent's reading (not an acceptance; see code review #6 below): no critical error in 150
   runs. Every run that is not ok:
   - luna / medium `conflict-decline-en` #3 `scenario_session_01793302915962425368_0000000202_77ef79d8676a4e71871f3e393ba776fc`
     and luna / high `conflict-decline-en` #3 `scenario_session_01793304525700580296_0000000202_7c662e9c84534781beb70e629be10346`:
     the gaps and the whole answer in Spanish for an English order (ANY-771); the term statuses are
     right. The gaps step answered in Spanish in 6 of these 100 runs, and the proposal followed it twice.
   - luna / high `conflict-decline-es` #1 `scenario_session_01793304030387357943_0000000142_e03e1d6bbeb0487e81a9047e223f32de`:
     the form gave up after 60 s; the scenario completed after 74 s with a correct answer (ANY-777).
   - Read by hand and ok: two `conflict-decline-es` refusals the check missed (the guarantee refused
     without the number, and "10.000" with a dot; the fixture now accepts the dot), one explicit "I
     do not accept unlimited concepts" next to "agreed in advance", and two open fees with their
     discovery-call condition. One high answer also calls the discovery call itself "proposed, not
     agreed": awkward, not a term error.

Result of the agent's reading: with the code review #5 prompt neither `gpt-6-luna` / `medium` nor
`gpt-6-luna` / `high` showed a critical error in 150 runs, and the agreed terms on the current
`medium` policy read 50/50. That is a suggestion, not an acceptance: code review #6 below makes the
human verdict the acceptance. The recommendation `gpt-6-luna` / `high` (ANY-776) still rests on the
comparison (P04 17/20 on medium in stage 2) and is the team lead's decision; the remaining failures
are the output language (ANY-771) and the 60 s form wait (ANY-777).

## Acceptance procedure (code review #6)

Six reviews in a row found a new wording that the term-status regular expressions misread ("I
propose EUR 800" read as the client's proposal, "not agreed" read as a refusal, a condition in the
next sentence read as missing). The check was the wrong tool: whether a term is refused, agreed or
left open is meaning, and no distance to a marker word decides it. Replaced, with the team lead's
contract:

- `scripts/agent/proposal_ai_eval.py` has three commands. `run` collects outputs from a running stack
  into JSONL records (input, full output, session, git and prompt hashes read from the worker,
  model and reasoning, every provider call with its cost, UI or API latency); exit 0 when the
  records are written. `review` shows a person each output, criterion, agent suggestion and quote,
  and records their decision. `accept` is offline and deterministic; exit 0 only for PASS.
- Formal checks stay only where a text match proves the fact: placeholders, meta phrases, lists or
  headings, length, a required literal, a forbidden amount (`must_not`, a critical error), the
  language (clearly wrong: unusable; unclear: pending), long dashes (a warning). A number absent from
  the order is shown to the reviewer, never decided. The term-status markers, `check_terms` and the
  11 semantic `must_not` patterns of `terms.json` are deleted.
- Meaning is a question per order (`criteria` in `terms.json` and `qa_cases.json`, which now holds the
  P01, P02, P04 and P05 web-form inputs and ANY-631 criteria), plus `no-critical-error` for every
  run. Kinds keep the original acceptance: `not_agreed` accepts "proposed, not agreed" (the P04
  criterion), `declined` needs a refusal in so many words. `critical` marks the ANY-631 critical
  errors.
- Verdicts: one JSONL line per run and criterion with the answer hash, the agent `suggestion` and
  the human `decision` (null until a person confirms it). A run is PASS, FAIL (runtime error, formal
  violation, a confirmed "no") or PENDING. The suite is FAIL on a critical error, a group below its
  approved threshold or a series median latency above 60 s; PENDING while a decision is open or a
  group has no approved threshold; otherwise PASS. Thresholds are only the approved ones: P01, P02,
  P04, P05 x 5 per finalist use the stage 1 rule (at most one unusable of 5). The team lead approved
  (ANY-631 comment, 2026-10-30): every terms order x 3 per configuration needs 3/3 usable, every
  agreed-terms order x 10 on `luna/medium` needs 10/10, critical errors stay at zero.
- Evidence: `tests/fixtures/proposal_ai_eval/acceptance/any-631/` holds the 150 pass 5 runs
  (`runs.jsonl`: prompt hashes `f6e696dd...` and `f7608a3a...` read from the worker that served
  every run, equal to commit `02a7f39c`; model and reasoning from the switch read-back, matching
  `provider_calls`), `verdicts.jsonl` with the agent's 586 suggestions (every output read again,
  with a quote and reason per criterion; one `unknown`: P02 medium #4 never states "not a redesign")
  and, after review, the confirmed decisions of the reviewer (586 of 586, all "yes"), and
  `suite.json`.
- Result with the approved thresholds: `accept` reports FAIL. Passing: P01, P02, P04, P05 x 5 on
  both finalists, the 5 agreed-terms orders x 10 (10/10 each), 17 of 20 terms groups, median
  latency 19.5 to 30.1 s per series. Failing: `conflict-decline-en` on `medium` and on `high` (one
  whole answer in Spanish each, ANY-771) and `conflict-decline-es` on `high` (the form gave up
  after 60 s, ANY-777), each 2 of 3 usable. A critical error: none.
- Tests: CLI runs for PENDING (suggestion only, stale hash, unknown), PASS (a non-critical failure
  within the threshold, a long-dash warning), FAIL (critical verdict, forbidden amount, missed
  threshold, slow series) and a missing threshold; the review #6 wordings leave the run pending;
  the committed suite is consistent and its verdict reproducible.
