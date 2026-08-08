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

MVP-A2 Client Surfaces owns shared `ce-kit`, web mirror, and shared browser journeys. Product-owned
Chrome Extensions remain in Freelancer Suite and must consume CE-kit rather than copy transport,
storage, identity, quota, polling, result, or handoff code. MVP-A1 has no frontend dependency.

After A13/A15 (ANY-8, ANY-170/ANY-171), `createGuestIdentity()`, `getQuota()`, `startScenario()`
(via `prepareScenarioStart()`), `getScenarioSession()`, `pollScenarioSession()`, and `nextAction()`
are real CE-kit helpers backed by `PlatformApiClient`.

Required `ce-kit` capabilities:

- `createGuestIdentity()`
- `getRuntimeConfig()`
- `startScenario()`
- `getScenarioSession()`
- `nextAction()`
- `pollScenarioSession()`
- `getResult()`
- `createHandoff()`
- `openHandoffConsent()`
- `captureEmail()`
- `trackClientEvent()`
- `renderQuotaState()`
- `renderJobStatus()`
- `renderError()`

A15 ownership and delivery slices:

- A13 backend guest identity and quota enforcement are implemented;
- A15a / ANY-170 delivered the central `PlatformApiClient`, async storage, guest identity, runtime config,
  safe errors, cancellation, and OpenAPI drift foundation;
- A15b / ANY-171 delivered real quota HTTP calls, idempotent scenario start, bounded session polling,
  next actions, typed `429 quota_exhausted` handling, and CE integration tests;
- A15c / ANY-226 owns `getResult()` over the Platform Core frontend-safe result API;
- A18 owns shared client handoff helpers and web consent; product-specific handoff routes remain in
  Freelancer Suite.

## A12/A13 public scenario runtime contract

The A12/A13 public runtime surface is:

