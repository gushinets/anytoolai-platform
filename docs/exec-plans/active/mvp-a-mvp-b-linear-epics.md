# MVP-A and MVP-B Linear-ready Epics

## Status

- State: active
- Owner: product/engineering
- Created: 2026-06-23
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: keep the delivery map aligned with active MVP-A/MVP-B issues.
- Blocker: none

## Overview

This file contains implementation-ready epic descriptions for importing into Linear.

`docs/product-specs/mvp-scope-source-of-truth.md` controls product scope when this delivery map
and the product specification differ.

Use the same structure for every Linear ticket:

- **Priority**
- **Depends on**
- **Goal**
- **Implementation details**
- **Acceptance criteria**
- **DoD**
- **Repo impact**
- **Non-goals**
- **Implementation notes for assignee**
- **LLM runtime alignment**

All epics are intended to fit into 5-7 working days. Larger areas were split into smaller epics.

LLM runtime decisions from `docs/architecture/llm-runtime.md` and ADR 0007 apply to every epic: PydanticAI is allowed only inside the structured LLM executor boundary, LiteLLM SDK is allowed only behind ProviderGateway/provider adapters, LiteLLM Proxy is not part of MVP-A, hidden LiteLLM retries stay disabled, and `platform.provider_calls` is one row per physical ProviderGateway attempt.

---

## MVP-A: Platform Kernel

### A01. Platform Contracts And Public SDK Models

**Priority:** P0  
**Depends on:** repo skeleton  
**Goal:** зафиксировать продуктово-нейтральные typed contracts для всего kernel runtime.  
**Implementation details:** public DTO живут в `platform-sdk/contracts`; internal domain models в `platform-core` могут отличаться реализацией, но должны использовать те же field names. Описать `ProductDefinition`, `FrontendDefinition`, `ScenarioDefinition`, `WorkflowDefinition`, `WorkflowStepDefinition`, `ActionDefinition`, `ActionConfiguration`, `PromptRef`, `ProviderPolicy`, `QuotaPolicy`, `HandoffDefinition`, `EventEnvelope`. Для statuses добавить enums рядом с models.  
**Acceptance criteria:** существующие `kernel_demo` YAML парсятся в typed models; required fields валидируются; Freelancer/domain terms не появляются в contracts; нет циклических импортов между sdk/core/actions.  
**DoD:** unit tests на valid configs, missing fields, invalid enum, unknown optional metadata; docs по config model обновлены.  
**Repo impact:** `packages/backend/platform-sdk/src/anytoolai_platform_sdk/contracts`, `packages/backend/platform-core/src/anytoolai_platform_core/*/models.py`, `docs/architecture/config-model.md`.  
**Non-goals:** не делать SQLAlchemy runtime models, migrations, API endpoints.

**Implementation notes for assignee:** контракты являются публичной границей между backend, CE kit и web mirror, поэтому нужно зафиксировать field names, enum names и минимальную версионируемость моделей; internal core models могут иметь другую реализацию, но не другой смысл полей. Добавить explicit forbidden vocabulary для Freelancer/domain terms (`Proposal`, `Brief`, `Upwork`, `ScopeCreep`, etc.) и тест, что эти термины не попали в SDK contracts.

**LLM runtime alignment:** `ProviderPolicy` contracts must encode split retry budgets (`transport`, `validation`, `hard_limits`) and keep LiteLLM-format model strings in provider policy/model registry contracts only. Product, workflow, action, frontend, and CE-facing contracts should carry `provider_policy_ref`, never `gateway_model`, raw provider/model names, PydanticAI objects, or LiteLLM request shapes.

### A02. Config Loader And Registry Validation

**Priority:** P0  
**Depends on:** A01  
**Goal:** сделать read-only config registry, который является source of truth для MVP-A definitions.  
**Implementation details:** loader sequence: kernel defaults -> regions/provider policies -> action definitions -> product configs -> prompts/schemas -> cross-reference validation. Registry должен возвращать immutable objects. Ошибки должны содержать file path, config id, missing/broken ref.  
**Acceptance criteria:** API/app startup падает до serving traffic при invalid config; registry возвращает product/scenario/workflow/action_config/prompt/provider_policy; duplicate ids and broken refs fail fast.  
**DoD:** tests на valid load, duplicate ids, missing workflow, missing action_config, missing prompt/schema; `validate_configs.py` использует общий loader или тот же validation слой.  
**Repo impact:** `packages/backend/platform-core/src/anytoolai_platform_core/config`, `products`, `workflows`, `actions`, `prompts`, `configs/kernel`.  
**Non-goals:** DB-backed registry, runtime editing, admin UI.

**Implementation notes for assignee:** registry в MVP-A строго read-only и загружается из repo configs, без fallback в DB и без silent defaults. Нужно явно описать merge/order rules, формат ошибок (`file_path`, `config_id`, `ref_type`, `ref_value`) и гарантировать, что startup падает до serving traffic при любом broken ref; исполнитель не должен добавлять runtime editing или admin hooks.

**LLM runtime alignment:** config validation must reject provider/model strings in product, scenario, workflow, action config, prompt, and frontend files; those files may reference only `provider_policy_ref`. Provider policy validation must require explicit owners for transport retries and validation retries, enforce `litellm_num_retries_per_attempt: 0` for MVP-A, and require `max_physical_provider_calls_per_action`.

### A03. Cross-platform Local And CI Checks

**Priority:** P0  
**Depends on:** none  
**Goal:** сделать baseline checks воспроизводимыми на Windows PowerShell и Linux CI.  
**Implementation details:** добавить `python scripts/agent/quick_check.py` как основной entrypoint; bash wrappers могут вызывать его. Убрать необходимость ручного `PYTHONPATH` через wrapper или editable install strategy.  
**Acceptance criteria:** одна команда запускает config validation, architecture validation, pytest на Windows без WSL; та же логика используется в GitHub Actions.  
**DoD:** README/AGENTS updated; локальная команда проходит; CI workflow зелёный.  
**Repo impact:** `scripts/agent`, `.github/workflows`, `README.md`, `AGENTS.md`, `pyproject.toml`.  
**Non-goals:** не переписывать весь dev tooling, не добавлять новые package managers.

**Implementation notes for assignee:** в задаче нужен один canonical command, который одинаково понятен человеку и CI; все bash/powershell wrappers должны быть thin wrappers вокруг Python entrypoint. Указать, какие проверки входят в baseline (`config validation`, architecture tests, pytest subset, optional frontend checks), как задаётся test DB, и что не требуется менять package manager или пересобирать весь tooling.

**LLM runtime alignment:** baseline architecture checks must cover forbidden `pydantic_ai`, `litellm`, direct provider SDK, and npm provider imports outside approved boundaries, including TypeScript extension/frontend code. The quick-check path should not require real provider credentials or live LLM calls; use fake-provider fixtures for deterministic validation.

### A04. Runtime Storage And Repositories

