# Rejected round 2 candidate: a8630c3e

Commit `a8630c3e746f6e524a25266309af2cc956d420e7` fixed Russian name inflection and expanded the
matrix. Its live run exposed a previously uncovered greeting error: `G11-en-noname-warm`, attempt 1,
started with `Hello,` instead of the required `Hi,`. This candidate is **not accepted**.

The collector was stopped after detection, with 27 greeting records and four QA records saved.
One already-submitted scenario completed in the worker after collection stopped; its API result
is preserved separately. All 32 submitted scenarios completed, with 64 physical provider calls
and USD 0.033605025 estimated cost. No output has been replaced by a retry.

- [Report](candidate-report.json): recorded first lines, flags and provenance.
- Inputs: [greeting](greeting-orders.json), [QA regression](regression-orders.json).
- Raw collector records: [greeting](greeting-runs.jsonl), [QA regression](regression-runs.jsonl).
- [Complete stack ledger](stack-provider-calls.json) includes the already-submitted scenario.
- [Recovered in-flight result](inflight-scenarios.json) is an API response, not a fabricated collector record.
- [Environment](environment.json): exact Git SHA/tree, prompt hashes and deployment fingerprints.

The inflected-name input produced `Здравствуйте, Анна Иванова!`. The failed English tone branch
led to an explicit language/tone/name selection table in the next candidate. The original 72-run
plan was not completed on this rejected prompt; the subsequent full verification is recorded
separately on its actual source commit.
