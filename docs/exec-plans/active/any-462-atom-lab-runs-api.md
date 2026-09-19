# ANY-462 Atom Lab Runs API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver atomic idempotent Atom Lab run admission plus protected durable run history over
the existing PostgreSQL → worker → ActionRunner → ProviderGateway path.

**Architecture:** A focused `AtomLabRunService` coordinates current catalog/contract validation and
the existing scenario runtime inside one transaction. A tenant/region admission row serializes
idempotency, daily quota and active-run checks; accepted run snapshots remain immutable while
history projects status, result and attempt counters from the existing runtime ledger.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-09-09-atom-lab-design.md` and AL04 in
`docs/exec-plans/active/atom-lab-v1.md`.

## Status

- State: active
- Phase: Implementation and required verification complete
- Owner: agent
- Last updated: 2026-09-18
- Review date: 2026-09-18
- Next action: Choose whether to keep, merge or publish `feature/ANY-462`.
- Blocker: none; an isolated local PostgreSQL container is available for the final gate.

## Global Constraints

- Work only on `feature/ANY-462`; preserve public runtime behavior and existing Atom Lab assets.
- Use TDD: every behavior test must be observed failing for the intended reason before production
  implementation.
- Auth precedes idempotency lookup. Same scoped key plus canonical request returns the original
  run; a different request returns `409 idempotency_conflict`.
- Accepted snapshot, session, job, stable guest identity and daily count commit atomically.
- Defaults are configurable: input JSON 256 KiB, prompt UTF-8 64 KiB, raw request 384 KiB,
  100 accepted starts per UTC day and one active run.
- Never hold the admission lock during provider execution. Pre-start failures consume no limit.
- No second execution ledger. Existing sessions/jobs/action runs/provider calls/artifacts remain
  authoritative; lab storage may keep immutable snapshot/admission fields and bounded diagnostics.
- Public endpoints must continue treating Atom Lab resources as not found. Errors/logs must never
  echo access code, full input, prompt, credentials or hidden reasoning.
- Run targeted tests after each task. Before completion run quick-check, full-check, real
  postgresql-check, validate-docs, validate-architecture and generated OpenAPI drift checks.

---

### Task 1: Durable admission and idempotency

**Files:**
- Create: `migrations/platform/versions/0015_atom_lab_run_admission.py`
- Create: `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/service.py`
- Create: `packages/backend/platform-core/tests/unit/test_atom_lab_run_admission.py`
- Modify: `packages/backend/platform-core/src/anytoolai_platform_core/storage/db.py`
- Modify: `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/models.py`
- Modify: `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/repository.py`

**Interfaces:**
- Produces `AtomLabRunAdmissionRequest`, `AtomLabRunAdmissionResult` and `AtomLabRunService.start()`.
- Produces repository methods for scoped idempotency lookup, serialized scope admission, stable
  `(created_at, run_id)` listing and atomic accepted-count bookkeeping.
- Later tasks consume a stored `AtomLabRunRecord` containing idempotency hash/key and guest ID.

- [x] Write failing unit tests for canonical JSON hashing, replay, conflict, active limit, daily
  rollover and transaction rollback; add a PostgreSQL race test using the repository's existing
  `postgresql` marker conventions.
- [x] Run the focused test module and confirm failures identify missing admission interfaces.
- [x] Add migration/table/model/repository state with a scoped unique idempotency constraint and a
  tenant/region lock row; avoid relying on process-local locks.
- [x] Implement the minimal service flow: lock scope, replay lookup, current validation callback,
  limits, guest/session/job/snapshot creation, count increment and return before provider execution.
- [x] Run focused SQLite tests and refactor only while green. The real PostgreSQL target remains a
  final verification concern because neither a test URL nor a Docker daemon is available locally.

### Task 2: Strict protected run admission API

**Files:**
- Create: `apps/platform-api/tests/test_atom_lab_runs.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/schemas.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/settings.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/routers/atom_lab.py`

**Interfaces:**
- Consumes `AtomLabRunService.start()` from Task 1.
- Produces `POST /v1/atom-lab/runs` with body
  `{atom_id,input,prompt,model_id,reasoning_effort,preset_ref?}` and response
  `{run_id,scenario_session_id,job_id,status}`.

- [x] Write failing API tests for auth-before-lookup, missing/oversized idempotency key, forbidden
  extra fields, malformed JSON, raw/input/prompt UTF-8 limits, model/effort validation, preset
  provenance, safe errors and one exact full-payload case for every A01–A11 workflow.
- [x] Run the new module and confirm failures are caused by the absent route/contracts.
- [x] Add strict Pydantic wire models and configurable positive settings using the documented
  defaults; keep nullable effort distinct from an omitted/invalid value.
- [x] Implement raw-body bounding and the protected route. Resolve atom → laboratory scenario on
  the server, validate current input schema/catalog/preset, and pass the server-only live token.
- [x] Map domain failures exactly to 401/404/409/413/422/429/503 Atom Lab envelopes and run the
  focused tests until green.

### Task 3: Protected stable run history

**Files:**
- Create: `apps/platform-api/tests/test_atom_lab_history.py`
- Modify: `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/models.py`
- Modify: `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/repository.py`
- Modify: `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/service.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/schemas.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/routers/atom_lab.py`

**Interfaces:**
- Produces `GET /v1/atom-lab/runs` → `{items,next_cursor}` ordered by
  `(created_at DESC, run_id DESC)` with default 20/max 100.
- Produces `GET /v1/atom-lab/runs/{run_id}` →
  `{run_id,status,snapshot,runtime_ids,result,diagnostics,created_at,started_at,finished_at}`.

- [x] Write failing list/detail tests for keyset stability, protected scope, all accepted statuses,
  nullable IDs/times, successful immutable result, failed diagnostics, historical model/contract
  drift and distinct semantic/transport/physical attempt counts.
- [x] Run the new test module and confirm failures identify absent history projection behavior.
- [x] Add scoped projection queries joining existing runtime rows without copying them into a
  second ledger. Return result only from a successful normalized structured-output artifact.
- [x] Add strict response models, bounded opaque cursors and protected list/detail routes.
- [x] Run focused API/storage tests and refactor only while green.

### Task 4: Worker diagnostics and vertical verification

**Files:**
- Modify: `apps/platform-worker/src/anytoolai_platform_worker/handlers/run_workflow.py`
- Modify: `apps/platform-worker/tests/test_atom_lab_execution.py`
- Modify: `apps/platform-api/tests/test_atom_lab_runs.py`
- Modify: `apps/platform-api/tests/test_atom_lab_history.py`
- Modify: `docs/exec-plans/active/atom-lab-v1.md`

**Interfaces:**
- Consumes Tasks 1–3 run records/history projection.
- Produces bounded Atom-Lab-only contract-failure diagnostics with explicit truncation and durable
  terminal visibility after worker reconciliation/restart.

- [x] Write failing worker/integration tests for final invalid output, provider failure,
  `worker_lease_lost`, success after validation retry, allowed transport retry and terminal replay.
- [x] Confirm each new test fails for missing diagnostics/projection behavior.
- [x] Persist the minimal bounded diagnostic projection from existing debug artifacts/runtime
  errors, never hidden reasoning or credentials; preserve current worker failure semantics.
- [x] Prove concurrent duplicate starts create one logical run/job while allowed retries create
  separate provider-call rows, and prove submitted input equals snapshot and ActionRunner input for
  all 11 atoms including omitted/null/false/zero shapes supported by their schemas.
- [x] Regenerate OpenAPI/contracts if drifted; run targeted tests, quick-check, real
  postgresql-check, full-check, validate-docs and validate-architecture. Record evidence and mark
  AL04 checkboxes/progress only after all required commands pass.

### Task 5: PR review follow-up

- [x] Preserve canonical terminal scenario-session precedence in Atom Lab status projection and
  keep stored results hidden when an independently expired session races with job success.
- [x] Isolate Atom Lab run-limit environment parsing from the shared request settings dependency;
  malformed Lab-only configuration now leaves unrelated routes unchanged and fails the run path
  with the safe `lab_unavailable` envelope.
- [x] Add and execute a real PostgreSQL concurrency regression proving distinct idempotency keys
  cannot exceed `active_limit=1` or increment the accepted counter twice.
- [x] Terminate every run-admission `DBAPIError` at the Atom Lab boundary with a safe 503 envelope
  and a parameter-free observability event; regress against secret prompt/input markers in both
  the response and captured logs.
- [x] Make active-run admission honor terminal scenario-session precedence so an expired session
  releases its slot even if its linked job remains `created`; cover the lifecycle race directly.