**Priority:** P0  
**Depends on:** A01  
**Goal:** заменить placeholder migrations/repositories на durable runtime storage для core execution state.  
**Implementation details:** реализовать Alembic `0001` для `platform.scenario_sessions`, `jobs`, `action_runs`, `provider_calls`, `artifacts`; добавить SQLAlchemy tables/repositories. Индексы: `scenario_session_id`, `job_id`, `product_id`, `created_at`, `status`. Repositories должны работать через явную transaction boundary.  
**Acceptance criteria:** можно create/read/update session, job, action_run, provider_call, artifact; все runtime rows несут `tenant_id`, `region`, и product/frontend dimensions где применимо.  
**DoD:** repository tests на status transitions, required fields, artifact text/json storage; migration applies on clean DB.  
**Repo impact:** `migrations/platform/versions/0001_runtime_tables.py`, `platform-core/storage`, `scenarios`, `workflows`, `actions`, `artifacts`, `providers`.  
**Non-goals:** event_log, quota, email, handoff tables.

**Implementation notes for assignee:** схемы таблиц должны следовать MVP-A scope: все runtime entities несут `tenant_id`, `region`, `product_id` и session/job/action dimensions где применимо. Зафиксировать status enums, id format, timestamp semantics, JSONB/text artifact behavior, indexes и explicit transaction boundary; не добавлять product definition tables, billing tables или domain-specific runtime tables.

**LLM runtime alignment:** `platform.provider_calls` must be modeled as one row per physical ProviderGateway attempt, not one PydanticAI run, workflow step, or logical LiteLLM call. Include gateway/policy/model dimensions, semantic attempt index, transport attempt index, physical call index, failure kind, token/cost/latency fields, optional `pydantic_run_id`, optional `litellm_response_id`, and allow only action-level PydanticAI usage summaries in `action_runs.metadata`.

### A05. Event Log And Event Emitter

**Priority:** P0  
**Depends on:** A04  
**Goal:** сделать event log обязательной частью runtime, а не аналитическим afterthought.  
**Implementation details:** реализовать Alembic `0002`; API `emit(event_type, context, result_status=None, properties=None)`. `ExecutionContext` заполняет `tenant_id`, `region`, `product_id`, `frontend_id`, `scenario_session_id`, `job_id`, `workflow_id`, `action_type`, `artifact_id`, `handoff_id` где доступны.  
**Acceptance criteria:** emitter rejects missing `tenant_id`/`region`; platform taxonomy покрывает guest/quota/scenario/workflow/action/provider/artifact/handoff/client events; события пишутся для success and failure paths.  
**DoD:** tests на persistence, required dimensions, safe properties json; generated event catalog updated.  
**Repo impact:** `migrations/platform/versions/0002_event_log.py`, `platform-core/events`, `docs/architecture/event-taxonomy.md`, `docs/generated/event-catalog.md`.  
**Non-goals:** dashboards, BI exports, billing ledger.

**Implementation notes for assignee:** event log является runtime contract, не аналитическим дополнением, поэтому все execution paths должны писать события через единый emitter. Добавить taxonomy source file/catalog, required dimensions, correlation/request id if available, safe property redaction rules и тесты на обязательные events для success/failure сценариев; не строить BI export, dashboard или billing ledger.

**LLM runtime alignment:** provider events should correlate with `provider_calls` using `scenario_session_id`, `job_id`, `action_run_id`, `workflow_id`, `step_id`, `provider_policy_ref`, physical call index, and response/run ids when available. Any LiteLLM callbacks or PydanticAI tracing are auxiliary telemetry only; the domain `event_log` and `provider_calls` ledger remain the source of truth.

### A06. API Bootstrap And Runtime Config Endpoint

**Priority:** P0  
**Depends on:** A02, A04  
**Goal:** связать FastAPI composition root с registry/storage и открыть frontend-safe runtime config.  
**Implementation details:** `create_app()` должен bootstrap configs on startup, wire dependencies, include error handler/request context. `GET /v1/products/{product_id}/runtime-config` возвращает product id, frontend ids, scenario ids, input/output renderer hints, quota summary; не возвращает prompt text, system prompt, provider policy/model.  
**Acceptance criteria:** unknown product returns safe 404; invalid startup config prevents API serving; OpenAPI содержит endpoint.  
**DoD:** API tests through `httpx`; generated OpenAPI updated.  
**Repo impact:** `apps/platform-api/src`, `platform-core/bootstrap`, `docs/generated/openapi.md`.  
**Non-goals:** scenario start, jobs, auth.

**Implementation notes for assignee:** endpoint должен возвращать только frontend-safe runtime metadata: ids, enabled scenarios, renderer hints, quota summary и allowed UI capabilities. Явно запретить prompt text, system prompts, provider policy/model, internal file paths и secrets в response; добавить OpenAPI example, safe error shape, startup failure test и basic CORS/extension-origin handling if already present locally.

**LLM runtime alignment:** runtime config responses must not expose `provider_policy_ref`, retry budgets, `gateway_backend`, LiteLLM model strings, provider names, PydanticAI settings, or provider-call telemetry ids. Provider/model choice remains backend-owned and resolved from repo config at execution time.

### A07. Provider Gateway And Fake Provider

**Priority:** P0  
**Depends on:** A02, A04  
**Goal:** обеспечить единственный путь к model/provider calls через gateway.  
**Implementation details:** перейти к async `ProviderGateway`; adapters implement async protocol. Fake provider chooses fixture by request metadata such as `action_config_id`/fixture key, not prompt string. Gateway resolves `ProviderPolicy`, handles timeout/retry metadata, writes `provider_calls`.  
**Acceptance criteria:** provider_call row exists for success and failure; direct provider import outside adapter prohibited; fake provider deterministic.  
**DoD:** unit/integration tests; architecture test remains green; provider docs updated.  
**Repo impact:** `platform-core/providers`, `tests/fixtures/provider`, `configs/kernel/provider_policies.yaml`.  
**Non-goals:** full production OpenAI hardening, billing-grade cost precision.

**Implementation notes for assignee:** единственный разрешённый путь к LLM/provider calls - через gateway; actions не импортируют provider adapters напрямую. Зафиксировать async request/response DTO, fake-provider fixture selection by metadata, timeout/retry metadata, provider_call logging fields (`provider`, `model`, tokens, latency, estimated_cost when known, success/failure) и architecture test, который ловит direct imports.

**LLM runtime alignment:** implement the in-process LiteLLM SDK adapter only under the provider boundary; do not introduce LiteLLM Proxy in MVP-A. ProviderGateway owns transport retry loops and hard-cap enforcement, calls LiteLLM with `num_retries=0` for each physical attempt, logs one `provider_calls` row per attempt, and must not import or depend on PydanticAI.

### A08. Structured Output Engine

**Priority:** P0  
**Depends on:** A07  
**Goal:** превратить raw LLM output в validated structured artifact.  
**Implementation details:** pipeline: raw text -> parse JSON object -> validate JSON Schema/Pydantic -> normalized dict -> artifact. On failure: save raw output artifact, return standardized safe validation error, retry according to action/provider policy.  
**Acceptance criteria:** invalid JSON retries or fails predictably; schema mismatch produces safe error; raw provider output is debuggable; final output matches declared output schema.  
**DoD:** tests for valid JSON, non-object JSON, malformed JSON, schema mismatch, retry exhausted.  
**Repo impact:** `platform-core/structured_output`, `platform-core/artifacts`, `docs/architecture/structured-output.md`.  
**Non-goals:** custom schema DSL, product-specific validation code.

**Implementation notes for assignee:** structured output должен быть generic platform layer: JSON parse, schema validation, normalized dict, artifact write и standardized safe error. Сохранять raw provider output как debug artifact, связанный с provider_call/action_run, но не отдавать raw output в safe user error; не добавлять custom schema DSL или product-specific validators.

