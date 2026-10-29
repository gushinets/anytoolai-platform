# Execution Plan: ProposalAI term status rule and six-configuration comparison (ANY-631)

## Status

- State: active
- Owner: agent
- Linear: ANY-631
- Created: 2026-10-29
- Last updated: 2026-10-29
- Review date: 2026-11-05
- Next action: team lead decision on the recommendation (`gpt-6-luna` / `high`); then move this
  plan to `completed/`. Follow-ups: ANY-776 (switch the model), ANY-777 (60 s form wait), ANY-771
  (output language).
- Blocker: none

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
    finalists (in progress, recorded here when it completes) and are not evidence for the final
    prompt.
- Code review #2: the status of a client term was defined in five places (a sentence in the limits
  rule, the three-status rule, "Amounts and dates the client states", and the value whitelist and
  "is not your offer" under "Price and terms"), so every fix to one place contradicted another. The
  ProposalAI prompt now has one "Terms" section that is the only rule for terms and their values:
  the first applying rule wins (1 the freelancer's own decision in the positioning or a direction
  in the order, 2 agreed, 3 left for discussion, 4 a conflicting client request, 5 otherwise the
  client's term), and one "Values" rule allows a value only as a client's term or the freelancer's
  own. Reply Draft states the same order with `intent` as the freelancer's decision. A structural
  test keeps the scattered wording from coming back.
- Regression set: `tests/fixtures/proposal_ai_eval/terms.json` (9 orders, rules 1-5, EN/RU/ES,
  including both review examples), run with `scripts/agent/proposal_ai_eval.py --orders`; a
  `must` / `must_not` match is evidence, the outputs are still read by hand.

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
