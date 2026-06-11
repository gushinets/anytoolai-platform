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
- `pollJob()`
- `getScenarioSession()`
- `getArtifact()`
- `createHandoff()`
- `openHandoffConsent()`
- `captureEmail()`
- `trackClientEvent()`
- `renderQuotaState()`
- `renderJobStatus()`
- `renderError()`