**LLM runtime alignment:** split ownership carefully: PydanticAI structured-output binding and validation retry live inside `StructuredLlmActionExecutor`, while AnytoolAI final validation, artifact persistence, and safe errors remain platform behavior. ProviderGateway/LiteLLM must not configure a second conflicting `response_format` or schema for the same action.

### A09. Action Runner And First Atoms

**Priority:** P0  
**Depends on:** A07, A08  
**Goal:** сделать runnable generic action execution на первых двух атомах.  
**Implementation details:** implement `ActionRunner.run(action_type, action_config_id, input_payload, context) -> ActionResult`. Context must include tenant, region, product, frontend, scenario_session_id, job_id, workflow_id, workflow_version, step_id, guest/user. First atoms: `text.extract_structured_fields`, `text.detect_issues_by_taxonomy`.  
**Acceptance criteria:** action resolves config/prompt/policy, calls `StructuredLlmActionExecutor`, validates input/output, creates action_run, emits action/provider/artifact events, stores output artifact.  
**DoD:** tests for A01/A04 happy path and provider/validation failure.  
**Repo impact:** `platform-core/actions`, `platform-actions/structured_llm`, `platform-actions/definitions`, `configs/kernel/products/kernel_demo`.  
**Non-goals:** product-specific atom names, Freelancer semantics.

**Implementation notes for assignee:** ActionRunner должен принимать `action_type` и `action_config_id`, резолвить prompt/policy/schema через registry и исполнять generic `StructuredLlmActionExecutor`. Для первых atom definitions нужны конкретные input/output schemas, prompt refs, fake fixtures и assertions на context propagation, action_run statuses, artifact linkage и events; запрещены product-specific action names вроде `generate_proposal`.

**LLM runtime alignment:** `StructuredLlmActionExecutor` is the only allowed PydanticAI boundary and must call ProviderGateway for every physical provider attempt instead of importing LiteLLM or provider SDKs. Cache clients/agents by stable config keys such as `provider_policy_ref`, `model_ref`, schema version, and `action_config_id`; pass run-specific ids through execution context, never cached objects.

### A10. Sequential Workflow Runner

**Priority:** P0  
**Depends on:** A09  
**Goal:** исполнить config-defined sequential workflows.  
**Implementation details:** extend workflow step schema backward-compatibly with optional `input_mapping`, `output_mapping`, `when`, `retry_count`; existing simple YAML remains valid. Mapping sources: `scenario.input`, `steps.<step_id>.output`, `context.*`.  
**Acceptance criteria:** single-step and multi-step workflows run; failed step stops workflow; skipped step records reason; final artifact created; workflow events emitted.  
**DoD:** tests for mapping, conditional skip, retry, failed step, final artifact.  
**Repo impact:** `platform-core/workflows`, `configs/kernel/products/kernel_demo/workflows.yaml`, `docs/architecture/workflow-model.md`.  
**Non-goals:** parallel branches, nested workflows, visual builder, webhooks.

**Implementation notes for assignee:** runner в MVP-A intentionally simple: sequential only, no durable workflow engine. Нужно описать mini-contract для `input_mapping`, `output_mapping`, `when`, `retry_count`, source paths (`scenario.input`, `steps.<step_id>.output`, `context.*`), skip reason storage и final artifact selection; не добавлять parallel branches, subworkflows, webhooks или graph builder.

**LLM runtime alignment:** workflow `retry_count` is not the provider retry policy and must not be forwarded as a generic LLM retry value. Step retries wrap action execution explicitly, while transport retries, validation retries, and physical-call hard caps remain controlled by ProviderPolicy and enforced by the executor/gateway split.

### A11. Job Lifecycle And Worker Integration

**Priority:** P0  
**Depends on:** A10  
**Goal:** связать job table, worker handler и workflow runner.  
**Implementation details:** simple DB-backed job lifecycle: `created -> running -> succeeded/failed/canceled`. Claim only `created` jobs; write safe error fields. No Celery/Temporal. Worker handler calls workflow runner and persists statuses.  
**Acceptance criteria:** job always linked to scenario_session_id; success writes result_artifact_id; failure writes safe error and event; worker boot test is no longer placeholder.  
**DoD:** integration tests for success/failure/cancel-ish path; idempotent claim behavior covered.  
**Repo impact:** `apps/platform-worker/src`, `platform-core/workflows`, `platform-core/storage/repositories.py`.  
**Non-goals:** distributed durable workflow engine, queue scaling.

**Implementation notes for assignee:** job lifecycle должен быть DB-backed и минимальным: claim только `created` jobs, безопасное завершение success/failure, idempotent behavior при повторном claim и safe error fields без raw provider leak. `canceled` можно поддержать как terminal status без полноценной queue cancellation; Celery, Temporal, distributed locks и scaling mechanics не входят.

**LLM runtime alignment:** job failure records should distinguish safe validation failures from safe transport/provider failures without exposing raw provider output. Preserve correlation from job to action runs, artifacts, events, and `provider_calls` so retries can be audited without relying on PydanticAI summaries or LiteLLM callbacks.

### A12. Scenario Runtime API

**Priority:** P0  
**Depends on:** A10, A11  
**Goal:** открыть пользовательский runtime entrypoint через scenario sessions.  
**Implementation details:** implement `POST /v1/products/{product_id}/scenarios/{scenario_id}/start`, `GET /v1/scenario-sessions/{id}`, `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}`. Start response: `scenario_session_id`, `job_id`, `status`, `allowed_next_actions`, optional `result_artifact_id`.  
**Acceptance criteria:** every start creates scenario_session_id; session/job dimensions match; next-action validates current checkpoint and allowed action; unknown scenario returns safe 404.  
**DoD:** API tests for start/get/next-action; docs updated.  
**Repo impact:** `apps/platform-api/src/routers`, `platform-core/scenarios`, `platform-core/scenarios/checkpoints.py`.  
**Non-goals:** resumable long-lived workflows, human approval queues.

**Implementation notes for assignee:** scenario start всегда создаёт `scenario_session_id` до запуска workflow/job и возвращает stable response для CE polling. Описать request body, async/sync ожидание, `allowed_next_actions` shape, checkpoint validation, safe 404/409/422 errors и связь session -> job -> artifact; long-lived resumable workflows и approval queues не реализуются.

**LLM runtime alignment:** `scenario_session_id` must propagate through ActionRunner, `StructuredLlmActionExecutor`, ProviderGateway, `provider_calls`, artifacts, and events. Scenario API responses must stay frontend-safe and not reveal prompts, provider policies, model names, retry budgets, PydanticAI run ids, or LiteLLM response ids.

### A13. Guest Identity And Quota

**Priority:** P1  
**Depends on:** A04, A12  
**Status:** backend-complete, integration pending; real CE-kit quota/start integration is deferred
to the A16 follow-up scope in this thread and to the local A15 CE client roadmap item.  
**Goal:** реализовать backend-enforced access-lite quota для guests.  
**Implementation details:** Alembic `0003` guest/quota tables. API creates opaque guest id; CE stores it locally. Quota consumed server-side on accepted scenario start, not frontend click.  
**Acceptance criteria:** guest can run N times; N+1 returns standardized `quota_exhausted`; quota events emitted; quota check endpoint returns current state.  
**DoD:** tests for guest create, quota check, consume, exhausted, repeat calls.  
**Repo impact:** `migrations/platform/versions/0003_guest_quota.py`, `platform-core/identity`, `platform-core/quotas`, `apps/platform-api/src/routers`.  
**Non-goals:** registered auth, magic link, subscriptions.

