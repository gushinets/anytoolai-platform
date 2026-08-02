# Handoff: PostgreSQL Required-Gate Coverage

## Outcome

The required backend PostgreSQL job now executes every collected `postgresql` test through one
canonical marker-driven command. The job identity `postgresql-quota-concurrency` was intentionally
preserved so existing required-check configuration continues to apply, even though its scope is now
all PostgreSQL production semantics.

The command fails with `PGTEST001` before pytest starts when
`ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset, so fixture-level skips cannot produce a
false-green PostgreSQL gate.

Pre-edit collection found 257 tests that were both `slow` and `postgresql`; no `slow`-only or
`postgresql`-only cases existed. The former workflow covered 56 and missed 201. The expanded gate
immediately found four stale quota-service tests, which are fixed without weakening assertions.

## Final marker/coverage matrix

Every row is selected by `-m "postgresql"`, requires
`ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`, and now runs in required job
`baseline-backend / postgresql-quota-concurrency`.

| Test file | Marker | Count | Environment / semantics | Before | After |
|---|---|---:|---|---:|---:|
| `platform-core/tests/unit/test_action_runner.py` | `slow and postgresql` | 13 | Action persistence/recovery | 13 | 13 |
| `platform-core/tests/unit/test_artifact_service.py` | `slow and postgresql` | 1 | Artifact rollback recovery | 1 | 1 |
| `platform-core/tests/unit/test_event_log.py` | `slow and postgresql` | 20 | Event persistence and migrations | 0 | 20 |
| `platform-core/tests/unit/test_handoffs.py` | `slow and postgresql` | 44 | Transactional handoff behavior | 0 | 44 |
| `platform-core/tests/unit/test_provider_gateway.py` | `slow and postgresql` | 19 | Provider ledger/event recovery | 0 | 19 |
| `platform-core/tests/unit/test_quota_service.py` | `slow and postgresql` | 6 | Quota persistence/recovery | 0 | 6 |
| `platform-core/tests/unit/test_runtime_storage.py` | `slow and postgresql` | 42 | Alembic, repositories, locking | 0 | 42 |
| `platform-core/tests/unit/test_scenario_runtime.py` | `slow and postgresql` | 31 | Idempotency and transactions | 0 | 31 |
| `platform-core/tests/unit/test_structured_output.py` | `slow and postgresql` | 6 | Structured artifact persistence | 6 | 6 |
| `platform-core/tests/unit/test_workflow_runner.py` | `slow and postgresql` | 20 | Workflow persistence/recovery | 20 | 20 |
| `platform-actions/tests/test_structured_llm_executor.py` | `slow and postgresql` | 8 | Structured action persistence | 8 | 8 |
| `platform-api/tests/test_handoffs_api.py` | `slow and postgresql` | 5 | Handoff API/worker transactions | 1 | 5 |
| `platform-api/tests/test_identity_quota_api.py` | `slow and postgresql` | 4 | Identity/quota API persistence | 0 | 4 |
| `platform-api/tests/test_migrate.py` (marked cases) | `slow and postgresql` | 2 | Real Alembic CLI execution | 0 | 2 |
| `platform-api/tests/test_quota_concurrency_postgresql.py` | `slow and postgresql` | 6 | Row locks and `ON CONFLICT` | 6 | 6 |
| `platform-api/tests/test_scenario_runtime_api.py` | `slow and postgresql` | 15 | Scenario API/worker integration | 1 | 15 |
| `platform-worker/tests/test_worker_boot.py` | `slow and postgresql` | 15 | Claim/execution/cancellation/recovery | 0 | 15 |
| **Total** |  | **257** |  | **56** | **257** |

`quick-check` and the baseline portion of `full-check` intentionally retain `-m "not slow"`.
PostgreSQL concurrency is not duplicated against SQLite or another required job. No new DB-free
behavior test was needed because no runtime code or marker classification changed; two fast harness
tests were added to keep the required PostgreSQL selection contract in baseline CI.

## Files changed

- `.github/workflows/backend.yml`
- `AGENTS.md`
- `scripts/agent/runner.py`
- `tests/test_runner.py`
- `packages/backend/platform-core/tests/unit/test_handoffs.py`
- `packages/backend/platform-core/tests/unit/test_quota_service.py`
- `docs/architecture/runtime-storage.md`
- `docs/exec-plans/completed/postgresql-required-gate-coverage.md`
- `docs/tasks/postgresql-required-gate-coverage.md`
- `docs/handoffs/postgresql-required-gate-coverage.md`

## Exact commands

Collection inventory:

```bash
uv run python -m pytest --collect-only -m "postgresql" \
  packages/backend/platform-core/tests \
  packages/backend/platform-actions/tests \
  apps/platform-api/tests \
  apps/platform-worker/tests \
  -q
```

Required workflow command:

```bash
uv run python scripts/agent/runner.py postgresql-check
```

The runner expands that to:

```bash
python -m pytest -m "postgresql" \
  packages/backend/platform-core/tests \
  packages/backend/platform-actions/tests \
  apps/platform-api/tests \
  apps/platform-worker/tests \
  -q
```

Baseline validation:

```bash
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py full-check
```

## PostgreSQL environment assumptions

- CI uses the `postgres:16` service and maintenance database `postgres`.
- `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is
  `postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres` in CI.
- The maintenance role can create/drop databases and terminate connections to disposable DBs.
- `tests/db_support.py` creates UUID-suffixed databases, applies Alembic, disposes engines, terminates
  remaining connections, and drops databases in `finally`.
- The GitHub Actions service container is the outer cleanup boundary if the process is forcibly
  canceled. Handoff tests now also clean each database at fixture teardown rather than `atexit`.

## Validation results

- Source inventory: 17 marked files; no markers outside the four configured roots.
- Marker symmetry: 257 `slow and postgresql`; zero `slow and not postgresql`; zero
  `postgresql and not slow`.
- Collection command: 257 selected.
- First expanded run: 4 stale quota-service contract failures found; all other tests passed.
- Targeted quota service after fix: 6 passed.
- Targeted handoffs after fixture fix: 44 passed in 2m14s; zero leaked DBs.
- Final exact `postgresql-check`: 257 passed in 12m20s.
- Maintenance database after final run: zero non-template databases.
- `tests/test_runner.py`: passed, including the marker/root/workflow regression guards.
- `quick-check`: passed; 211 baseline tests passed and 257 PostgreSQL tests were intentionally
  deselected by `-m "not slow"`.
- `full-check`: passed in 6m02s; repeated the 211/257 baseline result, passed all frontend
  typechecks/builds, and passed the 2-test freelancer product suite.
- Workflow syntax/contract: the workflow parsed successfully in `tests/test_runner.py`; `actionlint`
  was not installed locally.
- Documentation, generated-doc, and architecture validation passed through `full-check`.

## Remaining runtime and cost risks

- Local Windows PostgreSQL execution takes about 12 minutes; GitHub-hosted Ubuntu timing is not yet
  measured. Repeated Alembic setup is the dominant expected cost.
- Keep one required PostgreSQL job to avoid duplicate expense. Optimize fixture reuse only after CI
  duration data identifies a concrete bottleneck, and preserve per-test isolation while doing so.
- The historical job ID still mentions quota concurrency. Rename it only together with branch
  protection/status-check configuration so required coverage is never accidentally made optional.
