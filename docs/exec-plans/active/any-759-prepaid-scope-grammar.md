# ANY-759: Prepaid Request scope grammar

## Status

- State: active
- Owner: agent
- Created: 2026-11-27
- Last updated: 2026-11-27
- Review date: 2026-11-27
- Next action: owner reviews the scoped fix, model evidence, and remaining validation caveats
- Blocker: quick-check/full-check have three failures in unchanged deployment-runner tests; no green full-check claim
- Baseline: `26128baa3ae87ad9213906af18697feafff28470`

## Goal and boundaries

Make the opening scope description copy-ready without changing its facts, payment
terms or message kind. Product-owned prompt and regression tests only; no shared
atom, runtime, frontend or dependency changes. No confirmed analogous defect in
other Freelancer products; Brief Decoder already requires full sentences outside
verbatim lines and labels.

## Implementation and validation

- [x] Freeze six RU/EN/ES payment cases and nine A/B/C controls.
- [x] Collect unmodified Luna medium baseline from isolated live stack.
- [x] Add grammar rule and Python prompt contract test.
- [x] Collect candidate Luna matrix and Terra/Sol comparisons using the existing browser collector.
- [x] Run focused product/API checks, quick-check, config, architecture, docs and full-check (failures recorded below).
- [x] Record acceptance evidence and handoff for owner review.

## Progress

- Managed Python 3.12 doctor passed. System Python 3.14 doctor lacks pytest and
  pydantic; use the managed environment.
- Existing local worktree worker has live credentials configured, but its prompt
  SHA and active Sol model differ from the required baseline. Rebuild the profile
  before collecting. Rebuilt and verified the baseline deployment; the worker
  prompt matched the checkout and the Luna override was restored after collection.
- Baseline delivered 18/18 responses with matching scenario IDs, exact canonical/UI
  text and one successful A06 step each. No dangling clause occurred; some responses
  omitted payment conditions, stage identity or the intended language. This sample
  does not disprove the historical fragment. Provider ledger records the actual
  Luna model and deployment reasoning medium; direct reasoning effort is null.
- Added only the planned product prompt rule and Python regression assertion.

## Live evaluation

The baseline prompt SHA-256 is `c2f448cd4ddfbba865c1524e42751b4009dbcc107d277fec28fb6fc528857654`;
the candidate is `57a698d7cc3173e66ff070ac983c385c6526ba8f0318b16adce646d68a7a565d`.
Both matched the respective running worker before collection. The canonical local live profile
selects `sol_text_generation_v1` / `anytoolai.sol_text`, not Luna. Luna and Terra were selected
temporarily in the active model group, never through the client. Each series restored the exact
original router in a finally block with readback verification. At the end, the worker router
again matched the checkout (`dede022d99bc94440ea14f212cc669d939a39b51dbb73e8d0ef83ef5510aa1d2`),
with Sol medium selected. No model configuration is changed in this ticket.

All 153 fresh browser submissions succeeded technically: distinct session IDs, exact submitted
inputs, one successful A06 action per session, matching canonical and displayed text, actual
provider model, and successful start/result responses. The original Russian candidate-Luna
clipboard spot-check matched exactly. Provider metadata records deployment reasoning `medium`,
but direct reasoning effort is null; effective provider reasoning is not independently verified.
Raw browser traces stayed local. The sanitized evidence JSON includes exact inputs and visible
outputs, trace hashes, ledger fields, and individual semantic assessments.

### Comparable payment-request cases (18 attempts per model)

| Prompt/model | Ready | Dangling scope errors | Physical calls | Estimated USD/usable | Median UI seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline Luna | 9/18 | 0 | 22 | 0.000984 | 10.66 |
| Candidate Luna | 9/18 | 0 | 21 | 0.000994 | 8.78 |
| Candidate Terra | 18/18 | 0 | 25 | 0.003918 | 10.78 |
| Candidate Sol | 18/18 | 0 | 18 | 0.006409 | 8.76 |

### Complete candidate matrices (45 attempts per model)

| Model | Ready | Grammar errors | Semantic failures | Physical calls | Estimated USD/usable | Median UI seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Luna | 33/45 | 0 | 12 | 49 | 0.000641 | 8.55 |
| Terra | 45/45 | 0 | 0 | 54 | 0.003719 | 10.74 |
| Sol | 44/45 | 0 | 1 | 45 | 0.006792 | 8.76 |

Costs are runtime ledger estimates including retries, not provider invoices. All A/B/C
controls selected the correct message kind and contained no payment demand or request to
report payment. Luna omitted required stage-start conditions in nine payment requests,
returned Russian in two English controls, and overstated settlement in English control
`CU-P-EN-A` attempt 2. The same settlement criterion applies to Sol's Russian control
`CU-P-RU-A-1`: wording that can strengthen full receipt of the advance into full payment
of the stage is a conservative failure; explicitly acknowledging receipt of the full advance
remains valid. All 27 settlement controls were rechecked against this criterion; no other
verdict changes were needed. Terra kept the advance acknowledgment unambiguous. Its three
English original-case outputs elide the explicit adjective "separate", but identify the agreed
research stage and its boundaries; this is not treated as a scope loss. Minor currency wording is a
non-critical polish caveat. Semantic scoring accepts meaningful paraphrases, not exact strings.

