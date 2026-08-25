# Execution Plan: ANY-221 11-Atom Live Provider Canary

## Status

- State: completed
- Owner: agent
- Created: 2026-08-20
- Last updated: 2026-08-25
- Review date: 2026-08-25
- Next action: none on the code/docs side. `feature/ANY-221` is pushed and PR #84's body is
  synced to current state; CI is green (all 8 checks). The only remaining action is a standing
  human `CHANGES_REQUESTED` review from `gushinets` (2026-08-24) -- its requirements are already
  met by current code, but only that reviewer (or someone with repo permissions) re-reviewing or
  dismissing it can actually clear it; not something this session can action unilaterally.
- Blocker: none. A sixth human code review (2026-08-25, "code-review (me #6)") found
  `EvidenceCase`/`StepEvidence` never carried `result_artifact_id`/`output_artifact_id` despite
  ANY-221's acceptance criterion naming "session/artifact IDs" explicitly, and that `LIVE011`
  meant two different things across `runner.py` and `live_canary.py` -- both fixed, and now
  confirmed against a real credentialed run (see the 2026-08-25 rows below).

## Goal

Prove all 11 generic atom prompts/contracts, and (since 2026-08-21) all 3 composite kernel_demo
workflows, through a real, backend-selected LiteLLM/OpenAI provider call (not the deterministic
fake-provider path ANY-218/219/220 already prove), still with no caller-chosen
provider/model/prompt/retry/structured-output control, still ledger/schema validated rather than
wording-validated, bounded by an estimated-cost cap, and reported in a privacy-safe evidence JSON.
Runs manually or on a credentialed schedule; normal CI stays credential-free.