**Implementation notes for assignee:** quota enforcement находится только на backend и вызывается из scenario start flow, а не из CE click handler. Зафиксировать quota dimension как configurable policy from repo config, минимум `guest_id + product_id` with optional scenario dimension; consume должен быть transaction-safe для concurrent starts. Не добавлять registered auth, magic link, subscriptions или payment concepts.

**LLM runtime alignment:** quota consumption is tied to accepted scenario starts or explicit product policy, not to individual validation retries, transport retries, or physical provider attempts. Provider usage/cost is accounted in `provider_calls`; guest quota state must not depend on PydanticAI or LiteLLM telemetry.

### A14. Email Capture And Paywall Intent

**Priority:** P1  
**Depends on:** A13  
**Goal:** сохранить ранний conversion path после quota exhausted.  
**Implementation details:** implement `POST /v1/email-captures`, `POST /v1/paywall-intents`; normalize email; dedupe by normalized email + product_id + guest_id where available; keep source metadata in jsonb.  
**Acceptance criteria:** invalid email rejected; valid capture saved; paywall/waitlist intent saved; events `email_capture.submitted`, `waitlist.intent_submitted` or `paywall.intent_submitted` emitted.  
**DoD:** API/repository tests; safe validation errors.  
**Repo impact:** `platform-core/identity` or `quotas`, `apps/platform-api/src/routers`, migration `0003`.  
**Non-goals:** CRM integration, payment processor, marketing automation.

**Implementation notes for assignee:** email capture и intent - это access-lite conversion path после quota exhausted, не CRM. Добавить email normalization/lowercase/validation rules, dedupe semantics, `intent_type` enum or equivalent, product/guest/source metadata, PII-safe logging и events; не добавлять внешние marketing integrations, payment processors или user account creation.

**LLM runtime alignment:** email capture and paywall intent flows should not store provider/model metadata, raw LLM outputs, PydanticAI traces, or LiteLLM telemetry. Keep event properties PII-safe and product/session-scoped.

### A15. CE Kit MVP API Client

**Priority:** P1  
**Depends on:** A06, A12, A13  
**Goal:** заменить demo stubs в `ce-kit` реальным shared API client.  
**Implementation details:** central `PlatformApiClient` with base URL, timeout, typed request/response, safe error normalization. Export helpers: guest, runtime config, start scenario, poll job, session, artifact, email capture, quota, client event.  
**Acceptance criteria:** extensions do not duplicate API plumbing; ce-kit does not expose prompts/provider/model choice; errors have stable shape for UI.  
**DoD:** TypeScript typecheck; minimal tests or harness; README examples.  
**Repo impact:** `packages/frontend/ce-kit/src`, `packages/frontend/ce-kit/package.json`.  
**Non-goals:** product-specific UX, direct provider calls.

**Implementation notes for assignee:** ce-kit должен быть shared integration layer для всех CE, поэтому helpers возвращают typed results/errors и скрывают HTTP plumbing. Описать base URL configuration, timeout/retry/polling behavior, guest id persistence expectations, API versioning path и stable error union; не включать prompts, provider/model selection или product-specific UI decisions.
A15 must replace the A13 demo/deferred `startScenario()` and `getQuota()` helpers with real
Platform API calls, propagate the opaque guest id created by `createGuestIdentity()`, and handle
`429 quota_exhausted`, `422`, normal start success, and polling without moving quota enforcement into
the frontend.

**LLM runtime alignment:** `ce-kit` must never expose provider/model selection, `provider_policy_ref`, prompt text, retry controls, PydanticAI settings, LiteLLM settings, or provider-call internals. Browser retry/polling behavior is API-level only and must not attempt to replay LLM actions directly.

### A16. Web Mirror Result, Paywall, Onboarding Pages

**Priority:** P1  
**Depends on:** A06, A12, A14  
**Goal:** заменить web placeholders на минимальные working pages.  
**Implementation details:** client-fetch pages are acceptable. `/r/{artifact_id}` renders text/json with `web-result-kit`; `/paywall/{product_id}` captures email/intent; `/onboarding/{product_id}` shows product-safe install/continue state.  
**Acceptance criteria:** loading, not found, error, quota/paywall states handled; no dashboard/account behavior.  
**DoD:** frontend typecheck/build; component or Playwright smoke where available.  
**Repo impact:** `apps/web-mirror/src/app`, `apps/web-mirror/src/components`, `packages/frontend/web-result-kit`.  
**Non-goals:** user cabinet, auth pages, billing UI.

**Implementation notes for assignee:** web mirror - это минимальная публичная поверхность для artifacts/paywall/onboarding, не dashboard. Для каждой страницы нужны states `loading`, `not_found`, `safe_error`, `success`; `/r/{artifact_id}` рендерит только backend-returned artifact content through result kit, `/paywall` пишет capture/intent, `/onboarding` не создаёт account/auth flows.

**LLM runtime alignment:** web mirror pages render normalized backend artifacts only. Raw provider output artifacts, provider-call ledger fields, PydanticAI traces, LiteLLM response ids, and model/provider names remain backend-debug data and must not be surfaced in public result, paywall, or onboarding pages.

### A17. Handoff Backend Core

**Priority:** P1  
**Depends on:** A04, A05, A12  
**Goal:** реализовать generic user-confirmed handoff flow.  
**Implementation details:** Alembic `0004`; opaque expiring token; statuses `created/viewed/accepted/declined/consumed/expired/failed`. Default accept semantics: create/link target scenario session immediately; target workflow may run immediately only if config requires it.  
**Acceptance criteria:** token cannot be accepted twice; get returns safe preview; accept links source and target session through handoff_id; events emitted.  
**DoD:** repository/API tests for created/viewed/accepted/declined/expired.  
**Repo impact:** `migrations/platform/versions/0004_handoffs.py`, `platform-core/handoffs`, `apps/platform-api/src/routers`.  
**Non-goals:** raw extension-to-extension handoff, arbitrary user-created routes.

**Implementation notes for assignee:** handoff - backend-tokenized, user-confirmed flow; CE не передаёт raw result напрямую в другую extension. Зафиксировать token entropy/expiry, status transitions, double-accept handling, safe preview payload, source/target session linkage, event chain и policy для immediate vs deferred target workflow start; arbitrary custom routes не нужны.

**LLM runtime alignment:** handoff payloads should be built from normalized, schema-valid artifacts and safe preview fields, not raw provider outputs or LLM debug metadata. If accepting a handoff starts a target workflow, that workflow must create its own action runs and `provider_calls` under the target `scenario_session_id`.

### A18. Handoff Web And CE Integration

**Priority:** P1  
**Depends on:** A15, A17  
**Goal:** дать frontend surface для handoff consent.  
**Implementation details:** consent page data shape: source product, target product, safe preview summary, expires_at, status. CE helpers: `createHandoff`, `openHandoffConsent`.  
**Acceptance criteria:** CE creates handoff; browser opens consent; accept/decline updates backend; expired/declined terminal states render safely.  
**DoD:** frontend typecheck; integration smoke with backend.  
**Repo impact:** `apps/web-mirror/src/app/handoff`, `packages/frontend/ce-kit/src/handoffs`, `extensions/kernel-demo-ce`.  
**Non-goals:** complex multi-step consent, hidden raw context display.

