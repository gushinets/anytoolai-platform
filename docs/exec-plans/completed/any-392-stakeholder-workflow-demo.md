# ANY-392 Stakeholder Workflow Demo Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with strict red-green-refactor cycles. Do not add a separate frontend framework or demo-specific runtime concepts below `apps/platform-api`.

**Goal:** Deliver a Russian-language `/demo` page that securely starts and displays the three allowlisted live `kernel_demo` composite workflows.

**Architecture:** `platform-api` serves a same-origin semantic HTML/CSS/JavaScript page and owns a narrowly scoped demo start route. The route validates server-side secrets and input, serializes the PostgreSQL-backed daily/busy gate with a process-local lock, creates a fresh guest, and delegates execution to the existing `ScenarioRuntimeService`; polling and result retrieval reuse existing frontend-safe endpoints.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy, plain HTML/CSS/browser JavaScript, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-stakeholder-workflow-demo-design.md`

## Status

- State: completed
- Owner: agent
- Created: 2026-08-29
- Last updated: 2026-08-29
- Review date: 2026-08-29
- Next action: Operator smoke with real secrets after deployment.
- Blocker: None.

## Global constraints

- Only `analyze`, `evaluate`, and `write` may map to fixed live scenario IDs.
- Secrets remain server-side and comparisons use `hmac.compare_digest`.
- Source text is required after trimming and limited to 4,000 Unicode characters by the API.
- The gate accepts at most 50 runs per UTC day and one `created`/`running` demo job at a time.
- The access code remains only in current-tab JavaScript memory.
- Browser rendering uses `textContent`, never `innerHTML`, and reports only honest global progress.
- No migration, new frontend dependency, platform-core concept, prompt/config, or provider-policy change.

## Scope

### In scope

- Same-origin `/demo` page and static assets.
- Secure `POST /v1/demo/runs` orchestration route.
- PostgreSQL-backed daily/busy checks using existing runtime tables.
- Compose/deployment secret wiring and operating instructions.
- API, page, architecture, generated-contract, and frontend validation.

### Out of scope

- User accounts, history, billing, arbitrary scenarios, step-level progress, distributed locking, new database tables, or public deployment/TLS changes.

## Relevant docs

- `docs/superpowers/specs/2026-08-27-stakeholder-workflow-demo-design.md`
- `docs/product-specs/mvp-a2-client-surfaces.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/quota-model.md`

## Contracts touched

- API: add `GET /demo`, asset GET routes, and `POST /v1/demo/runs`; reuse scenario-session and result GET routes.
- DB: read existing `platform.scenario_sessions` and `platform.jobs`; existing services create guest/session/job rows.
- Config: no definition changes; read `ANYTOOLAI_DEMO_ACCESS_CODE` and `ANYTOOLAI_LIVE_CANARY_TOKEN` from the API environment.
- Events: existing guest/scenario services emit canonical events; no demo event type.
- Frontend: plain same-origin HTML/CSS/JS, Russian copy, keyboard/focus/reduced-motion support.

## File structure

- Create `apps/platform-api/src/anytoolai_platform_api/routers/demo.py`: fixed workflow definitions, access/input validation, daily/busy query, guest/session orchestration, and page/assets.
- Create `apps/platform-api/src/anytoolai_platform_api/static/demo/index.html`: semantic page structure and accessible state regions.
- Create `apps/platform-api/src/anytoolai_platform_api/static/demo/demo.css`: payments-portal-inspired responsive glass presentation.
- Create `apps/platform-api/src/anytoolai_platform_api/static/demo/demo.js`: current-tab access state, start/poll/result flow, safe rendering, and Russian errors.
- Modify `apps/platform-api/src/anytoolai_platform_api/main.py`: register the demo router and allow the demo access header through CORS.
- Modify `apps/platform-api/src/anytoolai_platform_api/schemas.py`: strict demo request model.
- Create `apps/platform-api/tests/test_demo_api.py`: access, validation, mapping, limits, busy state, and runtime delegation.
- Create `apps/platform-api/tests/test_demo_page.py`: page/assets, accessibility hooks, and executable browser-source safety contracts.
- Modify `infra/compose/docker-compose.yml`, `infra/compose/.env.example`, `infra/deployment/README.md`: fail-closed configuration and one-replica/HTTPS operating contract.
- Update generated API documentation through the repository generator if drift validation requires it.

## Implementation tasks

### Task 1: Page and static asset contract

- [x] Write `test_demo_page.py` tests that request `/demo`, `/demo/demo.css`, and `/demo/demo.js`; assert UTF-8 Russian landmarks, labelled controls, status live region, technical `<details>`, character limit, and correct content types.
- [x] Add source-safety tests that fail if the JavaScript uses `innerHTML`, `localStorage`, or `sessionStorage`, and assert the polling/result endpoint templates are present.
- [x] Run the page tests and confirm they fail because the routes do not exist.
- [x] Add the minimal router GET routes, semantic HTML, CSS, and JS assets to satisfy the contract.
- [x] Run the page tests and keep them green while completing responsive/focus/reduced-motion styling.

### Task 2: Demo request validation and secure access

- [x] Write API tests for missing/wrong access codes, missing server configuration, unknown demo IDs, blank text, text over 4,000 characters, and forbidden extra fields; assert stable safe errors and zero runtime rows.
- [x] Run the focused tests and confirm the expected failures.
- [x] Add `DemoRunRequest` with forbidden extras and route-owned semantic validation so required demo failures use `demo_input_invalid`.
- [x] Add constant-time access-code validation and fail-closed live-token/config handling without logging or returning secrets.
- [x] Run the focused tests to green.

### Task 3: Gate and runtime delegation

- [x] Write tests proving each public key maps to the exact scenario and fixed input, creates a fresh guest, injects `frontend_id="web_mirror"` and the server live token, and returns the standard start response.
- [x] Write database-backed tests proving an active allowlisted demo job returns `demo_busy`, 50 accepted UTC-day sessions return `demo_daily_limit_exhausted`, unrelated frontends/scenarios do not count, and rejected starts create no guest/session.
- [x] Run the focused tests and confirm each behavior fails for the missing implementation.
- [x] Implement a module-level process lock, scoped SQLAlchemy count/existence queries, fresh guest creation, existing service delegation, and stable PlatformError mapping in one transaction.
- [x] Run the focused tests to green, then refactor duplicated service construction only where the resulting boundary stays explicit.

### Task 4: Browser state machine and rendering

- [x] Extend page tests around the stable DOM hooks needed for locked, ready, running, reconnecting, terminal error, result, raw JSON, technical proof, and rerun states.
- [x] Run tests and confirm missing hooks/behavior fail.
- [x] Implement access unlock, editable examples, character counter, duplicate-submit prevention, two-second polling with a 90-second deadline, transient reconnect messaging, terminal status handling, safe recursive result rendering, JSON fallback, and rerun behavior.
- [x] Run page and executable state-machine tests to green; local browser surface was unavailable, so viewport inspection remains an operator smoke item.

### Task 5: Deployment and generated contracts

- [x] Add tests or existing validation coverage for `ANYTOOLAI_DEMO_ACCESS_CODE` propagation and documented fail-closed defaults where executable behavior exists.
- [x] Wire `ANYTOOLAI_DEMO_ACCESS_CODE` into `platform-api`, add it with live/provider secrets to `.env.example`, and document one API replica, HTTPS, secret placement, verification, and the multi-replica locking ceiling.
- [x] Generate/check OpenAPI and repository docs, accepting only expected ANY-392 drift.

### Task 6: Verification and handoff

- [x] Run focused demo API/page tests.
- [x] Run `python scripts/agent/runner.py quick-check` (`974 passed, 397 deselected`).
- [x] Run `python scripts/agent/runner.py frontend-check` (typecheck, 313 tests including six demo state tests, generated contract check, and builds passed).
- [x] Run `python scripts/agent/runner.py validate-docs` and `python scripts/agent/runner.py generate-docs --check`.
- [x] Review `git diff` against every success criterion and scan for secrets, unsafe DOM writes, storage use, fake progress, and unrelated changes.
- [x] Update this plan to completed with exact verification evidence and remaining manual Compose/TLS smoke requirements.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-29 | Serve the demo from `platform-api` with plain assets. | Matches the approved spec and avoids a second deployment/build pipeline. |
| 2026-08-29 | Reuse the payments portal's visual language, not its React implementation. | Preserves the requested appearance without importing another application's dependencies. |
| 2026-08-29 | Execute inline in the existing clean `ANY-392` checkout. | The user explicitly selected this branch; no subagent workflow is permitted in this session. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-29 | Linear ticket, approved spec, architecture, current API, runtime repositories, deployment, and payments-portal design tokens inspected. | Run doctor/baseline, then Task 1 RED. |
| 2026-08-29 | Implemented same-origin page, allowlisted API orchestration, deployment wiring, generated contracts, SQLite and PostgreSQL coverage, and executable browser state tests. Review follow-ups fixed Unicode-safe comparison, deadline-aware aborts covering response bodies, permanent/transient polling classification, access-denied recovery, result/editor state isolation, workflow-card keyboard focus, and the Unicode code-point input limit. | Operator smoke with production PostgreSQL, worker/provider credentials, TLS, and a real browser. |

## Open questions

- None. The approved repository specification controls behavior; public TLS/DNS remains operator-owned.

## Follow-up debt

- Replace the process-local lock with a PostgreSQL advisory lock only if production deploys more than one `platform-api` replica.
- Complete a real-provider Compose/TLS smoke after deployment secrets and public browser access are available.
