# Frontend Boundaries

Frontends are thin delivery surfaces.

They may:

- collect input;
- create guest identity through backend APIs;
- store the opaque backend-created guest id locally;
- fetch runtime config;
- call approved scenario APIs;
- show job progress;
- fetch scenario session state;
- render artifacts;
- display backend-provided next actions;
- create backend-owned handoffs.
- open backend-owned handoff consent pages;
- capture email for quota/paywall flows;
- track client events.

They must not:

- store system prompts;
- choose provider/model;
- invent workflow steps;
- bypass quota;
- decide quota state authoritatively;
- call LLM providers directly;
- own authoritative scenario state.

Shared `ce-kit` must provide reusable API/job/quota/handoff helpers so MVP-B Chrome Extensions do not copy that code.
After A13, only `createGuestIdentity()` is wired as a real CE-kit helper: it creates an opaque
backend guest id and may store it locally. Full CE-kit API integration for `getQuota()` and
`startScenario()` is deferred to A16.

Required `ce-kit` capabilities:

- `createGuestIdentity()`
- `getRuntimeConfig()`
- `startScenario()`
- `getScenarioSession()`
- `nextAction()`
- `pollJob()`
- `getArtifact()`
- `createHandoff()`
- `openHandoffConsent()`
- `captureEmail()`
- `trackClientEvent()`
- `renderQuotaState()`
- `renderJobStatus()`
- `renderError()`

A13 status:

- backend guest identity and quota enforcement are implemented;
- CE local guest-id persistence is the only implemented CE-kit integration and is provided through
  `createGuestIdentity()`;
- `startScenario()` and `getQuota()` remain A13 demo/deferred helpers;
- A16 owns the central `PlatformApiClient`, real HTTP start/quota calls, guest-id propagation,
  typed `429 quota_exhausted` handling, and CE integration tests.

## A12/A13 public scenario runtime contract

The A12/A13 public runtime surface is:

- `POST /v1/identity/guest`
- `GET /v1/products/{product_id}/quota?guest_id={guest_id}`
- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start`
- `GET /v1/scenario-sessions/{id}`
- `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}`

`startScenario()` request body:

```json
{
  "frontend_id": "kernel_demo_ce",
  "input": {
    "source_text": "deadline budget deliverables"
  },
  "guest_id": "guest_optional",
  "user_id": "user_optional",
  "source_frontend_instance_id": "instance_optional"
}
```

For products with `quota_policy_ref`, `guest_id` is required and must be an opaque id created by
`POST /v1/identity/guest`.

`startScenario()` returns a stable queue-and-return payload:

```json
{
  "scenario_session_id": "scenario_session_123",
  "job_id": "job_123",
  "status": "started",
  "allowed_next_actions": [],
  "result_artifact_id": null
}
```

`getScenarioSession()` returns the frontend-safe polling snapshot:

```json
{
  "scenario_session_id": "scenario_session_123",
  "job_id": "job_123",
  "status": "completed",
  "current_checkpoint_id": "result_ready",
  "allowed_next_actions": ["copy_result", "create_handoff"],
  "result_artifact_id": "artifact_123"
}
```

`nextAction()` request body:

```json
{
  "checkpoint_id": "result_ready"
}
```

The frontend must poll `getScenarioSession()` for runtime progress in A12. `job_id` is returned for
correlation and future expansion, but job polling is not the primary public runtime contract for
this slice.

Safe API behavior:

- `404` for unknown scenario, unknown session, or unknown guest identity;
- `409` for stale checkpoints, non-actionable checkpoints, or disallowed next actions;
- `422` for invalid frontend selection, non-object scenario input, or missing guest identity;
- `429` with `quota_exhausted` when the backend rejects a scenario start because quota is exhausted.

Recommended frontend behavior for `429 quota_exhausted`:

- keep quota state advisory in the frontend and treat the backend response as authoritative;
- disable the run action or show a clear quota-exhausted state after the response;
- do not show a progress row, job, or partial session for the rejected attempt because the backend
  creates none.

Frontend-safe responses must not expose prompts, provider policies, provider/model names, retry
budgets, PydanticAI run ids, LiteLLM response ids, or raw unsafe exception text.
