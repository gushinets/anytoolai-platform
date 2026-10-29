# Execution Plan: ProposalAI term status rule and six-configuration comparison (ANY-631)

## Status

- State: active
- Owner: agent
- Linear: ANY-631
- Created: 2026-10-29
- Last updated: 2026-10-29
- Review date: 2026-11-05
- Next action: commit the prompt rule, then run stage 1 of the comparison.
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

- Usable result: meets every ANY-631 criterion of its case and has no critical error.
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
