# Stakeholder Workflow Demo Design

**Date:** 2026-08-27

**Status:** Approved in chat; awaiting written-spec review

## Purpose

Provide a small, publicly reachable Russian-language page that lets an investor, marketer, or
other invited stakeholder independently prove that the three existing live composite
`kernel_demo` workflows execute end to end through the real AnytoolAI runtime and OpenAI provider.

The page is a stakeholder proof surface, not a new product UI. It must demonstrate real execution
without exposing provider credentials, the live-canary token, prompts, model selection, raw
provider output, or internal traces.

## Success Criteria

- An invited user opens `/demo` over HTTPS, enters a shared access code, chooses one of three
  workflows, edits a prepared Russian example, and starts a real run.
- The browser shows an honest global running state, then the frontend-safe final result returned by
  the existing runtime APIs.
- The completed view exposes `scenario_session_id`, `job_id`, `result_artifact_id`, and
  `workflow_id` in a collapsed technical-proof section.
- The server permits only the three explicitly allowlisted live composite scenarios.
- The server accepts at most 50 demo starts per UTC day and rejects a new start while another demo
  job is `created` or `running`.
- Secrets remain server-side, input is bounded, and the page contains no fake per-step progress.
- The existing production Compose stack can host the page with one `platform-api` replica and the
  existing `platform-worker`; no separate frontend deployment is required.

## Non-Goals

- User accounts, invitations, password reset, billing, or per-user history.
- A general workflow builder, arbitrary scenario execution, or provider/model controls.
- Changing prompts, action configs, workflow definitions, output schemas, or the Provider Gateway.
- Exposing intermediate artifacts, action runs, provider calls, costs, logs, or traces.
- Adding a new database table, extending the lifetime quota engine, or supporting multiple API
  replicas for the demo gate.
- Pretending to know which workflow step is currently running. The current frontend-safe session
  snapshot exposes only overall session status.
- A separate SPA, frontend framework, JavaScript build pipeline, or new dependency.

## Architecture

The stakeholder demo lives inside `apps/platform-api` and is served from the same origin as the
existing API:

```text
Browser /demo
    -> POST /v1/demo/runs (shared code + workflow key + bounded source text)
    -> server-side allowlist and demo gate
    -> fresh guest identity
    -> existing ScenarioRuntimeService.start_session(..., frontend_id="web_mirror",
       live_canary_token=<server environment>)
    -> existing PostgreSQL job queue
    -> existing platform-worker -> ProviderGateway -> OpenAI
    -> GET /v1/scenario-sessions/{id}
    -> GET /v1/results/{artifact_id}
    -> rendered frontend-safe result
```

`platform-api` remains the composition root. `platform-core`, `platform-actions`, provider
policies, and kernel workflow configuration do not gain demo-specific concepts.

The implementation reuses the already enabled `web_mirror` frontend ID. The three live scenarios
remain `internal_only`; the browser never calls their public start route and never receives
`ANYTOOLAI_LIVE_CANARY_TOKEN`.

## Demo Workflows

The public request uses a short stable demo key. The server maps it to a fixed scenario ID and
constructs the complete runtime input. The browser cannot submit a scenario ID or arbitrary JSON.

| Demo key | Russian title | Existing scenario | Visible chain | Server-supplied input |
| --- | --- | --- | --- | --- |
| `analyze` | Анализ и уточнение | `kernel_demo.composite_analyze_and_clarify_live_smoke_v1` | Извлечение данных → поиск проблем → уточняющие вопросы → итоговый отчёт | Fixed `fields` for deadline, budget, and deliverables; `strict: false` |
| `evaluate` | Оценка соответствия | `kernel_demo.composite_evaluate_match_live_smoke_v1` | Сравнение и классификация → оценка по критериям → итоговая многомерная оценка | Only `source_text`; workflow literals remain authoritative |
| `write` | Подготовка убедительного ответа | `kernel_demo.composite_shape_and_write_live_smoke_v1` | Выбор аргумента → варианты улучшения → убедительный текст → готовый ответ | Only `source_text`; workflow literals remain authoritative |

