# ANY-467 Atom Lab v1 acceptance evidence

## Status

- State: active
- Owner: mixed
- Created: 2026-09-24
- Last updated: 2026-09-24
- Review date: 2026-09-24
- Next action: run the credentialed Atom Lab live canary and record the privacy-safe evidence.
- Blocker: required live-provider and protected-surface credentials are unavailable in this
  environment.
- Branch: `feature/ANY-467`
- Automated implementation: complete
- Required live evidence: not executed; the current environment has no `OPENAI_API_KEY`,
  `ANYTOOLAI_LIVE_CANARY_TOKEN`, or `ANYTOOLAI_ATOM_LAB_ACCESS_CODE`
- PostgreSQL acceptance gate: passed against a disposable local PostgreSQL 16 instance

This record does not accept Atom Lab v1 while the required credentialed live gate is missing. Fake
adapters prove plumbing and retry accounting only; they are not provider evidence.

## Acceptance harness

ANY-467 extends the existing `scripts/agent/live_canary.py` harness. The production surface remains
the default and retains its existing 11-atom plus three-composite behavior. Setting
`ANYTOOLAI_LIVE_CANARY_SURFACE=atom-lab` switches the same harness to the protected Atom Lab API.
This is optional credentialed evidence and is not a new MVP-A1 required gate.

The Atom Lab mode:

1. reads the protected atom and model catalogs;
2. selects a compatible reasoning-capable GPT, or the compatible model explicitly named by
   `ANYTOOLAI_ATOM_LAB_MODEL_ID`;
3. submits non-smoke inputs for A01-A11 with each repository-owned live prompt;
4. verifies the accepted IDs, immutable snapshot, requested model/reasoning, validated result,
   idempotent replay, PostgreSQL ledger and existing retry caps;
5. repeats A01 for every reasoning effort confirmed by that model's catalog entry;
6. writes privacy-safe evidence under `.agent/live-canary/atom-lab/`.

The evidence contains run/session/job/action/artifact IDs where available, requested and
provider-confirmed model IDs, reasoning effort, completion time, input/result validity flags,
attempt/cost/token/latency counters, and pass/fail codes. It contains no prompt, submitted input,
generated result, access code, API key, database URL, or hidden reasoning.

Operator command after starting the normal API/PostgreSQL/worker stack with matching server-side
configuration:

```bash
ANYTOOLAI_LIVE_CANARY_SURFACE=atom-lab \
ANYTOOLAI_ATOM_LAB_ACCESS_CODE='<configured lab code>' \
OPENAI_API_KEY='<provider key>' \
ANYTOOLAI_LIVE_CANARY_TOKEN='<server live token>' \
python3 scripts/agent/runner.py live-canary
```

`ANYTOOLAI_ATOM_LAB_MODEL_ID` is optional. If it is omitted, the harness chooses a compatible
catalog model with confirmed reasoning efforts. The run fails closed if it cannot execute at least
one supported reasoning combination.

## Twelve-criterion matrix