**Implementation notes for assignee:** UI должен показывать только safe preview, status и accept/decline actions from backend, без hidden raw context dump. Добавить dependency/coordination with web mirror page implementation, CE helper signatures, terminal states rendering (`accepted`, `declined`, `expired`, `consumed`) и smoke path from kernel-demo-ce to `/handoff/{token}`.

**LLM runtime alignment:** handoff UI and CE helpers must not expose prompts, provider policies, model names, raw provider outputs, PydanticAI traces, LiteLLM telemetry, or hidden source artifacts. The only LLM-derived content shown here should already be normalized and approved by backend preview rules.

### A19. Kernel Demo CE End-to-End

**Priority:** P1  
**Depends on:** A15, A16, A18  
**Goal:** сделать reference CE, который доказывает MVP-A runtime.  
**Implementation details:** support scenarios `single_action_smoke_v1`, `multi_step_workflow_smoke_v1`, `quota_exhausted_smoke_v1`, `handoff_smoke_source_v1`. UI states: input, progress, result, copy, quota exhausted, email capture, handoff.  
**Acceptance criteria:** CE runs scenario through backend; CE has no prompts/provider config; manual script covers install/open/run/copy/handoff/email.  
**DoD:** WXT build/typecheck; browser smoke documented.  
**Repo impact:** `extensions/kernel-demo-ce/src`, `packages/frontend/ce-kit/src/ui`.  
**Non-goals:** unified CE for Freelancer products.

**Implementation notes for assignee:** kernel-demo-ce - reference implementation for platform mechanics, not product UX. Keep it thin: use ce-kit for all API calls, no prompt/provider/workflow decisions in extension, and document manual smoke checklist for install/open/run/poll/result/copy/quota/email/handoff. If multi-step demo uses `document.generate_from_template`, coordinate with A20a readiness or use a two-atom workflow until A20a lands.

**LLM runtime alignment:** kernel-demo-ce may trigger scenarios but must not choose provider policy, model, prompts, structured-output mode, validation retries, or transport retries. Fake vs real provider behavior is backend config only; the CE smoke should verify that no LLM runtime settings are bundled in extension code.

### A20a. Reply/Document/Questions Atom Pack

**Priority:** P1  
**Depends on:** A09  
**Goal:** сделать runnable atoms `text.compose_reply`, `document.generate_from_template`, `text.generate_clarifying_questions`.  
**Implementation details:** add/update action definitions, input/output schemas, prompt refs, fake provider fixtures, smoke coverage.  
**Acceptance criteria:** all three run through generic action runner and produce validated artifacts.  
**DoD:** action registry tests and fake-provider smoke pass.  
**Repo impact:** `configs/kernel/action_definitions`, `platform-actions/definitions`, `platform-actions/schemas`, `configs/kernel/products/kernel_demo`.  
**Non-goals:** product-specific reply/document semantics.

**Implementation notes for assignee:** each atom needs an action definition, input schema, output schema, prompt ref, provider policy ref and deterministic fake-provider fixture. Output schemas must remain generic (`reply`, `document`, `questions`) and not mention client/proposal/brief semantics; add smoke examples and tests that all outputs become validated artifacts through the generic runner.

**LLM runtime alignment:** atom definitions and action configs reference `provider_policy_ref` only; they must not contain LiteLLM model strings, provider SDK settings, or PydanticAI-specific objects. Validation retry is handled by `StructuredLlmActionExecutor`; ProviderGateway still logs every physical fake or real provider attempt.

### A20b. Scoring And Classification Atom Pack

**Priority:** P1  
**Depends on:** A09  
**Goal:** сделать runnable atoms `text.compare_and_classify`, `text.score_match_by_rubric`, `text.score_multidimensional_axes`.  
**Implementation details:** same structure: definitions, schemas, prompts/fixtures, smoke tests. Score schemas should use explicit numeric ranges and labels.  
**Acceptance criteria:** each atom returns schema-valid score/classification output and writes events/artifacts.  
**DoD:** registry/fake-provider tests pass.  
**Repo impact:** same as A20a.  
**Non-goals:** product-specific rubrics in platform-core.

**Implementation notes for assignee:** score/classification contracts need explicit numeric ranges, labels, confidence fields where useful, and validation for out-of-range scores. Rubrics/taxonomies are inputs or product config, not platform-core constants; add high/low/invalid fixture coverage and ensure events/artifacts are identical to other generic atoms.

**LLM runtime alignment:** score/classification validation must be expressed through generic schemas and final AnytoolAI validation, with PydanticAI retry only inside the structured executor. Fixtures should exercise invalid structured output and confirm provider-call accounting remains deterministic under validation retry.

### A20c. Persuasion/Angle/Rewrite Atom Pack

**Priority:** P1  
**Depends on:** A09  
**Goal:** сделать runnable atoms `text.compose_persuasive_text`, `text.synthesize_angle`, `text.generate_gap_rewrites`.  
**Implementation details:** platform action names stay generic; no `generate_proposal` action type.  
**Acceptance criteria:** each atom runs via generic executor; ProposalAI semantics remain deferred to MVP-B action configs/prompts.  
**DoD:** tests prove no forbidden Freelancer terms in platform-core.  
**Repo impact:** same as A20a.  
**Non-goals:** ProposalAI product behavior.

**Implementation notes for assignee:** keep action names and schemas platform-generic: `text.compose_persuasive_text`, `text.synthesize_angle`, `text.generate_gap_rewrites`. Add explicit tests that `generate_proposal`, `ProposalAI`, `Upwork` and similar product terms are absent from platform-core/action definitions; product-specific persuasion/proposal semantics move to MVP-B action configs/prompts.

**LLM runtime alignment:** this pack is especially vulnerable to product/runtime leakage: keep proposal semantics in MVP-B prompts/configs, keep provider/model selection behind `provider_policy_ref`, and keep all PydanticAI/LiteLLM usage inside the approved executor/gateway boundaries.

### A21a. Backend Runtime E2E Tests

**Priority:** P1  
**Depends on:** A12, A13, A20a-c  
**Goal:** заменить placeholder tests реальными backend e2e.  
**Implementation details:** tests use fake provider and clean test DB. Cover one-action, three-action, quota exhausted. Assert API response plus DB/event/artifact state.  
**Acceptance criteria:** no placeholder e2e remains for these flows; tests deterministic.  
**DoD:** pytest passes through cross-platform quick check.  
**Repo impact:** `tests/e2e`, `tests/fixtures`, `scripts/agent`.  
**Non-goals:** browser extension automation.

**Implementation notes for assignee:** e2e tests should assert not only API response, but DB rows, event_log entries, action_runs, provider_calls and artifacts. Use fake provider, isolated clean DB, deterministic fixture keys and the same command wired into quick_check; browser/extension automation remains outside this task.

**LLM runtime alignment:** add E2E coverage for retry accounting, including validation retry plus transport retry not exceeding `max_physical_provider_calls_per_action`, LiteLLM SDK `num_retries=0` in MVP mode, one `provider_calls` row per physical attempt, raw plus normalized artifact behavior, and final AnytoolAI validation after PydanticAI output handling.

### A21b. Handoff E2E Tests

