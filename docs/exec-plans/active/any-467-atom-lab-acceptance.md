# ANY-467 Atom Lab v1 acceptance evidence

## Status

- State: active
- Owner: mixed
- Created: 2026-09-24
- Last updated: 2026-09-25
- Review date: 2026-09-24
- Next action: run the credentialed Atom Lab live canary and record the privacy-safe evidence.
- Blocker: required live-provider and protected-surface credentials are unavailable in this
  environment.
- Branch: `feature/ANY-467`
- Automated implementation: complete
- Required live evidence: not executed; no configured live stack and matching
  `ANYTOOLAI_ATOM_LAB_ACCESS_CODE` are available in the current environment
- PostgreSQL acceptance gate: passed against a disposable local PostgreSQL 16 instance

This record does not accept Atom Lab v1 while the required credentialed live gate is missing. Fake
adapters prove plumbing and retry accounting only; they are not provider evidence.

## 2026-09-25 review remediation plan

- [x] Put the 11 non-smoke acceptance inputs in one repository fixture, drive that fixture through
  the real browser Form-mode submission path, and reuse it at the HTTP/snapshot/ActionRunner
  boundary.
- [x] Parse the protected `/v1/atom-lab/atoms` response as its declared JSON array while retaining
  the separate `/models` envelope contract.
- [x] Validate each successful live result against the catalog's repository-owned output schema
  and the configured semantic output validator before setting `result_valid=true`.
- [x] Split runner prerequisites by surface so production retains its API-key/token checks while
  the Atom Lab client requires only its access code and database/API connectivity.
- [x] Treat terminal `worker_lease_lost` with no committed provider calls as unknown cost and abort
  the remaining paid matrix.
- [x] Verify every physical provider-call ledger row kept the requested direct model and reasoning
  effort across retries, and accept only an exact or dated provider-confirmed version of that model.
- [x] Run focused Python and Node suites, canonical quick-check, and documentation/architecture
  checks; leave the credentialed-live blocker unresolved until the configured stack is available.

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

First start the normal API/PostgreSQL/worker stack. `OPENAI_API_KEY` belongs to the worker and the
configured `ANYTOOLAI_ATOM_LAB_ACCESS_CODE` belongs to platform-api; neither the provider key nor
the production-only `ANYTOOLAI_LIVE_CANARY_TOKEN` is a Lab-client prerequisite. From an operator
shell that can reach that stack and its PostgreSQL ledger, run:

```bash
ANYTOOLAI_LIVE_CANARY_SURFACE=atom-lab \
ANYTOOLAI_ATOM_LAB_ACCESS_CODE='<configured lab code>' \
python3 scripts/agent/runner.py live-canary
```

`ANYTOOLAI_ATOM_LAB_MODEL_ID` is optional. If it is omitted, the harness chooses a compatible
catalog model with confirmed reasoning efforts. The run fails closed if it cannot execute at least
one supported reasoning combination.

## Twelve-criterion matrix

| # | Evidence | Status |
|---|---|---|
| 1 | `apps/platform-api/tests/test_atom_lab_catalog.py::test_atom_lab_catalog_contains_all_eleven_atoms_in_stable_order`, `::test_every_atom_lab_example_passes_the_runtime_input_contracts`; live mode A01-A11 | Automated; live pending |
| 2 | shared `tests/fixtures/atom_lab_acceptance_cases.json`; browser Form-mode POST coverage in `atom-lab.test.mjs`; HTTP/snapshot/ActionRunner bridge in `test_atom_lab_run_execution.py`; live matrix fixture validation in `test_live_canary.py` | Automated |
| 3 | browser `prompt reset and example replacement are explicit dirty-state transitions`; schemas are rendered read-only by the protected journey tests | Automated |
| 4 | adapter isolation/null/retry tests in `test_atom_lab_execution.py`; live ledger checks require direct addressing and the requested model/effort on every physical attempt, plus exact/dated provider confirmation | Automated; live pending |
| 5 | worker retry/ledger tests; HTTP terminal/replay test; live result validation against catalog output schema and configured semantic cross-validator before `result_valid=true` | Automated; live pending |
| 6 | `packages/backend/platform-core/tests/unit/test_model_catalog_storage.py` initial/TTL/manual/lease/failure tests; `apps/platform-api/tests/test_atom_lab_models_api.py`; browser catalog state tests | Automated |
| 7 | `apps/platform-api/tests/test_atom_lab_presets.py::test_create_read_list_version_and_export_preserves_immutable_payload`, `::test_new_version_is_append_only_and_rejects_stale_base`; PostgreSQL atomic version test; browser conflict/recovery journeys | Automated; PostgreSQL gate passed |
| 8 | `apps/platform-api/tests/test_atom_lab_history.py` lifecycle/snapshot/retry/failure coverage; browser running/crash-failed and restore journeys | Automated |
| 9 | `apps/platform-api/tests/test_atom_lab_run_execution.py::test_http_worker_terminal_history_and_idempotent_replay`; worker pending/running/terminal restart coverage; live replay in `_run_atom_lab_case` | Automated; live pending |
| 10 | preset export round-trip API test and protected browser export journey; evidence serializer omits payload/prompt/result/secrets | Automated |
| 11 | `apps/platform-api/tests/test_atom_lab_access.py` authentication and public session/result/artifact/client-event/handoff bypass tests | Automated |
| 12 | Chromium accessibility/focus/error journeys, dirty-navigation tests and readable result/JSON journeys in `tests/e2e/atom-lab-browser/` | Automated |

## Audit-specific matrix

- Form/submitted/snapshot/ActionRunner equality for non-smoke A01-A11 uses one shared fixture in
  `atom-lab.test.mjs::all eleven non-smoke Form-mode drafts emit the shared acceptance POST payloads`
  and `test_atom_lab_run_execution.py::test_browser_acceptance_payload_equals_snapshot_and_action_runner_input`;
  the live canary consumes that same fixture.
- Model/effort at the adapter: direct addressing, explicit-null behavior, retry stability and
  ordinary-job isolation are covered in `test_atom_lab_execution.py`; the live canary additionally
  checks `gateway_model`, `metadata.model_addressing`, and `metadata.reasoning_effort` on every
  physical provider-call row and constrains provider confirmation to an exact or dated model.
- Crash/restart: durable pending snapshot and reconciliation remain covered in
  `test_atom_lab_execution.py`; canary regressions treat `worker_lease_lost` with an empty committed
  ledger as unknown spend and prove that every later paid case is skipped.
- Catalog: initial load, TTL, manual refresh, one PostgreSQL lease, expired-lease recovery and
  refresh without workflow jobs are covered by `test_model_catalog_storage.py` and
  `test_model_catalog_hook.py`.
- Preset/run dependencies and public bypasses are covered by `test_atom_lab_presets.py`,
  `test_atom_lab_runs.py` and `test_atom_lab_access.py`.
- Language is supplied only through the actual repository prompt and submitted contract fields;
  the harness adds no hidden language rule.

## Verification record

- 2026-09-25 final `python3 scripts/agent/runner.py quick-check`: 1929 passed, 480 deselected.
- 2026-09-25 Atom Lab Node unit suite: 52 passed; ESLint passed; Chromium: 78 passed.
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
- Credentialed Atom Lab live run: blocked because this environment has no configured live stack
  and matching Atom Lab access credential.

## Completion rule

Move this record to `docs/exec-plans/completed/` and mark AL09 complete only after a fresh
credentialed evidence JSON for this branch is inspected for privacy, committed or linked from a
durable repository-visible location, and every required repository gate is green. A missing secret,
skipped test or fake-provider pass is a blocker, not an alternative successful condition.