The historical dangling fragment did not recur even on the baseline. All candidate outputs
had grammatically complete statements or meaningful scope constructions, including legitimate
prepositional openings. The small regression test pins the prevention rule, but these finite
samples do not demonstrate a causal reduction in grammar errors. No further grammar prompt
refinement was justified; remaining Luna failures concern commercial-condition retention,
settlement wording and language, not the target construction. The model comparison is more
informative than adding more instructions. Terra is the strongest measured full-matrix candidate
at lower estimated cost per usable response than Sol; keep the existing model configuration
until a separate owner-approved, broader model decision. Sol passes all 18 targeted payment requests.

## Validation results

- Six focused Python test modules: passed.
- Complete Freelancer product suite and quick-check harness tests: passed independently.
- Config, architecture, documentation, and generated documentation validation: passed.
- Quick-check: 4,380 passed, 12 skipped, 723 deselected, three failures (17m 12s).
  The first two are `tests/test_runner.py::test_prod_stack_running_reflects_compose_ps_output`
  and `tests/test_runner.py::test_prod_stack_running_propagates_timeout`: an existing local
  production env file triggers Compose environment resolution in tests whose subprocess
  mocks expect only the Compose ps command. The third,
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`, requires
  passwordless sudo. Those source/test files are unchanged; none was suppressed or fixed
  as part of this grammar ticket. The managed Python refresh needed network access and
  succeeded on retry. An initial sandboxed focused API run stalled; the identical
  expanded-permission run passed.
- Full-check: failed at its quick-check stage with the same three failures; 4,380 passed,
  12 skipped, 723 deselected (11m 41s). Its frontend and product-suite stages did not run.
  Independently, `frontend-check` passed locked install, lint, typecheck, tests,
  generated API contract check and build; the complete Freelancer suite passed as noted above.
- Exact Russian fixture input and the 15-case structure were verified, along with 153 distinct
  sessions, all technical conditions and the restored Sol router. Final documentation and
  whitespace checks passed.

## Code review follow-up

- Corrected the Luna settlement assessment and recomputed the full-matrix aggregates above.
  All raw inputs, outputs, trace hashes, provider records and payment-request aggregates remain
  unchanged.
- The reusable Python collector previously hashed the Update prompt irrespective of suite
  mode. It now selects the prompt from the suite's single supported mode (omitted mode still
  means Update), verifies worker content against the checkout before producing a manifest or
  mutating the router, and rejects mixed or unsupported modes. Both offline review surfaces
  render the complete Prepaid billing context rather than assuming Update notes.
- The original 153 attempts used the lower-level browser collector with independently verified
  Prepaid prompt hashes. This tooling fix enables future collection through the Python CLI;
  it does not retroactively attribute the historical evidence to that CLI or require new paid runs.
- After these fixes, 416 focused evaluation, product, prompt and API tests passed; config,
  architecture, documentation and whitespace checks passed. No runtime prompt was changed.

### Second code review round: private interactive review

The interim CodeQL autofix hid Prepaid billing values in the terminal but left Update
inputs, generated responses, criteria and agent observations in the same output channel.
It also prevented the reviewer from comparing a Prepaid response against the actual case.
The review tool now uses a single private presentation contract for both modes:

- Run the existing `client_update_writer_eval.py review` command, then open the printed
  temporary `case.txt` path in a local editor. The file contains the complete case (including
  language, tone and billing fields where present), response, numbered criteria and any
  hash-matching agent observation. The HTML report uses the same complete input rendering.
- Enter decisions in the terminal by criterion number. The terminal shows progress and
  outcomes, not the full inputs, responses, criteria or observation content. The temporary
  directory is private, the file is owner-only on POSIX, and the file is removed on normal
  completion or interruption. A file creation failure stops the review before any decision.
  Persistent evidence and verdict files remain local review artifacts, not console logs.
- 420 focused evaluation, product, prompt and API tests passed, including both modes,
  private file contents and permissions, redaction, cleanup, and failure before decisions.
  Config, architecture, documentation and whitespace checks passed. The GitHub CodeQL
  result for this revision still needs CI verification. No runtime prompt, model or stored
  live output was changed, and no additional paid calls were made.

### Third code review round: termination lifecycle

The offline review CLI returned through its dispatcher before the collector's SIGTERM
handler was installed. Review now owns its termination handler at its common CLI entry
point; both direct and dispatched review commands unwind the private directory on catchable
SIGTERM, exit with status 143, and restore the previous handler. Saved verdicts remain
intact and an unfinished run remains pending. Forced termination that cannot be intercepted
(for example SIGKILL or Windows TerminateProcess) cannot guarantee cleanup of a temporary
file; the private directory and owner-only POSIX file permissions remain the boundary.
Real child-process SIGTERM tests cover both CLI entry paths after a partial verdict has
been saved, verify removal of the file and directory, and compare the persisted verdict
bytes before and after termination. No paid evaluations or product runtime changes are needed.
All 423 focused evaluation, product, prompt and API tests passed, with config, architecture,
documentation and whitespace validation also passing.

## Handoff

The scoped implementation is ready for owner review. All eighteen targeted payment requests
pass on the current Sol live profile; Terra passes the complete matrix and warrants broader
model-selection consideration. Do not switch the default or mark acceptance complete on behalf
of the owner: the Sol settlement caveat, Luna's semantic failures and the non-green repository
gate remain visible. This is a low-priority iterative generation improvement, not a reason to
expand the task into general linguistic or model-policy redesign.