**Priority:** P1  
**Depends on:** A17, A18  
**Goal:** prove source session -> handoff -> consent -> target session chain.  
**Implementation details:** create source scenario, create handoff, get consent payload, accept, assert target_scenario_session_id and event chain.  
**Acceptance criteria:** source/target linked through handoff_id; token terminal behavior tested.  
**DoD:** deterministic fake-provider e2e.  
**Repo impact:** `tests/e2e/test_kernel_handoff_flow.py`, fixtures.  
**Non-goals:** real Freelancer handoff routes.

**Implementation notes for assignee:** cover the full token lifecycle: created, viewed, accepted, declined, expired and double-accept rejection. Assertions must include source session, handoff row, target session, event chain and terminal status; do not add real Freelancer routes or product-specific handoff mapping here.

**LLM runtime alignment:** when a handoff acceptance creates or starts a target scenario, assert the target action runs have their own `provider_calls` rows and correlation ids. The source handoff data must come from normalized artifacts only, never raw provider output or LLM telemetry fields.

### A22a. MVP-A Release Gates

**Priority:** P1  
**Depends on:** A21a, A21b  
**Goal:** собрать единый release gate для MVP-A.  
**Implementation details:** command runs config validation, architecture validation, backend pytest, frontend typecheck/build.  
**Acceptance criteria:** gate green locally and CI, or known failures documented with owner and blocker.  
**DoD:** CI status and local command documented.  
**Repo impact:** `scripts/agent`, `.github/workflows`, `docs/quality-score.md`.  
**Non-goals:** performance/load testing.

**Implementation notes for assignee:** define one release-gate command and make CI run the same logical steps: config validation, architecture validation, backend tests, frontend typecheck/build and generated-doc freshness if available. Known failures must include owner, blocker, date and exact command output location; no load/performance testing in this gate.

**LLM runtime alignment:** release gates must include the LLM/provider import-boundary tests, provider policy validation for split retry budgets and hidden LiteLLM retries, structured-output ownership tests, provider-call granularity tests, and a check that real provider credentials are not needed for baseline fake-provider runs.

### A22b. Generated Docs Refresh

**Priority:** P1  
**Depends on:** A22a  
**Goal:** сделать generated docs фактическими, не placeholder.  
**Implementation details:** generate OpenAPI, config registry, action registry, event catalog, DB schema.  
**Acceptance criteria:** docs match current configs/schema/API; stale generated docs detectable.  
**DoD:** generated docs committed/updated by script.  
**Repo impact:** `docs/generated`, `scripts/agent/generate-docs.*`.  
**Non-goals:** marketing docs.

**Implementation notes for assignee:** generated docs must be reproducible from source configs/schema/API and marked as generated. Add stale-doc detection in CI or release gate, include OpenAPI, config registry, action registry, event catalog and DB schema outputs, and avoid hand-written marketing/product copy in generated files.

**LLM runtime alignment:** generated docs should show provider policy retry fields, model registry ids, action registry `provider_policy_ref` usage, `provider_calls` DB schema, and provider events without leaking secrets. Product/generated docs must not imply that frontends or product bundles choose providers, models, PydanticAI behavior, or LiteLLM options.

### A22c. MVP-A Boundary Audit

**Priority:** P1  
**Depends on:** A22a  
**Goal:** подтвердить, что MVP-B можно строить без изменения `platform-core`.  
**Implementation details:** audit no Freelancer terms in core, no prompts in extensions, no direct provider calls outside gateway, no product-specific endpoints.  
**Acceptance criteria:** architecture tests enforce boundaries; add-product recipe documented.  
**DoD:** handoff note for MVP-B team.  
**Repo impact:** `tests/architecture`, `docs/product-specs`, `docs/architecture/platform-boundaries.md`.  
**Non-goals:** implementing MVP-B products.

**Implementation notes for assignee:** audit must prove the practical handoff criterion: a real MVP-B product can be added by configs/prompts/schemas/CE wrapper without modifying `platform-core`. Add forbidden-term/import/endpoint tests, document the add-product recipe, and list allowed exceptions only as explicit kernel bugfixes; do not implement any MVP-B product in this task.

**LLM runtime alignment:** boundary audit must verify `pydantic_ai` appears only in approved `platform-actions` structured executor paths, `litellm` and direct provider SDKs appear only under ProviderGateway/provider adapters, LiteLLM-format model strings appear only in provider policy/model registry files, and product bundles/extensions never bypass ProviderGateway.

---

## MVP-B: Freelancer Validation Bundle

### B01. Freelancer Product Template And Bundle Loader

**Priority:** P0  
**Depends on:** MVP-A DoD  
**Goal:** создать стандарт добавления Freelancer products without core changes.  
**Implementation details:** each product folder must contain `product.yaml`, `scenarios.yaml`, `workflows.yaml`, `action_configs.yaml`, `prompts/`, `schemas/`; optional `handoffs.yaml`, `events.yaml`. Bundle loader подключается только на app/bootstrap/product-platform layer.  
**Acceptance criteria:** template product loads; `platform-core` does not import freelancer package.  
**DoD:** `test_bundle_loads.py` uses real template.  
**Repo impact:** `packages/backend/product-platforms/freelancer-suite`, `apps/platform-api/bootstrap`, `docs/product-specs/freelancer-suite-v0.md`.  
**Non-goals:** real product behavior.

**Implementation notes for assignee:** this task creates the product-packaging standard, not user-facing Freelancer behavior. Define manifest/schema versioning, required file names, loader order, validation errors and bootstrap integration point outside `platform-core`; add an architecture/import test proving `platform-core` has no dependency on `freelancer-suite`.

**LLM runtime alignment:** Freelancer product bundles may provide prompts, schemas, workflows, action configs, renderers, events, and handoff maps, but must not import PydanticAI, LiteLLM, or provider SDKs. Product action configs may reference `provider_policy_ref`; they must not carry LiteLLM-format model strings, gateway settings, or retry owner decisions.

### B02. ProposalAI CE Product

**Priority:** P0  
**Depends on:** B01  
**Goal:** первый реальный CE product as proof of config-defined product.  
**Implementation details:** input: client brief/task text, optional freelancer positioning/context. Workflow: `text.compose_persuasive_text`. Output: copy-ready proposal body, optional angle/rationale. CE: input, run, progress, result, copy, handoff to Send-Ready.  
**Acceptance criteria:** product runs without `platform-core` changes; `result_copied` event emitted; result artifact opens in web mirror.  
**DoD:** fake-provider happy path; CE build/typecheck.  
**Repo impact:** `freelancer-suite/products/proposal_ai`, `extensions/proposal-ai-ce`, `web-result-kit`.  
**Non-goals:** Gmail/Upwork posting, marketplace scraping.

**Implementation notes for assignee:** ProposalAI must be the first proof that a real product is config-defined: product config, scenario, workflow, action_config, prompt, schema, renderer and CE wrapper only. Define exact input/output schema, fake-provider fixture, result renderer fields, product events and Send-Ready handoff stub; do not add marketplace scraping, posting automation, custom backend endpoint or kernel changes.

**LLM runtime alignment:** ProposalAI uses `text.compose_persuasive_text` through product-specific prompts/schema/action config and a `provider_policy_ref` only. No ProposalAI backend or CE code may instantiate PydanticAI, call LiteLLM/provider SDKs, set models, tune transport retries, or read provider-call internals.

### B03. Acceptance Builder Product

