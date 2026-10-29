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