Each card starts with a useful Russian example. The textarea is editable, required after trimming,
and limited to 4,000 Unicode characters. The API, not only the browser, enforces the limit.

## HTTP Surface

### `GET /demo`

Returns the UTF-8 HTML page. Static CSS and JavaScript are package assets served by
`platform-api`. Loading the page does not require the shared code and does not disclose whether
the server secrets are configured.

### `POST /v1/demo/runs`

Request header:

```text
X-Demo-Access-Code: <shared code>
```

Request body:

```json
{
  "demo_id": "analyze",
  "source_text": "Клиенту нужен первый релиз как можно скорее..."
}
```

Successful response reuses the frontend-safe start shape:

```json
{
  "scenario_session_id": "scenario_session_...",
  "job_id": "job_...",
  "status": "started",
  "allowed_next_actions": [],
  "result_artifact_id": null
}
```

The browser then uses the existing `GET /v1/scenario-sessions/{scenario_session_id}` polling
contract and, after completion, `GET /v1/results/{result_artifact_id}`. No demo-specific polling or
result endpoint is added.

Stable demo errors:

- `401 demo_access_denied` for a missing or incorrect shared code;
- `409 demo_busy` while an allowlisted `web_mirror` job is `created` or `running`;
- `422 demo_input_invalid` for an unknown demo key, blank input, or input over 4,000 characters;
- `429 demo_daily_limit_exhausted` after 50 accepted starts since 00:00 UTC;
- `503 demo_unavailable` when required server configuration or runtime storage is unavailable.

The API returns only safe error messages and a request ID. It never echoes either secret.

## Access and Secret Handling

The operator configures three secrets outside version control:

- `ANYTOOLAI_DEMO_ACCESS_CODE` on `platform-api`;
- `ANYTOOLAI_LIVE_CANARY_TOKEN` on `platform-api`;
- `OPENAI_API_KEY` on `platform-worker`.

`POST /v1/demo/runs` compares the supplied access code with
`ANYTOOLAI_DEMO_ACCESS_CODE` using `hmac.compare_digest`. Missing or blank server values fail
closed with `demo_unavailable`. The request-context middleware does not log headers or bodies, and
the demo code must not be added to log fields or error details.

The page keeps the access code only in JavaScript memory for the current tab. It is not placed in
a URL, cookie, local storage, session storage, source file, or returned response. Production access
requires HTTPS at the deployment boundary.

## Daily Limit and Single-Run Gate

The existing quota policy is intentionally unchanged: it supports only the `lifetime` period and
protects normal `kernel_demo` guest journeys. Each accepted demo start creates a fresh server-side
guest identity so the existing per-guest lifetime quota remains valid and auditable.

Before creating that guest, the demo router queries existing `scenario_sessions` and `jobs`:

- daily usage is the count of sessions created since 00:00 UTC with product `kernel_demo`, frontend
  `web_mirror`, and one of the three allowlisted scenario IDs;
- the busy state is the existence of a linked job with status `created` or `running` in that same
  scope.

A process-local lock serializes the check-and-start section. This is correct for the production
Compose default of one `platform-api` replica and remains durable across restarts because accepted
runs are counted from PostgreSQL. The known ceiling is multiple API replicas; if that deployment
becomes real, replace the process lock with a PostgreSQL advisory lock. Do not add distributed
coordination pre-emptively.

Only successfully created scenario sessions count toward 50. Invalid access codes, invalid input,
busy responses, and failed pre-start validation do not consume the demo limit. A workflow that is
accepted and later fails does consume one run because it may already have incurred provider cost.

## Page Experience

The page uses semantic HTML, plain CSS, and browser-native JavaScript. All visible copy is Russian.

1. Header: `AnytoolAI — демонстрация рабочих AI-цепочек` and a short statement that the page runs
   real backend workflows.