- `POST /v1/identity/guest`
- `GET /v1/products/{product_id}/quota?guest_id={guest_id}`
- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start`
- `GET /v1/scenario-sessions/{id}`
- `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}`
- `GET /v1/results/{result_artifact_id}` (A12b / ANY-217)

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
When a product's quota policy uses `dimension: scenario`, quota state checks also provide
`scenario_id`; product-wide policies do not require it.

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

Product Chrome Extensions complete through CE-kit and the frontend-safe result API. Opening the
same result in web mirror is an optional MVP-A2 integration, never a prerequisite for MVP-A1 or an
individual Freelancer product.

## A12b public result artifact contract

`GET /v1/results/{result_artifact_id}` returns only the normalized canonical workflow result for a
`result_artifact_id` already surfaced by `startScenario()` / `getScenarioSession()`:

```json
{
  "result_artifact_id": "artifact_123",
  "scenario_session_id": "scenario_session_123",
  "job_id": "job_123",
  "workflow_id": "kernel_demo.single_action_extract_v1",
  "workflow_version": 1,
  "schema_ref": "kernel_demo.extract_output_v1",
  "schema_version": 1,
  "created_at": "2026-01-01T00:00:00Z",
  "output": { "...": "workflow output schema-shaped payload" }
}
```

The endpoint is scoped to tenant/region and only ever serves an artifact that is: `stored`, of the
canonical `structured_output` type (never `structured_output_debug_raw` or any raw/debug artifact),
tagged `artifact_role: workflow_result`, linked as `result_artifact_id` on a `succeeded` job whose
tenant/region/product/frontend match the artifact's, and re-validated against its workflow's
output schema/version at read time. `output` is never returned raw from storage without this
re-validation pass.

Raw/debug artifacts (`structured_output_debug_raw` type, or any artifact not tagged
`artifact_role: workflow_result`) are rejected outright by the canonical-artifact guard above and
never reach response serialization.

Separately, because the endpoint returns the full normalized output *object* (unlike handoffs,
which only ever expose an explicit per-field allowlist mapping), and shipped workflow output
schemas may still declare `additionalProperties: true`, `ResultService` additionally rejects any
normalized output containing a *key* that exactly matches (after normalizing `-`/`_`/case to a
common form) a small, results-specific denylist, at any nesting depth. The list covers both the
actual bare internal field names used for provider/prompt lineage elsewhere in the platform
(`prompt`, `prompt_ref`, `provider`, `model`, `provider_policy_ref`, `provider_call_id`,
`gateway_backend`, `gateway_model`, `pydantic_run_id`, `litellm_response_id`) and additional
compound/lineage-shaped names not currently used verbatim elsewhere but plausible leak shapes
(`system_prompt`, `raw_prompt`, `prompt_template`, `raw_provider`, `provider_output`,
`provider_model`, `provider_name`, `provider_policy`, `model_name`, `model_id`, `model_version`,
`litellm`, `litellm_debug_info`, `trace_id`, `parent_trace_id`). Key normalization strips `-`/`_`
separators and casefolds, from both the incoming key and the marker, then compares the results for
equality — it deliberately does **not** try to re-insert word boundaries into camelCase/acronym
spellings (an earlier revision did, and needed a growing pile of regex rules that still missed
fully-uppercase spellings like `TRACEID`/`GATEWAYMODEL`, which have no lowercase letter to anchor
a boundary on, and multi-acronym PascalCase like `LiteLlmDebugInfo`, which splits into more words
than its marker has). Comparing separator-stripped canonical forms sidesteps that ambiguity
entirely while still being a whole-string equality check, so `provider-model`, `providerModel`,
`GATEWAYMODEL`, and `LiteLlmDebugInfo` all resolve to the same canonical form as their marker.
Matching is against the whole normalized key, not a
substring: an earlier
revision matched markers as substrings, which both left the bare internal names above undetected
(they were deliberately excluded from a substring-based list to avoid colliding with fields like
`car_model`/`insurance_provider`) and, separately, rejected unrelated legitimate compound fields
that happened to contain a marker substring (e.g. `vehicle_model_id`, `car_model_version`,
`insurance_provider_name`, `business_trace_id`). Whole-key matching fixes both. This list is
deliberately its own, narrower policy rather than a reuse of `common.logging.SENSITIVE_KEY_PARTS`
(the log-redaction denylist): a false positive there just redacts a logged value, while a false
positive here would make an entire valid, already-succeeded result silently disappear as a 404, so
broad single-word markers like `email`/`token`/`handoff`/`secret` are intentionally not used. This
is a defense-in-depth backstop against those specific key names while workflow output schemas are
not yet uniformly closed — it is not a general guarantee against every possible form of
provider/prompt/debug content (an unlisted key name, or a value rather than a key, is not
inspected). It also cuts both ways: because `prompt`/`provider`/`model` are blocked as bare exact
keys (not just compound markers), a future workflow whose *legitimate* schema-declared output
happens to use one of those exact names (e.g. a prompt-generation product returning a field
literally called `prompt`) would incorrectly 404 rather than leak. This is an accepted trade-off
of a key-name denylist over a schema; a workflow needing a legitimate field with one of these
exact names must pick a differently-named field. Closing the relevant workflow output schemas, or
introducing a dedicated public output schema per workflow, remains open follow-up work.

Safe API behavior — both cases return `404`, and neither ever includes artifact/job internals,
prompts, or provider/model identifiers in the response body:

- `result_artifact_not_found`: the id is unknown, or belongs to a different tenant/region;
- `result_artifact_unavailable`: the artifact exists in the caller's tenant/region but is not an
  available canonical result (a raw/debug artifact, an artifact from an unfinished/non-succeeded
  job, an artifact with schema/version drift, or content that fails re-validation against its
  declared output schema).

`getScenarioSession()` only ever surfaces a non-null `result_artifact_id` once the job has
succeeded, so this endpoint is not meant to be polled for an in-progress job. The two codes
intentionally differ so a caller holding a previously-valid id (e.g. from before a config redeploy
changed the workflow's output schema/version) can tell "this id is wrong or out of scope" apart
from "this id was valid but the artifact is no longer an available canonical result." This does
distinguish "exists in my own tenant/region" from "unknown," i.e. it is not a strict
no-existence-oracle guarantee across all callers who can reach an id in-scope — it only guarantees
that a caller cannot learn anything about artifacts outside their own tenant/region.

The canonical-artifact guard (job/workflow/schema consistency + schema re-validation) is shared with
the handoff payload builder (see `handoff-model.md`) through
`anytoolai_platform_core.artifacts.canonical.resolve_canonical_workflow_result`, so both consumers
reject the same non-canonical states identically.

## A17 public handoff contract

The backend now provides `POST /v1/handoffs`, token-based preview, accept, and decline endpoints.
The create response is the only response containing the opaque plaintext token. Frontends must
treat it as a short-lived bearer capability, avoid analytics/logging/storage beyond the consent
navigation need, and never derive or inspect its contents.

The unexpired preview response contains only display-safe product/scenario identity, status,
expiry, bounded config-mapped preview data, and nullable target session/job ids. It never contains
hidden target context, source artifact/session/job identifiers, token hashes, artifact metadata,
prompts, providers/models, or debug data. After token TTL, preview content and linked target
identifiers are redacted even when the durable handoff remains in a terminal accepted, consumed,
declined, or failed state. The backend remains authoritative for expiry and terminal status.

Accept creates and links the target session. An immediate definition may return a target job; a
deferred definition returns a retrievable `waiting_for_user/handoff_ready` target session with
`job_id: null`. Frontends must not start or fabricate a target workflow merely because the user
accepted; start policy belongs to the config contract and backend.
