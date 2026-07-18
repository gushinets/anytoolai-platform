# Frontend Boundaries

Frontends are thin delivery surfaces.

They may:

- collect input;
- create guest identity through backend APIs;
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
- call LLM providers directly;
- own authoritative scenario state.

Shared `ce-kit` must provide reusable API/job/quota/handoff helpers so MVP-B Chrome Extensions do not copy that code.

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

## A12 public scenario runtime contract

The A12 public runtime surface is:

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

- `404` for unknown scenario or unknown session;
- `409` for stale checkpoints, non-actionable checkpoints, or disallowed next actions;
- `422` for invalid frontend selection or non-object scenario input.

Frontend-safe responses must not expose prompts, provider policies, provider/model names, retry
budgets, PydanticAI run ids, LiteLLM response ids, or raw unsafe exception text.
