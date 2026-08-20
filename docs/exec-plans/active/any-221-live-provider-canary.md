# Execution Plan: ANY-221 11-Atom Live Provider Canary

## Status

- State: active
- Owner: agent
- Created: 2026-08-20
- Last updated: 2026-08-20
- Review date: 2026-08-20
- Next action: run the credentialed manual cycle (`OPENAI_API_KEY` + `dev-up` -> `live-canary` ->
  `dev-down`) to get the first real evidence report, then link its result in this doc's Progress
  log and in MVP-A1's own completion doc.
- Blocker: none for the CI-safe half of this ticket; the manual credentialed run still needs an
  operator with a real `OPENAI_API_KEY` to execute it.

## Goal

Prove all 11 generic atom prompts/contracts through a real, backend-selected LiteLLM/OpenAI
provider call (not the deterministic fake-provider path ANY-218/219/220 already prove), still with
no caller-chosen provider/model/prompt/retry/structured-output control, still ledger/schema
validated rather than wording-validated, bounded by an estimated-cost cap, and reported in a
privacy-safe evidence JSON. Runs manually or on a credentialed schedule; normal CI stays
credential-free.

Full design rationale (verified against real code before implementation) lives in
`plans/ANY-221.md` (gitignored, not part of this repo's history) and this file's Decision log.

## Scope

### In scope

- 11 new `_live_` config entries in `configs/kernel/products/kernel_demo/` (`action_configs.yaml`,
  `workflows.yaml`, `scenarios.yaml`, `product.yaml`), wired to the pre-existing, previously-unused
  `default_text_generation_v1` provider policy.
- `scripts/agent/atoms_proof.py`: additive `StepEvidence` fields (`latency_ms`, `input_tokens`,
  `output_tokens`, `total_tokens`, `estimated_cost`) populated from `provider_calls` rows already
  read by `_classify_ledger`.
- `scripts/agent/live_canary.py` (new): reuses `atoms_proof.py`'s HTTP/DB/evidence machinery to run
  the 11 live-sibling scenarios, with a cumulative `estimated_cost` cap (`LIVE001` abort code) that
  marks remaining cases failed instead of silently truncating the report.
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

### Out of scope

- Refactoring any frozen hot-path file (`config/loader.py`, `workflows/runner.py`,
  `actions/runner.py`, `StructuredLlmActionExecutor`, `handlers/run_workflow.py`, Session
  ownership) -- per ANY-24's execution constraints.
- A dedicated canary provider policy, a run-level physical-call aggregate cap (the fixed 11-case
  list x the existing per-action `max_physical_provider_calls_per_action: 4` cap already bounds the
  run to <=44 physical calls structurally), or a full fake-provider round-trip test for the new
  live scenario ids.
- Composite-workflow live coverage -- ticket scope is the 11 standalone scenarios only.
- Prompt benchmarking, semantic quality scoring, automatic model comparison, or exposing
  credentials/provider controls to clients (ticket non-goals).

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/exec-plans/active/any-220-atom-runtime-proof-cli.md` (the CLI/evidence machinery this
  ticket extends)

## Contracts touched

- API: none (drives existing `/v1/*` endpoints over HTTP, same as `atoms_proof.py`).
- DB: read-only ledger check, same 5 tables `atoms_proof.py` already reads; no schema change --
  `provider_calls`' `latency_ms`/`input_tokens`/`output_tokens`/`total_tokens`/`estimated_cost`
  columns already existed.
- Config: 11 new action_config/workflow/scenario entries + 11 new `product.yaml` scenario_ids, all
  additive; no existing entry mutated (regression-guarded by
  `test_live_canary_config.py`).
- Events: none produced; existing event types read and asserted against (same set
  `atoms_proof.py` already checks).
- Frontend: none.

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
- [ ] Manual credentialed run: `OPENAI_API_KEY=... dev-up -> live-canary -> dev-down`, must print
      `11/11`, exit 0, evidence JSON written to `.agent/live-canary/`.
- [ ] Link the first successful run's evidence in this file's Progress log and in MVP-A1's own
      completion doc.

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check`
- [ ] `export OPENAI_API_KEY=... && python scripts/agent/runner.py dev-up && python scripts/agent/runner.py live-canary && python scripts/agent/runner.py dev-down`
- [ ] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-20 | Reused `default_text_generation_v1` as-is; no dedicated canary provider policy | Already conservative (`max_physical_provider_calls_per_action: 4`, `timeout_seconds: 60`) and unused by any product before this ticket; add a dedicated policy later only if real runs show it's wrong. |
| 2026-08-20 | Parallel `_live_` entries in the same `kernel_demo` product config files, not a new product/config root | Mirrors exactly how the 11 fake atoms already live there; pure YAML, doesn't touch the frozen `config/loader.py`. |
| 2026-08-20 | New sibling script `scripts/agent/live_canary.py`, not a flag on `atoms_proof.py` | Keeps the deterministic gate's behavior/output byte-for-byte unchanged; imports `atoms_proof` for all shared HTTP/DB/evidence machinery. |
| 2026-08-20 | Cost cap lives in `live_canary.py`, not `ProviderGateway` | `ProviderGateway`/hot-path files are frozen per ANY-24's execution constraints; the fixed 11-case list already structurally bounds physical calls via the existing per-action cap, so no new gateway-level aggregate counter is needed either. |
| 2026-08-20 | `live_canary.py`'s CLI takes `--database-url-env ENV_VAR`, mirroring `atoms_proof.py`'s own fourteenth-round fix, not a `database_url` positional | `RuntimeIdentity.database_url` can embed a real `ANYTOOLAI_POSTGRES_PASSWORD` override; passing it via env (not argv) keeps it out of `ps`/process-listing output, exactly like `atoms_proof.py` and `runner.py`'s `atoms_proof()` already do. |
| 2026-08-20 | `live_canary.py` imports `atoms_proof.smoke` lazily (via `atoms_proof.smoke.*` attribute access inside functions), not `from atoms_proof import smoke` at module load time | `atoms_proof.py`'s own `smoke = load_smoke_module()` assignment only happens inside its guarded try/except; if that block fails, `atoms_proof.smoke` doesn't exist as an attribute, and an eager `from atoms_proof import smoke` would raise a raw `ImportError` before `main()` ever gets to print a clean `LIVE00x` code -- the same "run far enough to fail cleanly" contract `atoms_proof.py` and `kernel_demo_smoke.py` both already honor for their own guarded imports. |
| 2026-08-20 | `_atom_coverage_error(LIVE_ATOM_CASES)` reused directly (not `_coverage_gate_error`, which also requires a non-empty composite-case tuple) | This ticket has no composite-workflow live coverage (out of scope); `_coverage_gate_error` would need a real `composite_cases` argument, so the pure atom-only check is the correct-sized reuse. |
| 2026-08-20 | Fixed `test_config_loader.py`'s `test_loader_rejects_negative_workflow_step_retry_count` to look up `retry_extract_v1` by `workflow_id` instead of `workflows[-1]` | Appending the 11 live workflows to the end of `workflows.yaml` silently broke this test's positional-index assumption; looking up by id is correct regardless of future appends, not just a patch for this one addition. |
| 2026-08-20 | `.github/workflows/live-canary.yml` pins `actions/upload-artifact` to `v7.0.1`'s commit SHA (looked up via `gh api repos/actions/upload-artifact/git/refs/tags/v7.0.1`, not guessed) | Matches this repo's existing pinned-action convention (`actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv`); no prior `upload-artifact` usage existed anywhere in the repo to copy a pin from. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-20 | Verified `plans/ANY-221.md`'s pre-existing implementation plan against real code (3 parallel Explore passes), corrected 2 minor inaccuracies (a docstring-citation overclaim, a stale 4-job `backend.yml` count). Implemented config wiring (11 x 4 YAML entries) and `atoms_proof.py`'s `StepEvidence`/`_classify_ledger` extension; `validate-configs` passed. Committed (`624ed47`). | Continue with `live_canary.py` and the rest of the file list. |
| 2026-08-20 | Merged `feature/ANY-220` into the branch; fixed 4 regressions the merge + config additions surfaced (stale generated config-registry doc, a runtime-config test's hardcoded scenario_ids list, a positional-index test assumption broken by appending workflows, ledger fixtures missing the 5 new columns). `quick-check` green (813 tests). Committed (`3c8004a`). Implemented `scripts/agent/live_canary.py`, the `live-canary` runner command, the `docker-compose.yml` `OPENAI_API_KEY` passthrough, and all CI-safe tests (`test_live_canary_config.py`, `tests/test_live_canary.py`, 3 new `test_runner.py` cases). `quick-check` green (816 tests). Committed (`5454523`). Added `.github/workflows/live-canary.yml` and this exec-plan doc. | Run the manual credentialed cycle (`dev-up` -> `live-canary` -> `dev-down`) with a real `OPENAI_API_KEY`, confirm `11/11`, inspect the evidence JSON, then run `full-check` and link results here. |

## Open questions

- `default_text_generation_v1`'s existing caps (4 calls/action, 60s timeout) and the `$0.50`
  default cost cap are both estimates made without real gpt-4.1-mini latency/cost data on these 11
  prompts; revisit both after the first couple of manual runs (no plumbing change needed either
  way -- both are plain config/CLI values).

## Follow-up debt

- The first successful manual/CI `live-canary` run's evidence still needs to be linked here (this
  file's Progress log) and from MVP-A1's own completion doc, per the parent ticket's acceptance
  criterion ("a recent successful manual live-provider canary is linked").
