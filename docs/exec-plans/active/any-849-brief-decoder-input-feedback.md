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
