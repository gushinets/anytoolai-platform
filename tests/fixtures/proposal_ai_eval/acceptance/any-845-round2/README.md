# ANY-845 review round 2: live evidence

The two review fixes are implemented on `cce65cdcdff3ebc77e1ab4502386828a477081d4`:
unambiguous Russian name normalization and a complete RU/EN/ES × tone × named/unnamed matrix.
Live verification on 2026-11-12 found one remaining punctuation deviation. **The owner accepted
this iteration with that explicit exception** after reviewing the published evidence. The strict
every-run requirement remains unmet; measured results and raw failures are unchanged.

| Verification | Result |
|---|---:|
| 18 language/tone/name combinations, three repetitions | 54/54 exact greetings |
| Inflected `Заказ от Анны Ивановой…`, three repetitions | 3/3 `Здравствуйте, Анна Иванова!` |
| All 24 cases, including six edge cases, three repetitions | 71/72 exact greetings |
| Original P01/P02/P04/P05 QA cases | 4/4 agent assessments pass |
| Focused product, speaker-identity and eval tests | 244 passed |
| Required CI on the tested source | Passed |

`G10-ru-brand-name`, attempt 3, returned `Здравствуйте!` in `neutral`, where `Здравствуйте.` is
required. It correctly omitted the brand as a personal name. This is a `missing_required` failure,
not a pass or a suppressed warning. The other two repetitions match. The owner explicitly authorized closing both review findings with this exception on 2026-11-12.
No 100% success or full human/browser acceptance is claimed. The decision is recorded separately
from measured results in `owner_decision` in the report.

## Records

- [Report](report.json): all first lines, literal pass/fail results, answer hashes, retained
  diagnostics, per-case agent assessments and the acceptance boundary.
- Input snapshots: [24 greeting cases](greeting-orders.json), [four original QA cases](regression-orders.json).
- Full raw collector records: [greeting](greeting-runs.jsonl), [QA](regression-runs.jsonl).
- Provider ledgers: [greeting](greeting-provider-calls.json), [QA](regression-provider-calls.json).
- [Environment](environment.json): exact Git SHA/tree, runtime prompt hashes checked against Git,
  clean working tree, API URL, source/profile fingerprints and provider policy.
- [CI result](ci-checks-cce65cdc.json): required checks passed, including full-check, Windows baseline,
  PostgreSQL concurrency, atoms-proof and production Compose smoke. All other checks passed except
  the intentionally skipped CodeRabbit check. Task Finder smoke first timed out waiting for Copy
  in its quota test; its isolated retry passed. The [initial snapshot](ci-first-attempt-cce65cdc.json)
  retains that failure.
- [Rejected first candidate](candidate-a8630c3e/README.md): all evidence from `a8630c3e`, including
  the English unnamed `warm` failure that prompted the explicit selection table. Those outputs
  are not used as evidence for the later prompt.

The input snapshot contains exactly the same 24 case objects as the committed fixture, reordered
to test English unnamed `warm` and the inflected Russian name first. No input values changed.
The original 12 cases, pinned QA/terms inputs and all round 1 evidence remain unchanged.

## Provenance and cost

The running worker and ledger confirm OpenAI `gpt-6-luna` through LiteLLM,
`default_text_generation_v1`, reasoning `medium`. Quotas were unmetered. No model policy,
runtime post-processing or frontend setting changed. The isolated checkout was clean
(`git_dirty=false`); source and generated deployment-profile fingerprints were verified.

- Composer SHA-256: `e9462bbfb7b1508e4eb25b317006f3c4bbf19e785570bd3217f27d1400f96660`.
- Gap prompt SHA-256: `dc23c818c04459410813584a18c811d389d702dddaac8699632a679119ab39d3`.
- Final-source series: 76 completed scenarios, 152 successful physical calls,
  USD 0.05645566 estimated. Collected from 17:14:49 to 17:31:15 UTC.
- Rejected candidate: 32 completed scenarios, 64 physical calls, USD 0.033605025 estimated.
- Entire round: 108 completed scenarios, 216 physical calls, USD 0.090060685 estimated.

Main was merged before this round, including ANY-846 gap detection changes. Both prompt hashes
differ from round 1; this is not a controlled composer-only comparison against that round.

## Assessment limits

All three inflected-name outputs preserve both name components and normalize only their case.
All named/unnamed matrix cells pass, including English `Hi,` for unnamed `warm`. Freelancer,
manager, ambiguous-person and brand names are not used as the client. The one G10 punctuation
failure remains a failed literal check even though its identity handling and semantic greeting
criteria pass. Agent assessments do not override automatic failures or impersonate human verdicts.

Five body long-dash warnings remain. One QA gap, “Shopify experience is not covered.”, is below
the six-word language-detector threshold; the agent confirms English and retains `language_unverified`.
Further body-style tuning is deferred. Experience-gap classification quality, including the
retained WhatsApp-related findings, is outside this greeting-focused acceptance.

These are local API runs with a real provider, not production/browser acceptance or the complete
ANY-631 human protocol. The sample does not guarantee every future generation. No deployment or
Linear status transition was performed.

## Reproduction

Use the exact tested commit and a fresh live stack configured for ProposalAI. The existing runner
requires configured provider credentials; never place them in the evidence files. With its API
URL and Compose project, run:

```bash
.quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py run \
  --api-url "$API_URL" --compose-project "$COMPOSE_PROJECT" \
  --orders tests/fixtures/proposal_ai_eval/greeting_cases.json \
  --series any-845-round2-repeat --repeats 3 --timeout 180 --out "$NEW_RUNS_PATH"
```

Run the unchanged `qa_cases.json` once as well. Use fresh output paths: the collector appends.
Inspect every output and diagnostic, verify runtime hashes and ledger policy/model, and record
failures as failures. This command spends provider credits.
