# ANY-849 Brief Decoder input feedback

## Status

- State: active
- Owner: agent
- Created: 2026-11-26
- Last updated: 2026-11-26
- Review date: 2026-11-26
- Next action: owner review and authorization to push the task branch.
- Blocker: none.

## Scope

Brief Decoder should ask what the client wants done when a submitted text has no identifiable
commission or deliverable. Short requests and briefs missing ordinary project details still
receive an analysis. Use the existing risk detector and product field validation path. Keep the
version 2 artifact contract compatible with previously stored results.

## Implementation plan

1. Verify the two reported inputs from the production recheck and prepare the Russian, English
   and Spanish task-presence suite. Reproduce the UI gap with a focused failing test.
2. Add the missing-task issue to the Brief Decoder workflow and output schema. Keep all four
   workflow stages and use the existing empty-question document path.
3. Map the issue to the existing accessible textarea error and translate the hint in all seven UI
   locales. Normalize the same outer whitespace as submission for rejection matching.
4. Verify publication, recovery compatibility, correction, and ordinary result rendering with
   deterministic tests. Run repository and isolated live checks and record outcomes.

## Evidence

- Starting revision `7a90428a1797ffc576246082b25a5f591e978f67` on `feature/ANY-849`.
- Repository doctor passed with the managed Python 3.12 interpreter.
- Confirmed both exact inputs against the November 11, 2026 Linear attachment.
- Replayed both exact inputs on an isolated stack built from the starting revision. The worker
  used `default_text_generation_v1` with `openai/gpt-6-luna` and configured medium reasoning.
  The provider ledger confirmed Luna on all four calls for each run.
- Junk published with `missing_information` in 15.4 seconds. The bare recipe published with
  `missing_information` and `ambiguity` in 16.3 seconds. In Chrome with Russian selected, both
  produced a result with Copy and the Acceptance Builder button. Neither showed a field message.
- Baseline A04 prompt SHA-256 was
  `a8b150c1f681ad541aadcf8a2ba6e8340f2e85e813e13ba316b2de0bc70cf37f`.
  Baseline A05 was `198c42b2e229ecd26d23d1e92fa6fefe5cf5f38b95b961957f06bda1dbc9e003`.
- A mixed-version replay returned a generic error in the old web build for both marked version 2
  results. Both mounted tests passed with the updated web build and the same response envelope.

## Verification

- Focused Python tests passed (1,246). Both reported inputs published a version 2 artifact with
  the original text, the new issue and the A10 empty-question fallback under a controlled provider.
- The complete Freelancer Suite Python tests passed (1,715).
- Both frontend files passed (53 tests). They exercise focus and error association, all seven
  locales, previous result clearing, version 2 recovery, and correctable rejection.
- The standalone `frontend-check` passed lint, type checks, tests, API type drift and builds.
- The Brief Decoder Playwright suite passed (9 tests), including correction after trim-only edits.
- `full-check` reached the end of its backend gate with 4,364 passing tests and three failures
  in `tests/test_runner.py`. A clean starting-revision snapshot reproduced all three in this
  environment. Two mocked Compose tests are affected by the local production env file. The
  activation-marker test requires passwordless `sudo -u nobody`.
- In Chrome with Russian selected on the live build, empty input displayed the required-field
  error with zero starts. Both reported inputs kept the draft and displayed the localized task
  hint after one start, with Copy and the handoff absent. The short recipe commission returned
  an analysis with both actions.
- The live worker used the default Luna policy with medium reasoning configured. The collector
  captured the following SHA-256 values from the running worker.

| Worker source | SHA-256 |
| --- | --- |
| A01 prompt | `0968f8fcc1762feaf10e86c11fffe41a58b960eceac2b4dda034d56902903c44` |
| A04 prompt | `735ff5cbb0940a0ee5a3a251299e1454d0636575af800b7131d5a3572af48b2c` |
| A05 prompt | `365ae08640d54a38e5ad080177f707b3066409b1c276af98b7e9a3a1db395570` |
| A10 prompt | `b535e867748d970b020218c1b3ebc2a0ff386af100f4331b73cf67754a7376a1` |
| Workflow | `f88bd663238858f7f23a9d8346e875881bfad1c1cf6d05dc725abad33152bfd3` |
| Output schema | `40de2ea4c94720b41d5b7bc53a495f3beac39d1538dcbb1608bcff0be840931b` |