**Priority:** P0  
**Depends on:** B01  
**Goal:** validate multi-atom product workflow for acceptance criteria/document output.  
**Implementation details:** workflow A01 + A07 + A10. Output sections: acceptance criteria, deliverables, assumptions, questions, suggested reply/document.  
**Acceptance criteria:** accepts handoff from Brief Decoder; renderer supports sectioned document.  
**DoD:** fake-provider e2e; no custom backend endpoint.  
**Repo impact:** `freelancer-suite/products/acceptance_builder`, `extensions/acceptance-builder-ce`.  
**Non-goals:** legal contract generation.

**Implementation notes for assignee:** implement as a multi-step config workflow over existing atoms; the product meaning lives in prompts/schemas/action_configs, not in backend code. Because Brief Decoder lands later, either use a fixture/scaffold source handoff for this task or explicitly move full Brief Decoder handoff validation to B08/B06; do not generate legal contracts or add document-domain tables.

**LLM runtime alignment:** Acceptance Builder composes existing generic atoms only; any document-specific behavior belongs in product prompts and output schema. Each step uses backend-resolved `provider_policy_ref` and the shared structured executor/gateway path, with no custom PydanticAI agent, LiteLLM call, provider selection, or action implementation.

### B04. Scope Guard Product

**Priority:** P1  
**Depends on:** B01  
**Goal:** detect scope risks and produce boundary-setting response.  
**Implementation details:** workflow A01 + A04 + A11 + A07. Risk taxonomy lives in product prompt/schema config, not platform-core.  
**Acceptance criteria:** result includes detected risks, classification, suggested reply; handles no-risk state.  
**DoD:** product smoke test and renderer coverage.  
**Repo impact:** `freelancer-suite/products/scope_guard`, `extensions/scope-guard-ce`.  
**Non-goals:** legal advice, CRM.

**Implementation notes for assignee:** risk taxonomy, classification labels and response style must live in product config/schema/prompt files. Include no-risk and high-risk fixtures, renderer behavior for risk lists and suggested reply, and a clear product copy boundary that this is not legal advice; no CRM integration, no custom risk tables and no platform-core taxonomy constants.

**LLM runtime alignment:** Scope Guard risk taxonomy can influence prompts and schemas, but it must not create provider/runtime specialization. The product should rely on existing action configs, `provider_policy_ref`, PydanticAI validation through the shared executor, and ProviderGateway provider-call logging.

### B05. Send-Ready Product

**Priority:** P1  
**Depends on:** B01, B02  
**Goal:** validate quality verdict and rewrite flow.  
**Implementation details:** workflow A04 + A11 + A02 + A08. Verdict enum: `ready`, `needs_revision`, `not_ready`; include score and rewrite suggestions.  
**Acceptance criteria:** ProposalAI handoff pre-fills draft; copy emits product event.  
**DoD:** smoke tests for ready and needs_revision fixtures.  
**Repo impact:** `freelancer-suite/products/send_ready`, `extensions/send-ready-ce`.  
**Non-goals:** actual send action.

**Implementation notes for assignee:** define verdict thresholds, score ranges, rewrite suggestion schema and ProposalAI artifact input mapping. Copy/result events must be product events layered on platform events; the product may prefill from handoff but must not send messages, open Gmail/Upwork compose automatically, or choose provider/model from CE.

**LLM runtime alignment:** Send-Ready may define verdict schemas and product fixtures, but it must not choose providers/models from the CE or product backend. Provider policy, transport retry, validation retry, and provider-call logging stay in the shared kernel runtime; handoff prefill uses normalized ProposalAI artifacts only.

### B06. Cross-product Handoff Map V1

**Priority:** P1  
**Depends on:** B02-B05  
**Goal:** реализовать реальные Freelancer handoff routes.  
**Implementation details:** each handoff config states `source_artifact_schema_ref`, `target_scenario_id`, field mapping. Routes: Task Finder -> ProposalAI, ProposalAI -> Send-Ready, Brief Decoder -> Scope Guard, Brief Decoder -> Acceptance Builder.  
**Acceptance criteria:** at least ProposalAI -> Send-Ready and Brief Decoder scaffold -> Acceptance Builder tested end-to-end.  
**DoD:** handoff map tests and consent page smoke.  
**Repo impact:** `freelancer-suite/shared/handoffs.yaml`, product handoff configs, relevant CE wrappers.  
**Non-goals:** arbitrary custom handoff routes.

**Implementation notes for assignee:** handoff routes are declarative product configs over the generic handoff backend. Add schema validation for `source_artifact_schema_ref`, `target_scenario_id`, field mapping and safe preview fields; because Task Finder and Brief Decoder may not exist yet, mark those routes as scaffolded until B07/B08 or update dependencies before implementation. Do not add arbitrary user-created routes or raw CE-to-CE transfer.

**LLM runtime alignment:** cross-product handoff maps reference artifact schemas and target scenarios, not raw provider outputs, provider-call ids, PydanticAI run ids, LiteLLM response ids, or model/provider metadata. Any target workflow started from handoff must go back through the standard executor and ProviderGateway path.

### B07. Task Finder Product

**Priority:** P1  
**Depends on:** B01, B06  
**Goal:** extract task listing and generate fit/angle for ProposalAI.  
**Implementation details:** CE consumes pasted listing or selected page text; no scraping automation. Workflow A01 + A11 + A02 + A09.  
**Acceptance criteria:** output includes extracted task fields, fit score, recommended angle; handoff to ProposalAI works.  
**DoD:** fake-provider e2e and handoff smoke.  
**Repo impact:** `freelancer-suite/products/task_finder`, `extensions/task-finder-ce`.  
**Non-goals:** Upwork API integration, automated scraping.

**Implementation notes for assignee:** CE input is pasted listing text or explicit user-selected page text only; no background scraping, no marketplace API and no automated crawling. Define max input size, selected-text permission behavior, extracted task schema, fit score schema, recommended angle schema and exact fields handed off to ProposalAI.

**LLM runtime alignment:** Task Finder product code and CE remain input/UX/config layers only. Extraction, classification, scoring, and angle generation all use generic atom workflows with `provider_policy_ref`; no marketplace-specific provider tuning, direct LiteLLM calls, custom PydanticAI agents, or provider/model choice in extension code.

### B08. Brief Decoder Product

**Priority:** P1  
**Depends on:** B01, B06  
**Goal:** decode brief into structured project understanding and next steps.  
**Implementation details:** workflow A01 + A04 + A05 + A10. Output: goals, requirements, deliverables, risks, missing info, clarifying questions, generated summary document.  
**Acceptance criteria:** handoffs to Scope Guard and Acceptance Builder use structured fields, not raw text only.  
**DoD:** product e2e plus two handoff tests.  
**Repo impact:** `freelancer-suite/products/brief_decoder`, `extensions/brief-decoder-ce`.  
**Non-goals:** file/PDF parsing.

**Implementation notes for assignee:** Brief Decoder outputs must include structured fields reusable by Scope Guard and Acceptance Builder, not only a generated text summary. Define output schema for goals, requirements, deliverables, risks, missing info, clarifying questions and summary document, plus two handoff mappings; do not implement file/PDF parsing or custom backend parsing endpoints.

**LLM runtime alignment:** Brief Decoder structured fields are product schemas validated through the shared action executor and final platform validator. Keep file parsing, prompt behavior, and output structure in product config; do not add custom backend parsing endpoints, PydanticAI imports, LiteLLM imports, or provider/model settings.

### B09. Case Study Product

