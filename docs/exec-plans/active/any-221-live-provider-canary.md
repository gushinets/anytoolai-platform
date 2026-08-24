# Execution Plan: ANY-221 11-Atom Live Provider Canary

## Status

- State: active
- Owner: agent
- Created: 2026-08-20
- Last updated: 2026-08-21
- Review date: 2026-08-21
- Next action: run the credentialed manual cycle (`OPENAI_API_KEY` + `dev-up` -> `live-canary` ->
  `dev-down`) to get the first real evidence report (now covering both the 11 atoms and the 3
  composite workflows), then link its result in this doc's Progress log and in MVP-A1's own
  completion doc.
- Blocker: none for the CI-safe half of this ticket; the manual credentialed run still needs an
  operator with a real `OPENAI_API_KEY` to execute it. A non-credentialed ad hoc local run against
  Ollama (not the ticket's real-provider acceptance evidence) already exercised the 11-atom path
  end-to-end -- see `plans/ANY-221-ollama-verification.md`.

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
  `docker-compose.yml`'s `platform-api` service and `live-canary.yml`'s job-level `env:` both pass
  it through.
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
      `11/11` atoms and `3/3` composites, exit 0, evidence JSON written to `.agent/live-canary/
      evidence-20260824T164316Z.json` with `atoms_total: 11, composite_total: 3`.
- [x] (2026-08-24) Linked the successful run's evidence in this file's Progress log (see below).
      No separate MVP-A1 "completion doc" exists as a distinct file to update -- MVP-A1's own
      Definition of Done (`docs/product-specs/mvp-a-platform-kernel.md`) states the criterion
      narratively ("a recent manual live-provider canary proves schema-valid output for all 11
      atoms") with no evidence-link field of its own; this exec-plan's Progress log is the evidence
      record.

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

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-20 | Verified `plans/ANY-221.md`'s pre-existing implementation plan against real code (3 parallel Explore passes), corrected 2 minor inaccuracies (a docstring-citation overclaim, a stale 4-job `backend.yml` count). Implemented config wiring (11 x 4 YAML entries) and `atoms_proof.py`'s `StepEvidence`/`_classify_ledger` extension; `validate-configs` passed. Committed (`624ed47`). | Continue with `live_canary.py` and the rest of the file list. |
| 2026-08-20 | Merged `feature/ANY-220` into the branch; fixed 4 regressions the merge + config additions surfaced (stale generated config-registry doc, a runtime-config test's hardcoded scenario_ids list, a positional-index test assumption broken by appending workflows, ledger fixtures missing the 5 new columns). `quick-check` green (813 tests). Committed (`3c8004a`). Implemented `scripts/agent/live_canary.py`, the `live-canary` runner command, the `docker-compose.yml` `OPENAI_API_KEY` passthrough, and all CI-safe tests (`test_live_canary_config.py`, `tests/test_live_canary.py`, 3 new `test_runner.py` cases). `quick-check` green (816 tests). Committed (`5454523`). Added `.github/workflows/live-canary.yml` and this exec-plan doc (`baba53c`). Ran `full-check` (backend 816 + frontend typecheck/test/build/generate-api-types + freelancer-suite), all green. | Run the manual credentialed cycle (`dev-up` -> `live-canary` -> `dev-down`) with a real `OPENAI_API_KEY`, confirm `11/11`, inspect the evidence JSON, then link results here and in MVP-A1's completion doc. |
| 2026-08-21 | Root-caused a merge artifact from `feature/ANY-220` (duplicate `_one_provider_call()` helper definitions in `tests/test_atoms_proof.py` left both fake-merge halves in place, the second shadowing the first and missing the `id` key some tests relied on) and fixed it -- unrelated to this ticket's own code but was blocking `quick-check`. Ran an ad hoc, uncommitted, non-credentialed local live-canary cycle against a local Ollama model (not this ticket's real-provider acceptance evidence -- see `plans/ANY-221-ollama-verification.md`), root-caused an intermittent timeout as Ollama's own cold-model-load latency after an idle eviction (confirmed via `/api/ps` and a direct no-Docker timing test), not a wiring bug; achieved `11/11` once warmed (`.agent/live-canary/evidence-20260821T083703Z.json`). At the user's request, scoped and implemented composite-workflow live coverage (previously out of scope): 3 new `_live_v1` composite workflow/scenario config entries, a permanent one-line `_live_v1` exclusion in `kernel_demo_smoke.py`'s `_composite_workflow_entries()` (not a fake/live parameter, per user pushback), `live_canary.py`'s own local live-composite coverage check, and a `run()` restructured to one combined atom+composite queue. Added/updated 8 tests across `tests/test_kernel_demo_smoke.py`/`tests/test_live_canary.py`/`apps/platform-api/tests/test_runtime_config.py`. `quick-check` green (846 tests; the one remaining failure is the pre-existing, unrelated, uncommitted local-Ollama config edit). | Run `full-check` to confirm the composite addition doesn't regress frontend/product-suite checks, then the manual credentialed OpenAI cycle (`dev-up` -> `live-canary` -> `dev-down`), confirm both `11/11` atoms and `3/3` composites, then link results here and in MVP-A1's completion doc. |
| 2026-08-24 | Fixed 2 blockers a human code reviewer requested before merge: (1) the 14 live scenario_ids were reachable through the normal public start-session API with no gate, bypassing `live_canary.py`'s cost cap/API-key fail-fast entirely; (2) `PROOF003` required exactly one `provider_calls` row per action_run, but `default_text_generation_v1` permits up to 4 (legitimate retries), so a live case's own retry was failing as a correctness bug. Implemented `ScenarioDefinition.internal_only` (core + SDK contract) + `X-Live-Canary-Token`/`ANYTOOLAI_LIVE_CANARY_TOKEN` gate across `scenarios/service.py`, the API route, `live_canary.py`/`kernel_demo_smoke.py`, `runner.py` (new `LIVE011`), `docker-compose.yml`, and `live-canary.yml`. Relaxed `PROOF003` to a configurable `max_provider_calls_per_action` and made the success-path `StepEvidence` sum cost/tokens/latency across every physical attempt per action_run instead of losing every retry but one. Added 20 new tests across 7 files, including `postgresql`-marked integration coverage verified against a real local PostgreSQL container (`postgresql-check` exit 0, not just `quick-check`'s DB-free subset). Regenerated `docs/generated/openapi.json`/`platformApi.ts` for the new header. `quick-check` 916 tests, `full-check` exit 0. | Commit; run the manual credentialed cycle (now needs both `OPENAI_API_KEY` and `ANYTOOLAI_LIVE_CANARY_TOKEN`), confirm `11/11` atoms and `3/3` composites, then link results here and in MVP-A1's completion doc. |
| 2026-08-24 | Ran the manual credentialed cycle against a real OpenAI provider (`gpt-4.1-mini`) on the new head, with both `OPENAI_API_KEY` and `ANYTOOLAI_LIVE_CANARY_TOKEN` set. Along the way, found and fixed 2 dev-stack issues unrelated to the ticket's own code: `configs/kernel/` isn't bind-mounted in the dev compose target, so a stale image (built while a since-reverted local-Ollama edit to `litellm_router.yaml` was present) kept serving that old config until rebuilt (`docker compose build platform-api platform-worker`); and `dev-up`, unlike `prod-up`, never passes `--build`, so recreating containers without the right shell env (`ANYTOOLAI_API_PORT`, `ANYTOOLAI_LIVE_CANARY_TOKEN`) silently reset the port mapping and blanked the server-side token, which the `internal_only` gate correctly (by design) treated as "reject everything" until `dev-up` was re-run from a shell with the real values. Result: `11/11` atoms + `3/3` composites passed (`.agent/live-canary/evidence-20260824T164316Z.json`; 14 cases, ~13,989 total tokens, ~$0.0082 total estimated cost). | Close ANY-221; link this evidence in MVP-A1's completion doc. |
| 2026-08-25 | Fixed a [P1] finding from a third human code review: `PROOF013` rejected a legitimate transport retry (its first physical attempt correctly ends in `provider.request_failed`, not `succeeded`), because `PROOF013` still demanded exactly one `succeeded` event per `provider_calls` row even after `PROOF003` was relaxed to allow retries. Split the check into `PROOF013` (started count), a new `PROOF024` (exactly one terminal event, succeeded xor failed), a new `PROOF025` (persisted `status` must agree with which terminal event fired; `timed_out` accepted alongside `failed`), extended `PROOF015` orphan detection to `provider.request_failed`, and added a new `PROOF026` (the last physical attempt by `physical_call_index` must be the one that succeeded). Also fixed the same review's non-blocking access-control-ordering note: `start_session()`'s idempotency-key replay lookup ran before the `internal_only`/token check, so a future caller sending `Idempotency-Key` against an internal_only scenario could in principle replay past the gate (`live_canary.py` itself never sends one today, so not currently exploitable) -- added an early `internal_only` peek (a bare config lookup, not `_require_product_scenario()`, so replay still tolerates a since-removed scenario) before the replay branch. 7 new regression tests in `tests/test_atoms_proof.py`, 1 new `postgresql`-marked test in `test_scenario_runtime.py`. `quick-check` 923 tests, `postgresql-check` exit 0 (real local Postgres). The existing 2026-08-24 credentialed-run evidence is unaffected (it had no retries, so never hit the old PROOF013 bug either way) -- no new live run is required by this fix, only a fresh review pass. Committed (`32c2883`). | Fix a fourth review pass's 2 remaining valid findings (live-canary.yml secret scoping, a missing token-forwarding assertion); get explicit go-ahead to commit those, then close ANY-221. |

## Open questions

- `default_text_generation_v1`'s existing caps (4 calls/action, 60s timeout) and the `$0.50`
  default cost cap are both estimates made without real gpt-4.1-mini latency/cost data on these 11
  prompts; revisit both after the first couple of manual runs (no plumbing change needed either
  way -- both are plain config/CLI values).

## Follow-up debt

- None outstanding. The credentialed run is linked (2026-08-24 Progress log row); the
  `$0.50`/4-calls/60s estimates in Open questions above are the only remaining soft spot, and they
  were validated as reasonable by the real run (14 cases cost ~$0.0082 total, nowhere near the cap).