### Live task-presence matrix

The collector ran against the starting revision plus the changes in this task. All 48 attempts
published a valid artifact and preserved the source text. The A04 artifact matched the published
issue list in each attempt. All 187 provider calls in the ledger used `gpt-6-luna`. Medium was
the configured reasoning effort. The ledger did not independently report the effective effort.

| Input | Expected decision | RU | EN | ES |
| --- | --- | --- | --- | --- |
| Bare recipe | Field hint | 3/3 | 3/3 | 3/3 |
| Write a recipe | Analysis | 3/3 | 3/3 | 3/3 |
| Edit supplied recipe | Analysis | 3/3 | 3/3 | 3/3 |
| Vague website brief | Analysis | 3/3 | 3/3 | 3/3 |
| Logo deliverable without a verb | Analysis | 3/3 | 3/3 | 3/3 |

The language-neutral junk showed the marker in 3/3 attempts. All 12 field-hint runs published
one high-severity marker with no evidence and no questions.
All 36 positive controls published with no marker. The Chrome acceptance above separately
checked the visible field and result states on real provider runs.

### Release compatibility

The updated browser and backend should ship together. A version 2 artifact saved before this
change can render using its original categories. A previous web build rejects the new category
through its closed parser.

## Review follow-up

1. Keep the submitted input and current form independent in the result-rejection path.
   Use the correlated canonical artifact as the submitted-input baseline when it has a source.
   Restore it only into an untouched form. Keep Brief Decoder's existing tab-storage behavior.
2. Give A05 the ordinary question categories through its existing taxonomy input. Keep version 2
   artifacts readable across both revisions and check localized labels for every readable category.
3. Verify attachment and retry, editing and duplicate submission guards, and A05 membership
   rejection. Recheck ordinary question output and loading of older artifacts.

Both reported recovery paths reproduced before the change. After the fix, Chrome reopened
both rejected live results by session link, restored the source and focused the brief field.
Submitting the same text or editing only outer whitespace issued zero starts. Correcting each
brief issued one start and rendered an analysis. Paid recovery tests also covered an accepted
session and a pending start replayed with its original key.

The web recovery and product suites passed 484 tests. TypeScript and ESLint passed. The
selected Python suites passed 1,248 tests, including the worker rejecting an issue-only
category in a new question and the version 2 schema accepting the stored legacy shape.

On the isolated live worker, all 16 RU, EN and ES cases matched their expected outcomes.
All four no-task inputs had the A04 marker and zero questions. The 12 positive controls
published ordinary analyses. Every question in the new artifacts used an ordinary category.
The 63 provider calls used Luna. The worker's A05 prompt SHA-256 was
`a325382763259e06b9d282f1af6bac3f8559692d7db4027fe994647b090d7e8a` and its workflow SHA-256 was
`964e68022708a94e586b77cdd6d267ab6847c7b67c7febbecf640bc37fa676be`.

## Main integration

- Integrate `main` at `cf8ae980` into `feature/ANY-849`.
- Preserve both suites of tests for localized feedback and question copying. The rejected
  result must expose neither copy action. Keep the task-presence and delivery-deviation
  eval suites independently selectable.
- Check the merged result recovery, A05 category validation, web and smoke tests. Compare
  the executable Brief Decoder workflow, prompts, and model configuration to the previously
  live-tested revision.

All three merge conflicts were in test files. The combined tests preserve localized
missing-task feedback, correction and session recovery, question-only copying, and
both eval inventories. The schema, prompts, workflow, model policies, and provider router
are identical to the live-tested revision `81c1bda8`.

On the merged tree, 2,285 Python tests passed across Freelancer Suite, Brief Decoder and
Acceptance Builder API bundles, and the relevant eval collectors. All 1,208 web-mirror
tests passed, and the 74 focused Brief Decoder tests passed after adding assertions for
the new Copy questions action. All nine isolated Playwright smoke tests passed, including
missing-task rejection, correction, question-only copying and the zero-question outcome.
Type checks, lint, config, architecture, documentation and generated-document checks passed.