Full design rationale (verified against real code before implementation) lives in
`plans/ANY-221.md` (gitignored, not part of this repo's history) and this file's Decision log.

## Scope

### In scope

- 11 new `_live_` config entries in `configs/kernel/products/kernel_demo/` (`action_configs.yaml`,
  `workflows.yaml`, `scenarios.yaml`, `product.yaml`), wired to the pre-existing, previously-unused
  `default_text_generation_v1` provider policy.
- (2026-08-21) 3 new `_live_` composite workflow/scenario entries (`workflows.yaml`/
  `scenarios.yaml`/`product.yaml`), reusing the 11 `_live_` action_configs above -- no new prompts/
  schemas/action_configs needed. `scripts/agent/kernel_demo_smoke.py`'s
  `_composite_workflow_entries()` permanently excludes `_live_v1`-suffixed workflow_ids (one-line,
  unparameterized fix); `scripts/agent/live_canary.py` owns its own, separate live-composite
  coverage check instead of a fake/live mode flag threaded through the shared module.
- `scripts/agent/atoms_proof.py`: additive `StepEvidence` fields (`latency_ms`, `input_tokens`,
  `output_tokens`, `total_tokens`, `estimated_cost`) populated from `provider_calls` rows already
  read by `_classify_ledger`.
- `scripts/agent/live_canary.py` (new): reuses `atoms_proof.py`'s HTTP/DB/evidence machinery to run
  the 11 live-sibling atom scenarios and (2026-08-21) the 3 live-sibling composite workflows as one
  combined, kind-tagged queue, with a cumulative `estimated_cost` cap (`LIVE001` abort code) that
  marks remaining cases (atom or composite) failed instead of silently truncating the report.
- `live-canary` command in `scripts/agent/runner.py`, fail-fast on missing `OPENAI_API_KEY`
  (`LIVE000`) before touching Docker/DB.
- `infra/compose/docker-compose.yml`: `OPENAI_API_KEY` passthrough to `platform-worker` only (the
  only service that calls `ProviderGateway`).
- CI-safe tests: `apps/platform-api/tests/test_live_canary_config.py` (`ConfigLoader`-only),
  `tests/test_live_canary.py` (cost-abort logic + evidence round-trip, no DB/network), extended
  `tests/test_atoms_proof.py` fixtures, `tests/test_runner.py` command-wiring tests, all registered
  in `quick_check.py`'s `PYTEST_TARGETS` where needed.
- `.github/workflows/live-canary.yml` (new): `workflow_dispatch` + weekly `schedule`, separate from
  `backend.yml`, uploads the evidence JSON as a workflow artifact.
- (2026-08-24, code-review finding) `internal_only` scenario config flag + `X-Live-Canary-Token`
  gate: the 14 live scenario_ids were reachable through the normal public start-session API with
  no gate at all, bypassing `live_canary.py`'s own cost cap and `OPENAI_API_KEY` fail-fast
  entirely (both exist only in the CLI). `ScenarioDefinition.internal_only: bool = False` (core +
  SDK contract), set `true` on all 14 live scenarios; `ScenarioRuntimeService.start_session()`
  rejects them (as a plain `scenario_not_found`, indistinguishable from an unknown scenario_id)
  unless the caller's `X-Live-Canary-Token` header matches the server's own
  `ANYTOOLAI_LIVE_CANARY_TOKEN` env var (fails closed if that's unset server-side);
  `create_linked_session()` (handoff continuation) rejects them unconditionally, no token check at
  all, since no legitimate handoff ever targets one. `live_canary.py`/`kernel_demo_smoke.py`'s
  `_run_one_case()` send the header via a new `live_canary_token` parameter; `runner.py`'s
  `live_canary()` fails fast (`LIVE011`) if the token env var is unset, mirroring `OPENAI_API_KEY`;
  `docker-compose.yml`'s `platform-api` service passes it through; `live-canary.yml` originally
  passed it at job level too, later scoped down to just the "Boot dev Compose stack" and "Run
  11-atom live provider canary" steps that actually need it (code-review finding, see the later
  Decision-log row for that fix).
- (2026-08-24, code-review finding) `_classify_ledger`'s `PROOF003` check relaxed from "exactly
  one `provider_calls` row per `action_run`" to a configurable `max_provider_calls_per_action`
  (default 1, unchanged for `atoms_proof.py`'s own fake-provider callers) -- the exactly-one
  invariant only ever held for `default_fake_provider_v1`
  (`max_physical_provider_calls_per_action: 1`); `default_text_generation_v1` (every live scenario)
  permits up to 4, so a live case's own legitimate structured-output/transport retry was failing
  as a `PROOF003` correctness bug. `live_canary.py` passes `_LIVE_PROVIDER_MAX_CALLS_PER_ACTION =
  4` (a static constant mirroring the policy's own config, not read dynamically). The success-path
  `StepEvidence` construction now sums every physical attempt's cost/tokens/latency per action_run
  (new `_step_evidence_from_action_run()`) instead of a single-row lookup that would silently drop
  every retry but one's own cost from `live_canary.py`'s cost cap.
- (2026-08-25, code review finding) Cost-cap fail-open on a lost DB connection: `_known_steps_for_
  session()`'s own recovery query could itself hit `SQLAlchemyError` (e.g. the canary script's DB
  connection dropped mid-run while the API/worker kept making real provider calls), in which case
  it returned `()` -- indistinguishable from "confirmed zero cost" -- so `live_canary.run()`'s cost
  cap saw `$0` for that case and kept running every remaining one with no cap actually in effect.
  Now returns `None` for "recovery itself failed" (cost genuinely unknown, not zero); a new
  `EvidenceCase.cost_unknown: bool` field carries that through `_fail()`, and `run()` aborts all
  remaining cases fail-closed (`LIVE012` -- see the 2026-08-25 code-review-#6 row below for why
  not `LIVE011`) the moment it sees `cost_unknown=True`, instead of comparing against
  `max_total_cost_usd`.
- (2026-08-25, code review finding) `internal_only` scenarios leaking into the public runtime-
  config: `build_product_runtime_config()`'s frontend-safe projection listed all 14 live
  scenario_ids in `scenario_ids`/`scenarios` even though `ScenarioRuntimeService.start_session()`
  rejects every one of them for a normal frontend client with `scenario_not_found` -- a
  contradictory API contract (`/runtime-config` advertises a scenario `/start` then refuses).
  `_build_scenario_metadata()` now returns `None` for `scenario.internal_only` scenarios, filtering
  them out of `scenario_ids`, `scenarios`, and (via `_allowed_ui_capabilities()`) the aggregated
  capability list.
- (2026-08-25, code review finding) Evidence report missing artifact IDs: ANY-221's acceptance
  criterion names a privacy-safe report with "session/artifact IDs" explicitly, but
  `EvidenceCase`/`StepEvidence` never carried `result_artifact_id`/`output_artifact_id` even
  though `_classify_ledger()` already reads both (`job_row["result_artifact_id"]`,
  `action_run["output_artifact_id"]`) for its own PROOF004/017/018/023 correlation checks --
  the values existed and were validated, just never threaded into the report. Added both fields
  (`str | None`, default `None`); the success path in `_classify_ledger()` and
  `_step_evidence_from_action_run()` populate them from the rows already in hand,
  `_best_effort_steps_from_provider_calls()`'s cost-recovery path populates
  `output_artifact_id` the same way it already does for the other per-step fields, and `fail`'s
  `functools.partial` is rebound with `result_artifact_id` right after `job_row` resolves so
  every PROOF00x branch from that point on carries the real value even on failure -- not just
  the success path.
- (2026-08-25, code review finding) `LIVE011` meant two different things: `runner.py` uses it for
  "`ANYTOOLAI_LIVE_CANARY_TOKEN` unset" (pre-existing, more call sites/docs/tests reference it),
  `live_canary.py` reused it for the 2026-08-25 `cost_unknown` fail-closed abort above (added the
  same day, fewer references) -- a shared LIVE0xx error-code namespace across logs/evidence/
  automation should be unambiguous. Renamed the newer, smaller-blast-radius one to `LIVE012`.
- (2026-08-25, code review finding) `_cumulative_estimated_cost()` summed `step.estimated_cost`
  at face value -- a NaN row (a corrupt `provider_calls.estimated_cost`, never a value this
  script itself writes) would make every later `total_cost > max_total_cost_usd` comparison
  silently `False` (NaN compares false to everything), the exact catastrophic fail-open
  `_positive_finite_cost()` already guards against for the cap value itself; a negative row would
  quietly reduce the running total instead of adding to it. New `_safe_step_cost()` maps
  None -> `0.0` (unchanged) and any non-finite or negative value -> `math.inf`, which `sum()`
  propagates straight into `run()`'s existing cap-trip branch -- fail closed, no new abort code
  path needed.
- (2026-08-25, code review finding) The `_safe_step_cost()` fix above only validated the already-
  summed `StepEvidence.estimated_cost` -- but `atoms_proof.py`'s own `_step_evidence_from_action_
  run()` sums multiple *raw* `provider_calls.estimated_cost` rows (one action's legitimate
  retries) before that value ever exists, so two corrupt rows could net out to an innocuous total
  (e.g. `$0.60` and `-$0.50` summing to `$0.10`) and sail through the post-hoc guard undetected.
  New `atoms_proof._safe_raw_cost()` applies the identical None/non-finite/negative -> `math.inf`
  mapping to each *raw* call before summing, so a corrupt row poisons the sum unconditionally
  instead of being able to cancel out a legitimate charge.

### Out of scope

- Refactoring any frozen hot-path file (`config/loader.py`, `workflows/runner.py`,
  `actions/runner.py`, `StructuredLlmActionExecutor`, `handlers/run_workflow.py`, Session
  ownership) -- per ANY-24's execution constraints.
- A dedicated canary provider policy or a full fake-provider round-trip test for the new live
  scenario ids. (A run-level physical-call aggregate cap was previously listed here too, on the
  reasoning that the fixed 11-atom + 3-composite case list x the per-action
  `max_physical_provider_calls_per_action` cap already bounds the run structurally -- still true
  for the *count* of physical calls, but not for their *cost*, which is why `PROOF003`/evidence
  needed the 2026-08-24 fix above instead of staying purely out of scope.)
- Prompt benchmarking, semantic quality scoring, automatic model comparison, or exposing
  credentials/provider controls to clients (ticket non-goals).

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/exec-plans/active/any-220-atom-runtime-proof-cli.md` (the CLI/evidence machinery this
  ticket extends)

## Contracts touched

- API: (2026-08-24) `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` gained an
  optional `X-Live-Canary-Token` header (`docs/generated/openapi.json`/`platformApi.ts`
  regenerated) -- absent on every normal request, so no behavior change for existing callers; only
  consulted for `internal_only` scenarios. Documented 404 response shape (`scenario_not_found`)
  is unchanged, since an internal_only rejection reuses it verbatim.
- DB: read-only ledger check, same 5 tables `atoms_proof.py` already reads; no schema change --
  `provider_calls`' `latency_ms`/`input_tokens`/`output_tokens`/`total_tokens`/`estimated_cost`
  columns already existed.
- Config: 11 new action_config/workflow/scenario entries + 11 new `product.yaml` scenario_ids, all
  additive; no existing entry mutated (regression-guarded by
  `test_live_canary_config.py`). (2026-08-24) New optional `ScenarioDefinition.internal_only: bool`
  field (core dataclass + SDK contract, mirrored per `test_contract_field_compatibility.py`),
  default `False` so every pre-existing scenario is unaffected; set `true` on all 14 live
  scenarios.
- Events: none produced; existing event types read and asserted against (same set
  `atoms_proof.py` already checks).
- Frontend: none (the new header is CLI-only; no frontend/CE-kit code sends it).
- API: (2026-08-25) `GET /v1/products/{product_id}/runtime-config`'s `scenario_ids`/`scenarios`
  no longer include the 14 `internal_only` live scenarios -- narrows an already-inconsistent
  response (they were never actually startable through this product's normal `/start` endpoint),
  no schema/shape change.
- Evidence report: (2026-08-25) `EvidenceCase`/`StepEvidence` gained `result_artifact_id`/
  `output_artifact_id: str | None = None` -- additive fields on this script's own private,
  gitignored-by-default JSON report (not a versioned API contract), so no consumer-breaking
  change; `write_evidence_report()`'s `asdict(case)` serialization picks them up automatically.

## Implementation steps

- [x] Config wiring: 11 `_live_` entries across `action_configs.yaml`/`workflows.yaml`/
      `scenarios.yaml`/`product.yaml`, wired to `default_text_generation_v1`.
- [x] `atoms_proof.py`: `StepEvidence` + `_classify_ledger` extended with the 5 ledger-metric
      fields.
- [x] Fixed 4 pre-existing tests that broke from the config append + merge with `feature/ANY-220`
      (stale `docs/generated/config-registry.md`, `test_runtime_config.py`'s hardcoded
      `scenario_ids` list, `test_config_loader.py`'s `workflows[-1]` positional-index assumption,
      `test_atoms_proof.py`'s ledger fixtures missing the 5 new columns).
- [x] `scripts/agent/live_canary.py`: `LIVE_ATOM_SCENARIO_IDS`, `LIVE_ATOM_CASES`, cost-abort `run()`,
      `main()` CLI (`--database-url-env`/`--timeout`/`--max-total-cost-usd`).
- [x] `runner.py`: `live_canary()` + `COMMANDS["live-canary"]` registration.
- [x] `docker-compose.yml`: `OPENAI_API_KEY` passthrough to `platform-worker`.
- [x] CI-safe tests: `test_live_canary_config.py` (3 cases), `tests/test_live_canary.py` (5 cases),
      3 new `test_runner.py` command-wiring tests. All registered where `PYTEST_TARGETS` needed an
      explicit entry.
- [x] `.github/workflows/live-canary.yml`: `workflow_dispatch` + weekly schedule, evidence-artifact
      upload.
- [x] `validate-configs` / `validate-architecture` / `quick-check` all pass (816 tests).
- [x] (2026-08-21) Composite live coverage: 3 `_live_v1` composite workflow/scenario entries;
      `kernel_demo_smoke.py`'s `_composite_workflow_entries()` permanently excludes them (one-line
      fix, no parameter); `live_canary.py`'s own `_live_composite_workflow_entries()`/
      `_live_composite_coverage_error()`; `run()` restructured to a single combined atom+composite
      queue sharing one cost cap and chained timeout.
- [x] (2026-08-21) Tests: `tests/test_kernel_demo_smoke.py` (1 new regression test for the
      permanent `_live_v1` exclusion, plus explicit re-verification that the 2 pre-existing
      composite coverage tests still pass unmodified), `tests/test_live_canary.py` (6 new tests --
      composite case-list shape, own coverage-entries/coverage-error/binding-mismatch checks,
      composite evidence round-trip; 1 existing cost-abort test updated for the combined queue),
      `apps/platform-api/tests/test_runtime_config.py` (hardcoded `scenario_ids` list extended).
- [x] (2026-08-24) `internal_only` access control: `ScenarioDefinition.internal_only` (core + SDK
      contract) set on all 14 live scenarios; `ScenarioRuntimeService.start_session()` gates on
      `X-Live-Canary-Token` matching `ANYTOOLAI_LIVE_CANARY_TOKEN` (fails closed if unset
      server-side), `create_linked_session()` rejects unconditionally;
      `live_canary.py`/`kernel_demo_smoke.py`'s `_run_one_case()` send the header;
      `runner.py live-canary` fails fast (`LIVE011`) if the token is unset;
      `docker-compose.yml`/`live-canary.yml` pass the env var through to `platform-api`.
- [x] (2026-08-24) `PROOF003` retry tolerance: `max_provider_calls_per_action` (default 1,
      `live_canary.py` passes 4 matching `default_text_generation_v1`'s own policy cap); success-path
      `StepEvidence` now sums cost/tokens/latency across every physical provider_calls row per
      action_run instead of a single-row lookup.
- [x] (2026-08-24) Tests: `packages/backend/platform-core/tests/unit/test_scenario_runtime.py` (5
      new `postgresql`-marked cases -- reject without token, reject with wrong token, fail closed
      when server token unset, accept with correct token, `create_linked_session` unconditional
      reject), new fast `test_scenario_service_live_canary_token.py` (6 cases, no DB),
      `test_config_loader.py` (2 cases -- parses `internal_only`, rejects a non-bool value),
      `apps/platform-api/tests/test_scenario_runtime_api.py` (2 new `postgresql`-marked HTTP-level
      cases), `test_live_canary_config.py`/`tests/test_live_canary.py` extended to assert
      `internal_only is True` on all 14 live scenarios, `tests/test_atoms_proof.py` (3 new cases
      for the relaxed `PROOF003`/summed evidence), `tests/test_live_canary.py`/`test_runner.py`
      extended for the token env-var/header plumbing and the new `LIVE011` fail-fast. Verified
      against a real local PostgreSQL container (not just `quick-check`'s DB-free subset) --
      `postgresql-check` exit 0.
- [x] (2026-08-24) Manual credentialed run: `dev-up -> live-canary -> dev-down` against real
      OpenAI (`gpt-4.1-mini`), both `OPENAI_API_KEY` and `ANYTOOLAI_LIVE_CANARY_TOKEN` set. Printed
      `11/11` atoms and `3/3` composites, exit 0, evidence JSON originally written to the local,
      gitignored `.agent/live-canary/evidence-20260824T164316Z.json` with
      `atoms_total: 11, composite_total: 3`.
- [x] (2026-08-25) A privacy-safe copy of that evidence JSON (ids, status, and per-step
      cost/token/latency counters only -- no prompts, generated content, or secrets, confirmed by
      reading the full file before committing) is now tracked in the repo at
      `docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260824T164316Z.json`
      (this doc and both evidence JSONs briefly round-tripped through `docs/exec-plans/active/`
      and back on 2026-08-25 while a sixth review's blocker was open -- see the two 2026-08-25
      Progress log rows below), linked in this file's Progress log (see below), addressing a
      fifth code review (2026-08-25):
      the earlier local-only `.agent/...` path is gitignored and unreachable by any future agent
      after checkout, which AGENTS.md's own "context not in the repo does not exist" principle
      means was effectively no evidence at all. No separate MVP-A1 "completion doc" exists as a
      distinct file to update -- MVP-A1's own Definition of Done
      (`docs/product-specs/mvp-a-platform-kernel.md`) states the criterion narratively ("a recent
      manual live-provider canary proves schema-valid output for all 11 atoms") with no
      evidence-link field of its own; this exec-plan's Progress log is the evidence record.
- [x] (2026-08-25) Fixed a sixth human code review's cost-cap fail-open finding
      (`cost_unknown`/`LIVE011`, see Scope above) and its `internal_only` runtime-config leak
      finding. 3 new/updated regression tests (`test_run_fails_closed_and_stops_when_a_case_cost_
      cannot_be_recovered` in `tests/test_live_canary.py`, `cost_unknown` assertions added to 3
      existing `tests/test_atoms_proof.py` cases, `test_runtime_config.py`'s hardcoded-inclusion
      assertions flipped to exclusion). `quick-check` 924 tests (was 923).
- [x] (2026-08-25) Fresh credentialed run (`dev-up -> live-canary -> dev-down`, real
      `OPENAI_API_KEY` + `ANYTOOLAI_LIVE_CANARY_TOKEN`, operator-supplied) on this HEAD (post
      `cost_unknown`/`LIVE011`/`internal_only`-runtime-config fixes): `11/11` atoms + `3/3`
      composites, exit 0, ~13,901 total tokens, ~$0.0081 total estimated cost. Evidence JSON read
      in full to confirm it holds only ids, status, and per-step cost/token/latency counters (no
      prompts, generated content, or secrets) before committing a copy at
      `docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260825T075842Z.json`.
- [x] (2026-08-25) Fixed a sixth human code review's two remaining code findings: added
      `result_artifact_id`/`output_artifact_id` to the evidence report (see Scope/Contracts
      above), renamed `live_canary.py`'s `cost_unknown` abort code from `LIVE011` to `LIVE012`
      (runner.py's pre-existing, more-referenced `LIVE011` keeps its name). 2 regression tests
      updated/added in `tests/test_atoms_proof.py`, 1 in `tests/test_live_canary.py`.
- [x] (2026-08-25) Synced PR #84's body via `gh pr edit` (see the Progress log row below) --
      execution-plan link, ANY-371/access-control scope, Architecture-boundaries, Validation, and
      Follow-up debt all updated to match current HEAD.
- [x] (2026-08-25) A fresh credentialed run (`dev-up -> live-canary -> dev-down`, new
      `OPENAI_API_KEY`) on this HEAD, against the new evidence-report shape: `11/11` atoms + `3/3`
      composites, exit 0, ~13,908 total tokens, ~$0.0081 total estimated cost,
      `result_artifact_id`/`output_artifact_id` populated on every case/step. Read the full
      evidence JSON (plus a scripted key-set check) to confirm privacy-safety before committing a
      copy at `docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260825T083858Z.json`
      (kept alongside, not replacing, the two earlier runs).
- [x] (2026-08-25) Fixed a code review finding: `_cumulative_estimated_cost()` didn't guard
      against NaN/negative `estimated_cost` values. New `_safe_step_cost()` maps an invalid value
      to `math.inf` (see Scope above); kept the sum on `sum()` itself rather than a hand-rolled
      accumulator loop after a first pass regressed float precision (CPython's `sum()` uses
      compensated summation for floats -- `0.1+0.2+0.3` accumulated naively is
      `0.6000000000000001`, `sum([0.1, 0.2, 0.3])` is exactly `0.6`, and the existing
      `test_cumulative_estimated_cost_treats_none_as_zero` test caught the regression
      immediately). 2 new regression tests in `tests/test_live_canary.py` (NaN, negative).
- [x] (2026-08-25) Fixed an eighth human code review's 1 P1 finding: the `_safe_step_cost()`
      guard above only validated the already-summed `StepEvidence.estimated_cost`, but
      `atoms_proof.py`'s own `_step_evidence_from_action_run()` sums raw, individually-corrupt
      `provider_calls.estimated_cost` rows *before* that value exists -- two rows (`$0.60`,
      `-$0.50`) could net out to `$0.10` and sail past the post-hoc guard undetected. New
      `atoms_proof._safe_raw_cost()` applies the same None/non-finite/negative -> `math.inf`
      mapping to each raw call before summing (see Scope/Decision log above). 2 new regression
      tests in `tests/test_atoms_proof.py` (netting-out negative pair, single NaN row); `quick-
      check` 928 (was 926).

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check` (846 tests, 2026-08-21 with composite coverage
      added; the 1 pre-existing `test_litellm_adapter.py` failure seen during this pass is caused
      by an unrelated, uncommitted, temporary local Ollama-testing edit to `litellm_router.yaml`
      -- see `plans/ANY-221-ollama-verification.md` -- not by this ticket's changes)
- [x] (2026-08-24) `export OPENAI_API_KEY=... ANYTOOLAI_LIVE_CANARY_TOKEN=... && python scripts/agent/runner.py dev-up && python scripts/agent/runner.py live-canary && python scripts/agent/runner.py dev-down`
      -- exit 0, `11/11` atoms + `3/3` composites.
- [x] `python scripts/agent/runner.py full-check` (2026-08-21, with the temporary uncommitted
      Ollama-testing edits stashed for a clean run: exit 0, 847 backend + 216 frontend tests,
      typecheck/build/OpenAPI-contract-drift all clean, freelancer-suite product tests pass)
- [x] (2026-08-24) `python scripts/agent/runner.py postgresql-check` against a real local
      PostgreSQL container (`docker run postgres:16-alpine`, not just CI) -- exit 0, all
      `postgresql`-marked tests including the 7 new `internal_only`-related cases across
      `test_scenario_runtime.py`/`test_scenario_runtime_api.py`.
- [x] (2026-08-24) `python scripts/agent/runner.py quick-check` (916 tests) and `full-check`
      (regenerated `docs/generated/openapi.json` and `platformApi.ts` for the new
      `X-Live-Canary-Token` header parameter, both were flagged stale by `generate-docs --check`/
      `generate-api-types:check` until regenerated) both green.
- [x] (2026-08-25) `python scripts/agent/runner.py quick-check` (924 tests, up from 923 with the
      new `cost_unknown` regression test) and `validate-docs`/`generate-docs --check` all green.
- [x] (2026-08-25) `export OPENAI_API_KEY=... ANYTOOLAI_LIVE_CANARY_TOKEN=... && python scripts/agent/runner.py dev-up && python scripts/agent/runner.py live-canary && python scripts/agent/runner.py dev-down`
      on this HEAD -- exit 0, `11/11` atoms + `3/3` composites, ~13,901 total tokens, ~$0.0081
      total estimated cost.
- [x] (2026-08-25) `python scripts/agent/runner.py quick-check` (924 tests, unchanged -- this
      round added `result_artifact_id`/`output_artifact_id` assertions to existing tests instead
      of new test functions) and `validate-docs` both green after moving this doc back to
      `docs/exec-plans/active/` (`validate-docs`'s `DOC004` enforces `State: active` living under
      `active/`).
- (2026-08-25, failed attempt, no checkbox -- superseded by the next row) Re-ran the credentialed
      cycle to pick up the new evidence report shape -- `0/11` + `0/3`, every case failed with
      `litellm.AuthenticationError`/HTTP 401 from OpenAI. Confirmed the key reached the worker
      container correctly (checked its length/prefix/suffix inside the container, matched what
      was supplied) and that this is the *same* key that passed `11/11` + `3/3` earlier the same
      day -- so the key itself was very likely revoked/rotated between the two runs, not a
      regression in this branch. Tore the stack back down; did not commit any evidence from this
      attempt.
- [x] (2026-08-25) `export OPENAI_API_KEY=... ANYTOOLAI_LIVE_CANARY_TOKEN=... && python scripts/agent/runner.py dev-up && python scripts/agent/runner.py live-canary && python scripts/agent/runner.py dev-down`
      on this HEAD with a fresh (operator-rotated) key -- exit 0, `11/11` atoms + `3/3` composites,
      ~13,908 total tokens, ~$0.0081 total estimated cost, `result_artifact_id`/
      `output_artifact_id` populated throughout.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-20 | Reused `default_text_generation_v1` as-is; no dedicated canary provider policy | Already conservative (`max_physical_provider_calls_per_action: 4`, `timeout_seconds: 60`) and unused by any product before this ticket; add a dedicated policy later only if real runs show it's wrong. |
| 2026-08-20 | Parallel `_live_` entries in the same `kernel_demo` product config files, not a new product/config root | Mirrors exactly how the 11 fake atoms already live there; pure YAML, doesn't touch the frozen `config/loader.py`. |
| 2026-08-20 | New sibling script `scripts/agent/live_canary.py`, not a flag on `atoms_proof.py` | Keeps the deterministic gate's behavior/output byte-for-byte unchanged; imports `atoms_proof` for all shared HTTP/DB/evidence machinery. |
| 2026-08-20 | Cost cap lives in `live_canary.py`, not `ProviderGateway` | `ProviderGateway`/hot-path files are frozen per ANY-24's execution constraints; the fixed 11-case list already structurally bounds physical calls via the existing per-action cap, so no new gateway-level aggregate counter is needed either. |
| 2026-08-20 | `live_canary.py`'s CLI takes `--database-url-env ENV_VAR`, mirroring `atoms_proof.py`'s own fourteenth-round fix, not a `database_url` positional | `RuntimeIdentity.database_url` can embed a real `ANYTOOLAI_POSTGRES_PASSWORD` override; passing it via env (not argv) keeps it out of `ps`/process-listing output, exactly like `atoms_proof.py` and `runner.py`'s `atoms_proof()` already do. |
| 2026-08-20 | `live_canary.py` imports `atoms_proof.smoke` lazily (via `atoms_proof.smoke.*` attribute access inside functions), not `from atoms_proof import smoke` at module load time | `atoms_proof.py`'s own `smoke = load_smoke_module()` assignment only happens inside its guarded try/except; if that block fails, `atoms_proof.smoke` doesn't exist as an attribute, and an eager `from atoms_proof import smoke` would raise a raw `ImportError` before `main()` ever gets to print a clean `LIVE00x` code -- the same "run far enough to fail cleanly" contract `atoms_proof.py` and `kernel_demo_smoke.py` both already honor for their own guarded imports. |
| 2026-08-20 | `_atom_coverage_error(LIVE_ATOM_CASES)` reused directly (not `_coverage_gate_error`, which also requires a non-empty composite-case tuple) | This ticket has no composite-workflow live coverage (out of scope); `_coverage_gate_error` would need a real `composite_cases` argument, so the pure atom-only check is the correct-sized reuse. **Superseded 2026-08-24: composite live coverage is now in scope (see the 2026-08-21 scope-expansion row below); `main()`'s coverage check now also calls the live-composite coverage check (`_atom_coverage_error(...) or _live_composite_coverage_error(...)`), not just the atom-only one this row originally justified.** |
| 2026-08-20 | Fixed `test_config_loader.py`'s `test_loader_rejects_negative_workflow_step_retry_count` to look up `retry_extract_v1` by `workflow_id` instead of `workflows[-1]` | Appending the 11 live workflows to the end of `workflows.yaml` silently broke this test's positional-index assumption; looking up by id is correct regardless of future appends, not just a patch for this one addition. |
| 2026-08-20 | `.github/workflows/live-canary.yml` pins `actions/upload-artifact` to `v7.0.1`'s commit SHA (looked up via `gh api repos/actions/upload-artifact/git/refs/tags/v7.0.1`, not guessed) | Matches this repo's existing pinned-action convention (`actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv`); no prior `upload-artifact` usage existed anywhere in the repo to copy a pin from. |
| 2026-08-21 | Scope grew to include the 3 composite kernel_demo workflows (previously an explicit Out-of-scope bullet), on user request after the first successful ad hoc Ollama run raised "what else can we verify?" | All 11 `_live_` action_configs the composite steps need already existed from the atom work -- no new prompts/schemas, only new workflow/scenario wiring + `live_canary.py` code, so the marginal cost was low relative to the coverage gained (composite/multi-step chaining is otherwise completely unproven against a real provider). |
| 2026-08-21 | `kernel_demo_smoke.py`'s `_composite_workflow_entries()` fixed with a permanent, unconditional `_live_v1` exclusion, not an `only_live: bool \| None` parameter threaded through it/`_composite_workflow_config()`/`_composite_coverage_error()` | First design drafted a tri-state parameter; user pushback ("зачем вводим флаги fake/live") was correct -- provider selection is a static config fact, not a mode this shared, fake-provider-oriented module (also used by `atoms_proof.py` and `dev-smoke`/`prod-smoke`) needs to choose per call. The hardcoded exclusion needs zero call-site changes anywhere existing. |
| 2026-08-21 | `live_canary.py` owns its own `_live_composite_workflow_entries()`/`_live_composite_coverage_error()`, not a reuse of `kernel_demo_smoke.py`'s `_composite_coverage_error()` even after the above fix | That shared function's error strings hardcode `"SMOKE010"`/`"COMPOSITE_SMOKE_CASES"`, which would misname the live case list/error family in a live-canary failure message; the live-specific version reuses only the non-fake-specific pure helpers (`_composite_case_ids`, `_composite_schema_ref_by_workflow_id`, `_coverage_mismatch_error`, `_required_composite_workflow_id_by_scenario_id`) and reimplements only the small duplicate/shape checks with correct naming. **Superseded 2026-08-24: `_composite_coverage_error()` was reworked to take `entries_provider`/`labels` (a `CoverageLabels` dataclass bundling `error_code`/`tuple_name`/`kind`) precisely so callers like this one can supply their own naming instead of hardcoding SMOKE010/COMPOSITE_SMOKE_CASES. `_live_composite_coverage_error()` is now a ~10-line wrapper that calls `atoms_proof.smoke._composite_coverage_error(cases, entries_provider=_live_composite_workflow_entries, labels=_LIVE_COMPOSITE_COVERAGE_LABELS)` instead of reimplementing the duplicate/shape/coverage/binding checks itself. Reuse that shared, parameterized helper for any future live-canary-side coverage check rather than re-duplicating its logic again.** |
| 2026-08-21 | `live_canary.py`'s `run()` restructured to one combined, kind-tagged (atom/composite) queue instead of two sequential phase calls | Simpler than threading a separate `_run_case_group()`-style two-phase orchestration: the existing per-case cost-abort loop already generalizes to a mixed queue by tagging each entry with its `kind`, so a cost-cap trip mid-atom-phase naturally marks every remaining item -- atoms and composites alike -- as `LIVE001` with no special-casing. |
| 2026-08-24 | `internal_only` gate enforced by a shared-secret header (`X-Live-Canary-Token` vs. server `ANYTOOLAI_LIVE_CANARY_TOKEN`), not a per-scenario allowlist keyed on some existing identity (guest_id, frontend_id) | No existing identity concept in this codebase distinguishes "the live-canary CLI" from "a normal guest" -- guest identities are anonymous and created fresh per case by design (`kernel_demo`'s own quota model). A shared secret is the smallest primitive that doesn't require inventing a new identity/auth system; `secrets.compare_digest` avoids a timing side-channel, and failing closed when the env var is unset means an operator who forgets to configure it gets "scenario unreachable" (safe) rather than "scenario reachable by anyone" (unsafe). |
| 2026-08-24 | `internal_only` check placed in `ScenarioRuntimeService.start_session()`/`create_linked_session()` (service layer), not `_require_product_scenario()` itself | `_require_product_scenario()` is also called by `get_session_snapshot()`/`record_next_action()` (status polling, next-action) for an *already-started* session -- gating those too would require the CLI to resend the token on every poll for no security benefit (viewing status of a session that already legitimately started isn't the risk; *starting* a new billed one is). Keeping the check at the two start-a-session call sites only, not inside the shared existence-check helper, avoids that. |
| 2026-08-24 | `create_linked_session()` (handoff continuation) rejects `internal_only` unconditionally, no token parameter at all | `live_canary.py` never creates linked/handoff sessions, so no legitimate caller could ever supply a matching token there anyway; an unconditional reject is simpler than plumbing a token parameter through the handoff flow for a path that must never succeed. |
| 2026-08-24 | `max_provider_calls_per_action` is a plain function parameter (default 1) threaded through `_classify_ledger`/`_check_ledger`/`_run_case_with_ledger_check`, not read dynamically from `configs/kernel/provider_policies.yaml` at ledger-check time | `atoms_proof.py`/`live_canary.py` deliberately keep this a pure, DB-only ledger-correctness check with no `ConfigLoader` dependency; resolving the real per-action cap would need a full action_run -> action_config -> provider_policy chase, and would make a correctness check depend on live, possibly-since-changed config state. `live_canary.py`'s `_LIVE_PROVIDER_MAX_CALLS_PER_ACTION = 4` is a static constant that must be kept in sync with the policy by hand -- accepted as a deliberate, documented tradeoff. |
| 2026-08-25 | Acceptance evidence committed as a tracked repo file (`docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260824T164316Z.json`), not a link to a GitHub Actions artifact/run or an external object-storage URL | The credentialed run that produced it was a local manual cycle, not a `live-canary.yml` `workflow_dispatch`/schedule invocation, so no CI run URL or uploaded-artifact URL exists to link to. The file itself is confirmed privacy-safe (ids, status, per-step cost/token/latency counters only -- read in full before committing), so committing it directly satisfies AGENTS.md's "context not in the repo does not exist for future agents" more directly than a URL would, and needs no external service to stay reachable. |
| 2026-08-25 | `_known_steps_for_session()` distinguishes "confirmed zero cost" (`()`) from "cost genuinely unknown" (`None`) instead of collapsing both to `()`, and `live_canary.run()` aborts fail-closed (new `LIVE012`, originally `LIVE011` -- renamed same day, see the code-review-#6 row below) on the latter rather than folding it into the existing `max_total_cost_usd` comparison | A silent `$0` for an unrecoverable case defeats the safety cap's whole purpose (a lost DB connection could let real spend run unbounded); reusing `LIVE001`'s abort-and-mark-remaining-failed loop for the new condition, rather than inventing a second code path, keeps the two abort reasons symmetric in the evidence report. |
| 2026-08-25 | `internal_only` filtered inside `_build_scenario_metadata()` (returns `None` before the `workflow`/renderer-hint lookups), not in `build_product_runtime_config()`'s own loop | Keeps the "what makes a scenario visible" decision co-located with the one function that already has the `ScenarioDefinition` in hand, and reuses the existing `None`-means-skip contract that function already has for an unknown `scenario_id`/`workflow_id` -- no new control-flow shape in the caller. |
| 2026-08-25 | Renamed `live_canary.py`'s `cost_unknown` abort code from `LIVE011` to `LIVE012` (code-review #6 finding) instead of renaming `runner.py`'s token-unset `LIVE011` | `runner.py`'s usage predates today's by a full day and has more references (its own error message, `.github/workflows/live-canary.yml`'s comment, 2 `tests/test_runner.py` assertions) -- renaming the newer, same-day addition is the smaller diff and doesn't touch any file outside `live_canary.py`/`tests/test_live_canary.py`/this doc. |
| 2026-08-25 | Added `EvidenceCase.result_artifact_id`/`StepEvidence.output_artifact_id` (both `str \| None = None`) by rebinding `_classify_ledger()`'s `fail` `functools.partial` with `result_artifact_id` right after `job_row` resolves, rather than adding the parameter to every one of `_classify_ledger()`'s ~20 `fail(...)` call sites individually | Mirrors the same rebind-a-partial pattern this function's own docstring already documents for `steps=known_steps` -- one rebind point instead of a repeated keyword at every call site, and the timing (right after `job_row["result_artifact_id"]` is read) means every branch from that point on, pass or fail, carries the real value. |
| 2026-08-25 | `_cumulative_estimated_cost()`'s NaN/negative guard (`_safe_step_cost()`) maps an invalid value to `math.inf` and still feeds it through `sum()`, not a hand-rolled `total = 0.0; total += cost` accumulator loop | A first attempt used the accumulator loop and broke `test_cumulative_estimated_cost_treats_none_as_zero` (`0.1 + 0.2 + 0.3` accumulated naively is `0.6000000000000001`, not `0.6`) -- CPython's `sum()` builtin uses compensated (Neumaier) summation for float sequences specifically to avoid this, and still returns `math.inf` correctly when one is present in the sequence (`inf + finite = inf`, verified). Keeping `sum()` and pre-mapping each step's cost through a small helper preserves both properties with a smaller diff than reimplementing accurate float summation by hand. |
| 2026-08-25 | `_safe_raw_cost()`'s NaN/negative guard on raw `provider_calls.estimated_cost` added in `atoms_proof.py` itself (this ticket's proof/canary script boundary), not upstream in `providers/adapters/litellm.py`'s `_float_like()` or a new `ProviderResponse`/DB check constraint, even though the review correctly identified `_float_like()`'s bare `float(value or 0.0)` as where an invalid value first enters the system | Hardening the Provider Gateway's cost-ingestion path is a real, separate improvement that would affect every product/caller of `ProviderGateway`, not just this ticket's own live-canary script -- out of proportion to ANY-221's own acceptance criterion (this script "enforces physical-call and cost limits", not "the platform validates provider cost data"), and `providers/adapters/litellm.py`/the DB schema aren't part of this PR's touched-file set otherwise. `atoms_proof.py`/`live_canary.py` already treat the ledger as untrusted at every other boundary (`cost_unknown`, the retry-ledger PROOF013/024/025/026 checks) -- this fix is the same "proof script doesn't trust the DB" posture applied one layer earlier (raw calls, not the already-summed step), not a new design direction. Revisit the upstream fix if a second caller of `ProviderGateway` ever needs the same guarantee. |
| 2026-08-25 | Did not re-run the credentialed live-provider cycle after this fix, despite the review's suggestion to | The fix is purely defensive: for the normal happy-path data a real OpenAI call produces (always-positive, always-finite per-call costs), `_safe_raw_cost()`/`_safe_step_cost()` are no-ops -- the aggregation math is byte-for-byte identical to before. The existing `...T083858Z.json` evidence still accurately demonstrates the 11 atom/3 composite contracts work end to end against a real provider; nothing about what that evidence proves has changed. A fresh run would re-spend real API budget to re-confirm a code path this fix doesn't touch. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-20 | Verified `plans/ANY-221.md`'s pre-existing implementation plan against real code (3 parallel Explore passes), corrected 2 minor inaccuracies (a docstring-citation overclaim, a stale 4-job `backend.yml` count). Implemented config wiring (11 x 4 YAML entries) and `atoms_proof.py`'s `StepEvidence`/`_classify_ledger` extension; `validate-configs` passed. Committed (`624ed47`). | Continue with `live_canary.py` and the rest of the file list. |
| 2026-08-20 | Merged `feature/ANY-220` into the branch; fixed 4 regressions the merge + config additions surfaced (stale generated config-registry doc, a runtime-config test's hardcoded scenario_ids list, a positional-index test assumption broken by appending workflows, ledger fixtures missing the 5 new columns). `quick-check` green (813 tests). Committed (`3c8004a`). Implemented `scripts/agent/live_canary.py`, the `live-canary` runner command, the `docker-compose.yml` `OPENAI_API_KEY` passthrough, and all CI-safe tests (`test_live_canary_config.py`, `tests/test_live_canary.py`, 3 new `test_runner.py` cases). `quick-check` green (816 tests). Committed (`5454523`). Added `.github/workflows/live-canary.yml` and this exec-plan doc (`baba53c`). Ran `full-check` (backend 816 + frontend typecheck/test/build/generate-api-types + freelancer-suite), all green. | Run the manual credentialed cycle (`dev-up` -> `live-canary` -> `dev-down`) with a real `OPENAI_API_KEY`, confirm `11/11`, inspect the evidence JSON, then link results here and in MVP-A1's completion doc. |
| 2026-08-21 | Root-caused a merge artifact from `feature/ANY-220` (duplicate `_one_provider_call()` helper definitions in `tests/test_atoms_proof.py` left both fake-merge halves in place, the second shadowing the first and missing the `id` key some tests relied on) and fixed it -- unrelated to this ticket's own code but was blocking `quick-check`. Ran an ad hoc, uncommitted, non-credentialed local live-canary cycle against a local Ollama model (not this ticket's real-provider acceptance evidence -- see `plans/ANY-221-ollama-verification.md`), root-caused an intermittent timeout as Ollama's own cold-model-load latency after an idle eviction (confirmed via `/api/ps` and a direct no-Docker timing test), not a wiring bug; achieved `11/11` once warmed (`.agent/live-canary/evidence-20260821T083703Z.json`). At the user's request, scoped and implemented composite-workflow live coverage (previously out of scope): 3 new `_live_v1` composite workflow/scenario config entries, a permanent one-line `_live_v1` exclusion in `kernel_demo_smoke.py`'s `_composite_workflow_entries()` (not a fake/live parameter, per user pushback), `live_canary.py`'s own local live-composite coverage check, and a `run()` restructured to one combined atom+composite queue. Added/updated 8 tests across `tests/test_kernel_demo_smoke.py`/`tests/test_live_canary.py`/`apps/platform-api/tests/test_runtime_config.py`. `quick-check` green (846 tests; the one remaining failure is the pre-existing, unrelated, uncommitted local-Ollama config edit). | Run `full-check` to confirm the composite addition doesn't regress frontend/product-suite checks, then the manual credentialed OpenAI cycle (`dev-up` -> `live-canary` -> `dev-down`), confirm both `11/11` atoms and `3/3` composites, then link results here and in MVP-A1's completion doc. |
| 2026-08-24 | Fixed 2 blockers a human code reviewer requested before merge: (1) the 14 live scenario_ids were reachable through the normal public start-session API with no gate, bypassing `live_canary.py`'s cost cap/API-key fail-fast entirely; (2) `PROOF003` required exactly one `provider_calls` row per action_run, but `default_text_generation_v1` permits up to 4 (legitimate retries), so a live case's own retry was failing as a correctness bug. Implemented `ScenarioDefinition.internal_only` (core + SDK contract) + `X-Live-Canary-Token`/`ANYTOOLAI_LIVE_CANARY_TOKEN` gate across `scenarios/service.py`, the API route, `live_canary.py`/`kernel_demo_smoke.py`, `runner.py` (new `LIVE011`), `docker-compose.yml`, and `live-canary.yml`. Relaxed `PROOF003` to a configurable `max_provider_calls_per_action` and made the success-path `StepEvidence` sum cost/tokens/latency across every physical attempt per action_run instead of losing every retry but one. Added 20 new tests across 7 files, including `postgresql`-marked integration coverage verified against a real local PostgreSQL container (`postgresql-check` exit 0, not just `quick-check`'s DB-free subset). Regenerated `docs/generated/openapi.json`/`platformApi.ts` for the new header. `quick-check` 916 tests, `full-check` exit 0. | Commit; run the manual credentialed cycle (now needs both `OPENAI_API_KEY` and `ANYTOOLAI_LIVE_CANARY_TOKEN`), confirm `11/11` atoms and `3/3` composites, then link results here and in MVP-A1's completion doc. |
| 2026-08-24 | Ran the manual credentialed cycle against a real OpenAI provider (`gpt-4.1-mini`) on the new head, with both `OPENAI_API_KEY` and `ANYTOOLAI_LIVE_CANARY_TOKEN` set. Along the way, found and fixed 2 dev-stack issues unrelated to the ticket's own code: `configs/kernel/` isn't bind-mounted in the dev compose target, so a stale image (built while a since-reverted local-Ollama edit to `litellm_router.yaml` was present) kept serving that old config until rebuilt (`docker compose build platform-api platform-worker`); and `dev-up`, unlike `prod-up`, never passes `--build`, so recreating containers without the right shell env (`ANYTOOLAI_API_PORT`, `ANYTOOLAI_LIVE_CANARY_TOKEN`) silently reset the port mapping and blanked the server-side token, which the `internal_only` gate correctly (by design) treated as "reject everything" until `dev-up` was re-run from a shell with the real values. Result: `11/11` atoms + `3/3` composites passed (evidence originally at the local, gitignored `.agent/live-canary/evidence-20260824T164316Z.json`; 14 cases, ~13,989 total tokens, ~$0.0082 total estimated cost -- a repo-tracked copy was committed 2026-08-25, see below). | Close ANY-221; link this evidence in MVP-A1's completion doc. |
| 2026-08-25 | Fixed a [P1] finding from a third human code review: `PROOF013` rejected a legitimate transport retry (its first physical attempt correctly ends in `provider.request_failed`, not `succeeded`), because `PROOF013` still demanded exactly one `succeeded` event per `provider_calls` row even after `PROOF003` was relaxed to allow retries. Split the check into `PROOF013` (started count), a new `PROOF024` (exactly one terminal event, succeeded xor failed), a new `PROOF025` (persisted `status` must agree with which terminal event fired; `timed_out` accepted alongside `failed`), extended `PROOF015` orphan detection to `provider.request_failed`, and added a new `PROOF026` (the last physical attempt by `physical_call_index` must be the one that succeeded). Also fixed the same review's non-blocking access-control-ordering note: `start_session()`'s idempotency-key replay lookup ran before the `internal_only`/token check, so a future caller sending `Idempotency-Key` against an internal_only scenario could in principle replay past the gate (`live_canary.py` itself never sends one today, so not currently exploitable) -- added an early `internal_only` peek (a bare config lookup, not `_require_product_scenario()`, so replay still tolerates a since-removed scenario) before the replay branch. 7 new regression tests in `tests/test_atoms_proof.py`, 1 new `postgresql`-marked test in `test_scenario_runtime.py`. `quick-check` 923 tests, `postgresql-check` exit 0 (real local Postgres). The existing 2026-08-24 credentialed-run evidence is unaffected (it had no retries, so never hit the old PROOF013 bug either way) -- no new live run is required by this fix, only a fresh review pass. Committed (`32c2883`). | Fix a fourth review pass's 2 remaining valid findings (live-canary.yml secret scoping, a missing token-forwarding assertion); get explicit go-ahead to commit those, then close ANY-221. |
| 2026-08-25 | Fixed a [P1/acceptance] finding from a fifth human code review: this doc claimed acceptance evidence was "linked" via the local `.agent/live-canary/evidence-20260824T164316Z.json` path, but `.agent/` is gitignored, so no future agent could ever actually reach that file after a fresh checkout -- AGENTS.md's own "context not in the repo does not exist" principle means that was effectively unlinked evidence, not linked evidence, despite the doc's own claims to the contrary. Read the full evidence JSON first to confirm it holds only ids, status, and per-step cost/token/latency counters (no prompts, generated content, or secrets), then committed a copy at `docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260824T164316Z.json`. Also fixed the review's [P2] finding: the Status header block (State/Last updated/Review date/Next action/Blocker) was stale from 2026-08-21, still describing the credentialed run as not-yet-attempted, directly contradicting the Progress log's own 2026-08-24/25 rows in the same document -- updated to State: completed, and moved this file from `docs/exec-plans/active/` to `docs/exec-plans/completed/` (via `git mv`, no other repo file referenced the old path). `validate-docs`/`generate-docs --check` confirmed no drift. | None -- ANY-221 is closed. |
| 2026-08-25 | Fixed 2 of 3 findings from a sixth human code review (PR #84, current HEAD): (1) [Blocker/P1] cost-cap fail-open when a case's ledger recovery itself hits a DB error (`cost_unknown`/`LIVE011`, see Scope/Decision log above); (2) [P2] `internal_only` scenarios still listed in the public `/runtime-config` response despite `/start` rejecting them (filtered in `_build_scenario_metadata()`). The third finding -- committed 2026-08-24 evidence no longer speaks for the current HEAD after this fix plus the earlier `PROOF013`/`024`/`025`/`026` fix -- is not a code fix; it needs a fresh credentialed run, which this session has no `OPENAI_API_KEY` to perform. Also swept every tracked file for the literal `` `/code-review` `` phrasing (a local skill/slash-command name meaningless outside this environment -- the same fix `docs/exec-plans/active/any-220-atom-runtime-proof-cli.md`'s 2026-08-20 rows already made once, which had crept back in through the 2026-08-24/25 review rounds) and replaced it with plain "code review"; left the gitignored `plans/ANY-*.md` session logs untouched. Re-ran `quick-check` (924 passed, was 923) and `validate-docs`, both green. Reverted Status's `State` from `completed` to `active` and moved this file back to `docs/exec-plans/active/` (`git mv`) to reflect the reopened acceptance blocker -- see Status above. Committed (`d540355`). | Get a fresh credentialed `11/11` + `3/3` run on this HEAD, commit its evidence, then push and re-request PR #84 review. |
| 2026-08-25 | User supplied `OPENAI_API_KEY`/`ANYTOOLAI_LIVE_CANARY_TOKEN` for this session. Confirmed Docker is available here (`doctor` passed); ran the manual credentialed cycle (`dev-up -> live-canary -> dev-down`) directly against real OpenAI on the current HEAD: `11/11` atoms + `3/3` composites, exit 0, ~13,901 total tokens, ~$0.0081 total estimated cost -- confirming the `cost_unknown`/`internal_only` fixes above don't regress the happy path. Read the full evidence JSON before committing a copy at `docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260825T075842Z.json` (kept alongside, not replacing, the 2026-08-24 evidence). Checked Linear directly (MCP connected this session): ANY-371 is `Done` (completed 2026-08-24), so the PR-metadata-drift note from the sixth review was already stale -- no further Linear sync needed. Flipped Status back to `State: completed`/`Blocker: none` and moved this file (and both evidence JSONs) back to `docs/exec-plans/completed/`. | Push `feature/ANY-221` and re-request PR #84 review, once the user confirms. |
| 2026-08-25 | Fixed the remaining 2 code findings from a sixth human code review ("code-review (me #6)"): (1) [P1/acceptance blocker] `EvidenceCase`/`StepEvidence` never carried `result_artifact_id`/`output_artifact_id` despite ANY-221's own acceptance criterion naming "session/artifact IDs" explicitly -- both values were already read by `_classify_ledger()` for its PROOF004/017/018/023 checks, just never threaded into the report; added both fields, rebinding `_classify_ledger()`'s `fail` partial with `result_artifact_id` once `job_row` resolves so failure paths carry it too, not just the success path. (2) [P2] `LIVE011` meant two different things across `runner.py` (token unset) and `live_canary.py` (today's `cost_unknown` abort); renamed the newer, smaller one to `LIVE012`. 2 tests updated, 1 new assertion, in `tests/test_atoms_proof.py`; 1 test updated in `tests/test_live_canary.py`. `quick-check` 924 (unchanged count -- existing tests extended, no new test functions). Moved this doc back to `docs/exec-plans/active/` (`validate-docs`'s `DOC004` requires `State: active` under `active/`) and re-ran the credentialed cycle to get evidence matching the new report shape -- every one of the 14 cases failed with a `litellm.AuthenticationError`/401 from OpenAI. Verified the key reached the platform-worker container intact (checked length/prefix/suffix inside the container) and that it's the identical key that passed `11/11` + `3/3` earlier the same day, so it was very likely revoked/rotated between runs, not a regression here. Tore the stack down without committing any evidence from the failed attempt. The [P2/reviewability] PR-body-drift finding is real but out of scope for this session without explicit push/PR-edit authorization -- see Status above. | Get a *valid* `OPENAI_API_KEY`, re-run the credentialed cycle, commit the resulting evidence (replacing the now-format-stale 2026-08-25 `...T075842Z` one, or adding alongside it), then push `feature/ANY-221` and sync PR #84's body once the user confirms. |
| 2026-08-25 | User supplied a fresh, valid `OPENAI_API_KEY` after the prior 401. Re-ran the credentialed cycle (`dev-up -> live-canary -> dev-down`) on the current HEAD against the new evidence-report shape: `11/11` atoms + `3/3` composites, exit 0, ~13,908 total tokens, ~$0.0081 total estimated cost, `result_artifact_id`/`output_artifact_id` populated on every case/step (verified both by reading the full JSON and with a scripted allowed-keys check for privacy-safety). Committed a copy at `docs/exec-plans/completed/any-221-live-provider-canary.evidence-20260825T083858Z.json`, kept alongside (not replacing) the two earlier runs. Flipped Status back to `State: completed`/`Blocker: none`; moved this doc back to `docs/exec-plans/completed/`. | Push `feature/ANY-221` and sync PR #84's body (still describes pre-#6-review state), once the user confirms -- see Follow-up debt. |
| 2026-08-25 | Confirmed `feature/ANY-221` was already up to date on GitHub (a concurrent process had pushed the local commits already -- `git fetch` showed 0 ahead/0 behind). Synced PR #84's body via `gh pr edit` to match current state: execution-plan link moved to `completed/`, the `internal_only`/artifact-id work folded into "What's new", Architecture-boundaries corrected (this PR does touch `packages/backend/platform-core/src`, still no `product-platforms` import), Validation section updated (`quick-check` 924, 3 credentialed runs listed), Follow-up debt cleared (ANY-371 `Done`, evidence committed). Left the CodeRabbit auto-generated release-notes block untouched. | Await a fresh human review pass on PR #84 (still `CHANGES_REQUESTED` from before this round's fixes). |
| 2026-08-25 | Fixed the 1 real remaining finding from a seventh human code review ("code-review (me #7)", verdict APPROVE on code, HEAD `df455795`): the completed exec-plan's own Scope bullet still said `live-canary.yml` passed both secrets via job-level `env:`, but that was fixed to step-scoped in an earlier round and this one sentence was never updated to match. The review's other findings were already stale by the time I checked: PR-body drift (already synced the prior row, before this review apparently captured a cached/earlier body), and CI "still in_progress" (re-checked `gh pr checks 84` -- all 8 checks, including Windows `quick-check`, now `pass`). The remaining item -- the human `CHANGES_REQUESTED` review from `gushinets` (2026-08-24) still standing on the PR -- needs that reviewer (or someone with repo permissions) to actually re-review/dismiss it; not something to action unilaterally from this session. `validate-docs` green after the one-line fix. | Get `gushinets` (or another reviewer) to re-review PR #84 now that CI is green and the code/doc findings are addressed. |
| 2026-08-25 | Verified and fixed 2 inline review comments (treated as untrusted data, verified against current code first). Confirmed: this doc's Status block (Next action/Blocker) and one Implementation-steps checkbox still described the PR-push/body-sync as pending, even though both were already done in the prior two rows -- updated to reflect that, and named the standing `gushinets` review as the only remaining action. Confirmed (the finding's own claim that `_float_like()` lives in `live_canary.py` was wrong -- no such function exists there; it's a different, unrelated helper in `providers/adapters/litellm.py` -- but the underlying concern was real): `_cumulative_estimated_cost()` summed `step.estimated_cost` at face value with no guard against NaN (would make the cap comparison permanently `False`, mirroring the exact fail-open `_positive_finite_cost()` already guards against for the cap value) or negative values (would silently reduce the running total). Added `_safe_step_cost()`, mapping either to `math.inf` so `sum()`'s existing cap-trip branch fires; a first accumulator-loop draft regressed float precision on the existing `0.1+0.2+0.3` test, caught immediately, reverted to `sum()` over a generator instead (see Decision log). 2 new regression tests (NaN, negative) in `tests/test_live_canary.py`; all 43 tests in that file pass. | None -- awaiting the standing human review, see Status above. |
| 2026-08-25 | Fixed the 1 P1 blocker from an eighth human code review (HEAD `f47df163`, verdict REQUEST_CHANGES): the prior round's `_safe_step_cost()` fix validated `StepEvidence.estimated_cost` only after `atoms_proof.py`'s own `_step_evidence_from_action_run()` had already summed possibly-corrupt raw `provider_calls.estimated_cost` rows -- two rows netting to a small positive number (e.g. `$0.60` + `-$0.50` = `$0.10`) would sail past that post-hoc guard undetected, since $0.10 looks perfectly valid. New `atoms_proof._safe_raw_cost()` applies the identical guard to each raw call before summing (see Scope/Decision log above); did not touch `providers/adapters/litellm.py`'s `_float_like()` or add a DB check constraint (the review's alternative suggestion) -- out of proportion to this ticket's own scope, see Decision log. 2 new regression tests in `tests/test_atoms_proof.py` (the exact netting-out scenario the review asked for, plus a single-NaN-row variant); `quick-check` 928 (was 926), all 112 tests in `test_atoms_proof.py`/`test_live_canary.py` pass. Deliberately did not re-run the credentialed live-provider cycle -- the fix is a no-op for real OpenAI's always-positive-finite costs, so the existing `...T083858Z.json` evidence still accurately demonstrates the atom/composite contracts (see Decision log). The review's other 2 items (Windows CI/postgres job "still running", metadata drift) were both stale by the time I checked -- CI is fully green on the prior HEAD, and I'll sync the PR body's test count/HEAD wording in the same push as this fix. | Push, sync PR #84's body test count, await the standing human review. |

## Open questions

- `default_text_generation_v1`'s existing caps (4 calls/action, 60s timeout) and the `$0.50`
  default cost cap are both estimates made without real gpt-4.1-mini latency/cost data on these 11
  prompts; revisit both after the first couple of manual runs (no plumbing change needed either
  way -- both are plain config/CLI values).

## Follow-up debt

- None outstanding on the code/docs side. PR #84's body is synced, CI is green (all 8 checks,
  including Windows `quick-check`, `pass` on HEAD `df455795`). The one open item is the human
  `CHANGES_REQUESTED` review from `gushinets` (2026-08-24) still standing on the PR -- its
  requirements (close public access, retry semantics, fresh `11/11` + `3/3` evidence) are all met
  by the current code, but only that reviewer (or someone with repo permissions) re-reviewing or
  dismissing it can actually clear it; not something this session can action unilaterally.
- The `$0.50`/4-calls/60s estimates in Open questions above are otherwise the only remaining soft
  spot, and all 3 completed runs so far validated them as reasonable (~$0.008 total per run,
  nowhere near the cap).