2. Access panel: shared-code password field and `Открыть демо` button.
3. Workflow selector: three cards showing purpose, fixed chain diagram, and expected output type.
4. Input panel: prepared editable text, character counter, `Запустить цепочку` button.
5. Running panel: spinner, elapsed time, selected chain, and `Выполняется на сервере`. Individual
   steps are not animated as completed because no step-level client contract exists.
6. Result panel: a readable Russian-labelled rendering of the returned JSON plus a `Показать JSON`
   fallback. Unknown future output fields remain visible in the JSON view.
7. Technical proof: collapsed `<details>` containing the real session, job, artifact, workflow,
   schema, version, and creation timestamp values returned by existing frontend-safe APIs.

The page disables duplicate submission in the current tab, preserves the edited input after a
recoverable error, and offers `Запустить ещё раз` after a terminal result. It is responsive down to
360 CSS pixels, fully usable by keyboard, has visible focus styles, labels every control, and
respects `prefers-reduced-motion`.

## State and Error Behaviour

- Poll every two seconds using the existing session endpoint.
- Stop after 90 seconds and show a timeout message with the technical session ID; the backend job is
  not canceled.
- Treat `completed` with a result artifact as success.
- Treat `failed` and `expired` as terminal safe failures.
- If polling temporarily fails, retry within the same 90-second window and show a reconnecting
  message; do not create another run.
- Render server-provided content with `textContent`, never `innerHTML`.
- Show actionable Russian messages for access denied, busy, daily limit, invalid input, timeout,
  and generic safe server failures.

## Files and Ownership

Expected implementation scope:

- `apps/platform-api/src/anytoolai_platform_api/routers/demo.py` — page/static responses, access
  validation, allowlist, daily/busy queries, guest creation, and delegated runtime start;
- `apps/platform-api/src/anytoolai_platform_api/static/demo/index.html` — semantic Russian page;
- `apps/platform-api/src/anytoolai_platform_api/static/demo/demo.css` — responsive presentation;
- `apps/platform-api/src/anytoolai_platform_api/static/demo/demo.js` — access, submission,
  polling, safe rendering, and UI states;
- `apps/platform-api/src/anytoolai_platform_api/main.py` — include the demo router;
- `apps/platform-api/src/anytoolai_platform_api/schemas.py` — strict demo request model;
- `apps/platform-api/tests/test_demo_api.py` — API security, allowlist, limits, concurrency gate,
  and delegation coverage;
- `apps/platform-api/tests/test_demo_page.py` — page/assets and required accessible-state hooks;
- `infra/compose/docker-compose.yml` and `infra/compose/.env.example` — pass and document the demo
  access code while preserving fail-closed defaults;
- `infra/deployment/README.md` — document one-replica demo deployment, HTTPS requirement, secrets,
  and verification steps.

No migration, platform-core change, workflow config change, or frontend dependency is expected.

## Verification

- API tests prove wrong/missing access codes cannot start work, only the three demo keys map to the
  expected scenarios and fixed inputs, 4,000-character validation is server-owned, busy and daily
  limits reject before guest/session creation, and the live token is injected only server-side.
- Page tests prove `/demo` and assets load, required Russian labels exist, form controls are
  labelled, and JavaScript does not use `innerHTML`, local storage, or session storage.
- Existing `ScenarioRuntimeService`, result API, architecture, and configuration tests remain
  unchanged and green.
- Run `python scripts/agent/runner.py quick-check` and
  `python scripts/agent/runner.py frontend-check`.
- Run a manual Compose smoke with configured secrets: open `/demo`, complete one workflow, verify
  the rendered result and technical IDs, then verify a wrong code is rejected without a new
  scenario-session row.

## Deployment Contract

The repository supplies the application surface and Compose environment wiring. The operator owns
the public hostname, TLS termination, DNS, firewall, secret storage, OpenAI account budget, and
rotation of the shared code. The demo is considered independently accessible only when `/demo` is
reachable through an HTTPS URL outside the operator's local network and a stakeholder can complete
a real run using the separately shared code.
