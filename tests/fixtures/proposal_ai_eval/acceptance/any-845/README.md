# ANY-845 live greeting acceptance

On 2026-11-12, real-provider API runs reproduced the missing greeting on the pre-change
commit and verified the selected greeting/name rules on the implementation commit.

| Series | Tested commit | Scenarios | Required greeting + blank line | Provider calls |
|---|---|---:|---:|---:|
| Reconstructed baseline | `36d96ffd3729bc1df7826ab84c7a3c000acc4bfe` | 12 | 0/12 | 26 |
| Greeting/name acceptance | `08ede3581ffe60cf465d3ffe4a7adf37f1b6d690` | 36 | 36/36 | 72 |
| Existing regression cases | `08ede3581ffe60cf465d3ffe4a7adf37f1b6d690` | 4 | 4/4 | 8 |

All 52 scenarios completed. The ledger records 106 successful physical provider calls and an
estimated total cost of USD 0.05047287. Baseline collected between 15:48:33 and 15:52:58 UTC;
fixed greeting runs between 15:49:45 and 15:59:44 UTC; regression between 16:00:00 and 16:01:54 UTC.
The two versions ran in separate local Compose stacks. This is a reconstructed source baseline
requested by the owner after the review, **not historical production evidence collected before editing**.

## Inputs and results

- [Baseline inputs](baseline-orders.json): the original Анна/P01 brief in `warm`, `neutral` and
  `firm`, plus the unnamed screenshot brief in `neutral`; three runs each.
- [Greeting inputs](../../greeting_cases.json): 12 RU/EN/ES cases, three runs each, including names
  belonging to the freelancer, a manager, ambiguous people and a brand.
- [Regression inputs](../../qa_cases.json): P01, P02, P04 and P05, once each. No P03 exists in this set.
- Full scenario records: [baseline](baseline-runs.jsonl), [fixed](fixed-runs.jsonl),
  [regression](regression-runs.jsonl). Every record includes input/output, scenario identity,
  source SHA, runtime prompt hashes, model, reasoning effort, timing and provider calls.
- Additional ledger fields, including actual provider policy and model:
  [baseline](baseline-provider-calls.json), [fixed](fixed-provider-calls.json),
  [regression](regression-provider-calls.json).
- [Report](report.json): every actual first line, expected opening, answer hash, automatic findings,
  per-case semantic assessment and the disposition of diagnostic flags.
- [Environment provenance](environments.json): API URLs, Compose projects, source/profile fingerprints
  and prompt hashes independently checked against the Git blobs.
- [CI snapshot](ci-checks-08ede358.json): all required checks passed for the implementation commit,
  including full-check, frontend, PostgreSQL concurrency and atoms-proof; CodeRabbit was skipped.

The provider ledger confirms `default_text_generation_v1`, OpenAI and `gpt-6-luna` on both versions.
The running worker router read by the existing collector records `openai/gpt-6-luna`, reasoning
`medium`. Quotas were unmetered; no product prompt or model setting was overridden for individual runs.
The composer prompt hash changed from
`8ff01adfd3e9858f2fea32050cff9fb3ee92423fabb8c968ed39aaad3c4157f9` to
`023916bbb59468e11cd83e9b2a18836c34b70b84f8b2a76b5846cdf84526a2dd`.
The gap prompt stayed at `f7608a3a6301ebe050a87e23a7d57b0432ed553f1b78f6ea9d804f950d57723d`.

The raw records retain `git_dirty=true`: Git reported only an untracked symlink to the existing
managed Python environment in each detached checkout. Tracked diffs were empty, and both the
source fingerprints and loaded prompt hashes were verified. The flag has not been rewritten.

## Assessment and limits

All 36 fixed greeting cases use the required one-line greeting, exact permitted name and tone-specific
punctuation, followed by a blank line and a pitch based on the supplied experience. None addresses
the freelancer, manager or brand as the client. Time-of-day greetings, gendered/familiar greetings
and named self-introductions were not observed.

All criteria of the four existing regression cases passed agent review: exclusions and named
conditions remain, unagreed terms are not accepted, agreed terms are confirmed, and speaker-identity
rules are retained. These are explicitly **agent assessments**, not fabricated human verdicts or
an execution of the complete ANY-631 browser/human acceptance protocol.

Two diagnostic findings remain in the fixed greeting set:

- `G01-ru-name-firm`, attempt 3: a long dash in the body. The evaluator classifies this as a
  non-blocking style warning; the baseline had three such warnings. Further style tuning is deferred.
- `G06-es-name-warm`, attempt 3: `language_unverified` for the five-word gap description
  “No mencionas experiencia diseñando menús.”, below the detector's six-word minimum. The agent
  confirmed that the proposal and gap are Spanish; the original diagnostic flag is preserved.

No unusable or critical automatic finding occurred in the 40 fixed-version scenarios. The baseline
has three `missing_required` findings because the unnamed case already contains the new greeting
regex; comparison against the selected rule in the report independently marks all 12 baseline
openings as failures. The old warm tone sometimes used Анна inside its pitch, so the evidence does
not support saying that the old version never used a client's name.

This evidence resolves the missing versioned reproduction/acceptance finding for the selected
rule and sample. It does not establish a universal success rate, production/browser behavior,
or A04 gap-classification quality beyond the checks recorded here. No production deployment occurred.

## Reproduction

Use the repository's `dev-live-up --product proposal_ai` runner in isolated checkouts of the two
commits, with existing operator-managed provider credentials. Verify the effective profile before
running `scripts/agent/proposal_ai_eval.py run` from that checkout:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py run \
  --api-url "$API_URL" --compose-project "$COMPOSE_PROJECT" \
  --orders "$ORDERS_PATH" --series "$SERIES" --repeats "$REPEATS" \
  --timeout 180 --out "$NEW_RUNS_PATH"
```

Use baseline-orders with three repeats on the old commit, greeting_cases with three repeats on the
fixed commit, and qa_cases once on the fixed commit. The existing collector's local-ledger reader
uses database user `produser` and database `proddb`; these isolated stacks were configured accordingly.
Preserve the results as new evidence and assess their criteria; do not overwrite this run record.