**Priority:** P2  
**Depends on:** B01  
**Goal:** generate case-study style artifact from project notes.  
**Implementation details:** workflow A01 + A09 + A07 + A10. Input: project notes/outcome/client context. Output: headline, narrative, bullets, CTA/reply variant.  
**Acceptance criteria:** renderer supports generated document plus copyable snippets.  
**DoD:** fake-provider smoke fixture.  
**Repo impact:** `freelancer-suite/products/case_study`, `extensions/case-study-ce`.  
**Non-goals:** portfolio hosting.

**Implementation notes for assignee:** this is a thin artifact generator, not portfolio hosting or content management. Define structured sections (`headline`, `problem`, `approach`, `result`, `proof_points`, `cta`, `reply_variant`), renderer expectations, copyable snippets and fake fixtures for sparse/complete notes; no hosting pages, media upload or persistent portfolio model.

**LLM runtime alignment:** Case Study remains a thin configured workflow over generic atoms. Product prompts/schemas can define narrative sections, but provider/model choice, validation retry, transport retry, provider-call ledger rows, and raw provider artifacts stay in MVP-A runtime boundaries.

### B10. Persuasion Lens Product

**Priority:** P2  
**Depends on:** B01  
**Goal:** thin persuasion analysis and rewrite product.  
**Implementation details:** workflow A03 + A04 + A09 + A08 + A06. Output: multidimensional scores, issues, recommended angle, rewrite variants, final persuasive version.  
**Acceptance criteria:** all five atoms run sequentially through generic workflow; no custom backend code.  
**DoD:** smoke tests for low-score and high-score paths.  
**Repo impact:** `freelancer-suite/products/persuasion_lens`, `extensions/persuasion-lens-ce`.  
**Non-goals:** deep analytics dashboard.

**Implementation notes for assignee:** the workflow must prove five generic atoms can compose without custom backend code. Define scoring axes, issue taxonomy, angle schema, rewrite variant count/limits, final persuasive output schema and low/high score fixtures; do not add analytics dashboard, custom scoring engine or product-specific action implementation.

**LLM runtime alignment:** Persuasion Lens is the stress test for composing multiple structured LLM actions without runtime leakage. Each atom must use the shared executor and ProviderGateway, with product-specific axes/taxonomies as config/schema only and no direct PydanticAI, LiteLLM, provider SDK, or model-string usage in product code.

### B11. Product Events And Evaluation Fixtures

**Priority:** P1  
**Depends on:** B02-B05 minimum  
**Goal:** сделать MVP-B deterministic and measurable.  
**Implementation details:** event naming: `freelancer.<product>.<event>`; fixtures under `tests/fixtures/freelancer/<product>`. Each P0/P1 product gets happy-path and weak-input fixture.  
**Acceptance criteria:** open/start/result_copied/handoff/email events emitted where relevant; fixtures documented.  
**DoD:** tests assert product events and fixture outputs; event catalog updated.  
**Repo impact:** `freelancer-suite/shared/events.yaml`, `tests/fixtures`, `docs/generated/event-catalog.md`.  
**Non-goals:** full prompt benchmark suite.

**Implementation notes for assignee:** product events extend platform taxonomy but must preserve common dimensions: product_id, frontend_id, scenario_session_id, job_id, artifact_id and handoff_id where relevant. Define event schema validation, required events per P0/P1 product, fixture naming conventions and expected outputs; do not build a full prompt benchmark or scoring harness.

**LLM runtime alignment:** product events and evaluation fixtures are not a substitute for `provider_calls`. Fixtures may assert deterministic fake-provider outputs and product events, but provider attempt accounting, token/cost metadata, validation retries, and transport retries remain kernel-level ledger concerns.

### B12a. MVP-B P0/P1 Product QA

**Priority:** P0  
**Depends on:** B02-B08, B11  
**Goal:** validate primary Freelancer bundle flows.  
**Implementation details:** QA ProposalAI, Acceptance Builder, Scope Guard, Send-Ready, Task Finder, Brief Decoder and main handoffs.  
**Acceptance criteria:** products install/open/run/copy; quota states work; configured handoffs work.  
**DoD:** QA evidence linked in Linear; failures converted to blocking tickets.  
**Repo impact:** `tests/e2e`, `extensions/*-ce`, `freelancer-suite/products`.  
**Non-goals:** P2 polish.

**Implementation notes for assignee:** create a QA matrix for ProposalAI, Acceptance Builder, Scope Guard, Send-Ready, Task Finder and Brief Decoder covering install/open/run/progress/result/copy/quota/email/handoff. Define fake-provider vs real-provider scope, browser/version expectations, evidence format and severity rules; P2 polish is not part of this gate.

**LLM runtime alignment:** QA must distinguish fake-provider product smoke from any optional real-provider validation. If real-provider checks run, they must go through ProviderGateway and verify provider-call rows; CEs must still show no provider/model controls and no bundled prompts, PydanticAI settings, LiteLLM settings, or provider SDK usage.

### B12b. MVP-B P2 Product QA

**Priority:** P2  
**Depends on:** B09, B10  
**Goal:** validate Case Study and Persuasion Lens as thin beta products.  
**Implementation details:** run happy path, weak input, result rendering, copy behavior.  
**Acceptance criteria:** both CEs build and run with fake fixtures.  
**DoD:** QA notes and known limitations documented.  
**Repo impact:** `extensions/case-study-ce`, `extensions/persuasion-lens-ce`, product configs.  
**Non-goals:** deep UX polish.

**Implementation notes for assignee:** validate Case Study and Persuasion Lens as beta-thin products with happy path, weak input, renderer and copy behavior. Document known limitations and decide whether failures block release only if they reveal shared kernel/ce-kit/handoff regressions; deep UX polish and expanded product analytics are out of scope.

**LLM runtime alignment:** P2 QA uses the same runtime boundary as P0/P1: fake fixtures by default, optional real-provider runs only through ProviderGateway, and no CE/product code access to provider/model selection or PydanticAI/LiteLLM internals. Runtime failures should be classified as kernel issues, not product workarounds.

### B12c. No-core-change Audit And Release Notes

**Priority:** P0  
**Depends on:** B12a  
**Goal:** prove MVP-B validated the kernel boundary.  
**Implementation details:** audit diff since MVP-A: no Freelancer code in `platform-core`, no product-specific backend endpoints, no prompts in extensions, no provider selection in CE.  
**Acceptance criteria:** all product configs load; CEs build; handoff smoke passes; architecture tests enforce boundary.  
**DoD:** release notes include known limitations and explicit "core changes: none / approved bugfix list".  
**Repo impact:** `tests/architecture`, `docs/quality-score.md`, `docs/product-specs/mvp-b-freelancer-validation-bundle.md`.  
**Non-goals:** implementing new products or kernel features.

**Implementation notes for assignee:** audit diff since MVP-A and classify every core touch as none, approved kernel bugfix or boundary violation. Run/import architecture tests for no Freelancer code in `platform-core`, no product endpoints, no prompts in extensions and no provider selection in CE; release notes must include exact product list, handoff coverage, known limitations and no new product/kernel implementation.

**LLM runtime alignment:** release audit must explicitly include no PydanticAI imports in product-platforms/extensions, no LiteLLM or provider SDK imports outside provider boundaries, no LiteLLM-format model strings outside provider policy/model registries, no product-owned retry policy overrides, and no product-specific bypass of ProviderGateway or `StructuredLlmActionExecutor`.
