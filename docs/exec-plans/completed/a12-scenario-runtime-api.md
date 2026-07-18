# Execution Plan: A12 Scenario Runtime API

## Status

- State: completed
- Owner: agent
- Created: 2026-07-18
- Last updated: 2026-07-18
- Review date: 2026-07-18
- Next action: none; implementation, validation, and documentation alignment are complete.
- Blocker: none

## Goal

Expose the first user-facing runtime entrypoint through scenario sessions by adding safe start,
polling, and next-action API endpoints that create the scenario session before queuing workflow
execution and preserve session/job/artifact/event correlation.

## Scope

### In scope

- Scenario runtime API routes for start, get session, and next-action.
- Scenario runtime/session snapshot service and checkpoint resolution in `platform-core`.
- Session/job/artifact lookup helpers required by the new API.
- Worker-side scenario session status/checkpoint updates on claim, success, and failure.
- Focused API/core/worker tests and required documentation updates.
- True A12 vertical integration coverage from HTTP start through real worker execution and API polling.

### Out of scope

- Inline workflow execution in the API.
- `GET /v1/jobs/{id}` or broader job API work.
- Durable workflow-engine semantics, resumable workflows, or approval queues.
- Handoff, quota, email-capture, or paywall side effects from `next-action`.

## Relevant docs

- `docs/architecture/scenario-session-model.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/job-lifecycle.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/action-runner.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/exec-plans/completed/a10-sequential-workflow-runner.md`
- `docs/exec-plans/completed/a11-job-lifecycle-and-worker-integration.md`
- `docs/exec-plans/completed/workflow-started-scenario-correlation.md`

## Contracts touched

- API: `POST /v1/products/{product_id}/scenarios/{scenario_id}/start`, `GET /v1/scenario-sessions/{id}`, `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}`
- DB: existing `platform.scenario_sessions`, `platform.jobs`, `platform.action_runs`, `platform.provider_calls`, `platform.artifacts`, `platform.event_log`
- Config: existing product/frontend/scenario/workflow config lookups only; no new config schema
- Events: `scenario.started`, `scenario.checkpoint_reached`, `scenario.completed`, `scenario.failed`, `client.next_action_clicked`
- Frontend: session polling and next-action contract for CE/web callers

## Implementation steps

- [x] Add scenario runtime models, checkpoint resolution, session snapshot building, and session/job lookup helpers in `platform-core`.
- [x] Add the scenario runtime API router, request/response schemas, safe error handling, and route wiring in `platform-api`.
- [x] Update worker session status/checkpoint transitions for claim, success, and failure.
- [x] Add focused API/core/worker tests for start/get/next-action and session correlation behavior.
- [x] Add a true A12 vertical integration test from HTTP start through real worker/provider/artifact execution and API polling.
- [x] Update architecture docs and generated OpenAPI documentation.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_scenario_runtime.py -q --basetemp .pytest-tmp\\scenario-runtime-core`
- [x] `uv run python -m pytest apps/platform-api/tests/test_scenario_runtime.py -q --basetemp .pytest-tmp\\scenario-runtime-api`
- [x] `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -q --basetemp .pytest-tmp\\scenario-runtime-worker`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q --basetemp .pytest-tmp\\scenario-runtime-workflow-runner`
- [x] `uv run python -m pytest apps/platform-api/tests -q --basetemp .pytest-tmp\\scenario-runtime-api-all`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py -q --basetemp .pytest-tmp\\scenario-runtime-event-log`
- [x] `uv run python scripts/agent/runner.py validate-architecture`
- [x] `uv run python scripts/agent/runner.py validate-docs`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-18 | Keep A12 as queue-and-return instead of inline execution | A11 already established a DB-backed worker path, and the task explicitly asks for a stable CE polling response after session creation |
| 2026-07-18 | Keep checkpoint definitions code-owned in `platform-core` for A12 | Existing scenario config only exposes static `allowed_next_actions`; introducing a new config schema here would widen scope unnecessarily |
| 2026-07-18 | Make `next-action` validation-only with event logging and no product side effects | The task requires checkpoint/action validation but explicitly keeps handoff/quota/access-lite slices out of scope |
| 2026-07-18 | Add a real HTTP-to-worker vertical test instead of extending manual terminal-state helpers | The review gap was specifically missing proof that API-started execution preserves `scenario_session_id` through the real worker, ActionRunner, ProviderGateway, provider ledger, artifacts, and polling response |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-18 | Implemented the scenario runtime service, API router, worker session updates, focused tests, and architecture/OpenAPI docs | Add the missing vertical A12 integration test and sync the execution-plan status |
| 2026-07-18 | Added a true API start -> real worker execution -> polling test with explicit `scenario_session_id` assertions across `provider_calls`, `artifacts`, and related runtime rows/events | None; validation and documentation alignment are complete |

## Open questions

- None.

## Follow-up debt

- `GET /v1/jobs/{id}` and real CE-kit client wiring remain separate slices after A12.