| # | Evidence | Status |
|---|---|---|
| 1 | `apps/platform-api/tests/test_atom_lab_catalog.py::test_atom_lab_catalog_contains_all_eleven_atoms_in_stable_order`, `::test_every_atom_lab_example_passes_the_runtime_input_contracts`; live mode A01-A11 | Automated; live pending |
| 2 | `tests/e2e/atom-lab-browser/atom-lab.test.mjs`: all-eleven form round-trip, omission/null/empty/false/zero, nested controls; `tests/test_live_canary.py::test_atom_lab_cases_cover_all_eleven_atoms_with_non_smoke_inputs` | Automated |
| 3 | browser `prompt reset and example replacement are explicit dirty-state transitions`; schemas are rendered read-only by the protected journey tests | Automated |
| 4 | `apps/platform-worker/tests/test_atom_lab_execution.py::test_parallel_lab_runs_do_not_leak_settings_into_an_ordinary_job`, `::test_lab_null_reasoning_reaches_adapter_without_inheriting_policy_default`, retry assertions in `::test_lab_retry_success_keeps_separate_physical_calls_after_restart`; live reasoning cases | Automated; live pending |
| 5 | worker retry/ledger tests above and `apps/platform-api/tests/test_atom_lab_run_execution.py::test_http_worker_terminal_history_and_idempotent_replay`; the live mode reuses `atoms_proof._check_ledger` | Automated; live pending |
| 6 | `packages/backend/platform-core/tests/unit/test_model_catalog_storage.py` initial/TTL/manual/lease/failure tests; `apps/platform-api/tests/test_atom_lab_models_api.py`; browser catalog state tests | Automated |
| 7 | `apps/platform-api/tests/test_atom_lab_presets.py::test_create_read_list_version_and_export_preserves_immutable_payload`, `::test_new_version_is_append_only_and_rejects_stale_base`; PostgreSQL atomic version test; browser conflict/recovery journeys | Automated; PostgreSQL gate pending |
| 8 | `apps/platform-api/tests/test_atom_lab_history.py` lifecycle/snapshot/retry/failure coverage; browser running/crash-failed and restore journeys | Automated |
| 9 | `apps/platform-api/tests/test_atom_lab_run_execution.py::test_http_worker_terminal_history_and_idempotent_replay`; worker pending/running/terminal restart coverage; live replay in `_run_atom_lab_case` | Automated; live pending |
| 10 | preset export round-trip API test and protected browser export journey; evidence serializer omits payload/prompt/result/secrets | Automated |
| 11 | `apps/platform-api/tests/test_atom_lab_access.py` authentication and public session/result/artifact/client-event/handoff bypass tests | Automated |
| 12 | Chromium accessibility/focus/error journeys, dirty-navigation tests and readable result/JSON journeys in `tests/e2e/atom-lab-browser/` | Automated |

## Audit-specific matrix

- Form/submitted/snapshot/ActionRunner equality for non-smoke A01-A11:
  `apps/platform-api/tests/test_atom_lab_run_execution.py::test_submitted_payload_equals_snapshot_and_action_runner_input`,
  `apps/platform-worker/tests/test_atom_lab_execution.py::test_worker_passes_each_atom_lab_payload_unchanged_to_executor`,
  and the live A01-A11 matrix.
- Model/effort at the adapter: direct addressing, explicit-null behavior, retry stability and
  ordinary-job isolation are covered in `test_atom_lab_execution.py`.
- Crash/restart: durable pending snapshot, `worker_lease_lost` reconciliation for interrupted
  running jobs, and immutable terminal replay are covered in `test_atom_lab_execution.py`.
- Catalog: initial load, TTL, manual refresh, one PostgreSQL lease, expired-lease recovery and
  refresh without workflow jobs are covered by `test_model_catalog_storage.py` and
  `test_model_catalog_hook.py`.
- Preset/run dependencies and public bypasses are covered by `test_atom_lab_presets.py`,
  `test_atom_lab_runs.py` and `test_atom_lab_access.py`.
- Language is supplied only through the actual repository prompt and submitted contract fields;
  the harness adds no hidden language rule.

## Verification record

- 2026-09-24 final `python3 scripts/agent/runner.py quick-check`: 1906 passed, 480 deselected.
- 2026-09-24 focused live-canary/atoms-proof/runner tests: passed.
- 2026-09-24 focused worker retry and explicit-null reasoning tests: passed.
- 2026-09-24 `uv run python scripts/agent/runner.py postgresql-check`: passed against a disposable
  PostgreSQL 16 instance; the container, network, and test data were removed afterward.
- 2026-09-24 `validate-docs`, `validate-architecture`, `generate-docs --check`, and
  `git diff --check`: passed.
- 2026-09-24 `full-check`: backend passed (1896 passed, 480 deselected), frontend install/lint/
  typecheck and all 78 Atom Lab Chromium journeys passed. The aggregate remained red only in the
  unrelated `web-mirror` package because local Node 26 exposes no jsdom `window.localStorage`, the
  same environment incompatibility already recorded for AL07 and AL08; the supported Node 22 CI
  gate remains required.
- 2026-09-24 independent read-only review: no remaining Critical or Important findings after
  correcting real snapshot nesting, rejecting blank evidence IDs, requiring provider model/date,
  and making admission, polling, timeout, and replay ambiguity cost-closed.
- Credentialed Atom Lab live run: blocked because this environment has no real provider, server
  live-canary, or Atom Lab access credentials.

## Completion rule

Move this record to `docs/exec-plans/completed/` and mark AL09 complete only after a fresh
credentialed evidence JSON for this branch is inspected for privacy, committed or linked from a
durable repository-visible location, and every required repository gate is green. A missing secret,
skipped test or fake-provider pass is a blocker, not an alternative successful condition.
