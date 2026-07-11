# MVP Scope Source Of Truth

This file mirrors the controlling concept document for AnytoolAI MVP-A and MVP-B scope:

```text
D:\Work\AI\AnytoolAI\platform concept\anytoolai-mvp-a-platform-kernel-and-mvp-b-freelancer-validation-bundle.md
```

Keep `AGENTS.md`, `ARCHITECTURE.md`, `docs/**`, configs, tests, and scaffold aligned with this summary. The external concept file remains the source for nuance; this repo-local file exists so future agents can work from repository context.

## Core Split

MVP-A is Platform Kernel: the smallest platform runtime that can launch typed atom actions, workflows, scenario sessions, artifacts, events, guest quota, email capture/paywall intent, handoff, web mirror, and CE kit.

MVP-B is Freelancer Validation Bundle: thin CE-first Freelancer products added on top of the kernel through product configs, prompts, schemas, workflows, result renderers, handoff maps, product events, and separate Chrome Extensions.

If the first real Freelancer CE cannot be added without changing `platform-core`, MVP-A is not complete.

## MVP-A Runtime Flow

```text
Product Definition
-> Scenario Session
-> Workflow Definition
-> Action Configurations
-> Atomic Actions
-> Provider Gateway
-> Structured Output
-> Artifact
-> Event Log
-> Guest Quota
-> Email Capture / Waitlist Intent
-> Handoff
-> Web Mirror / CE Kit
```

Every user journey starts with `scenario_session_id`.

## MVP-A In Scope

- config loader
- product, frontend, scenario, workflow, action, prompt, and provider policy registries
- scenario session runtime
- workflow runner
- action runner
- job model and action run model
- provider call logging
- structured output validation
- artifact storage
- event log
- guest identity and guest quota
- quota exhausted state
- email capture
- waitlist/paywall intent
- backend-owned handoff token flow
- minimal web mirror
- shared `ce-kit`
- `kernel-demo-ce`

## MVP-A Out Of Scope

- real Freelancer products as user releases
- eight production Chrome Extensions
- admin panel
- billing, Stripe, YooKassa, subscriptions, wallets, ledger
- registered auth via OTP or magic link
- Talent OS
- dashboards
- DSPy as required runtime
- Content Critic
- Spanish Accent Tutor
- file, audio, or video processing
- CRM
- visual workflow builder
- full multitenancy
- full regional deployment
- product-specific domain tables

## Product-Neutral Action Types

All 11 action types must be registered and runnable through the generic action runner.

| Old atom | MVP-A action type |
|---|---|
| A01 `extract_structured` | `text.extract_structured_fields` |
| A04 `detect_issues` | `text.detect_issues_by_taxonomy` |
| A07 `generate_reply` | `text.compose_reply` |
| A09 `generate_angle` | `text.synthesize_angle` |
| A10 `generate_document` | `document.generate_from_template` |
| A11 `compare_classify` | `text.compare_and_classify` |
| A02 `score_match` | `text.score_match_by_rubric` |
| A06 `generate_proposal` | `text.compose_persuasive_text` |
| A08 `generate_rewrites` | `text.generate_gap_rewrites` |
| A03 `score_multidim` | `text.score_multidimensional_axes` |
| A05 `generate_questions` | `text.generate_clarifying_questions` |

`generate_proposal` must not become a platform action type. ProposalAI uses `text.compose_persuasive_text` through a product-specific action config.

## Forbidden In MVP-A Platform Core

Platform Core must not contain product semantics such as:

- `FreelancerProfile`
- `ExternalTask`
- `Proposal`
- `Brief`
- `ScopeCreep`
- `AcceptanceDocument`
- `CaseStudy`
- `RhetoricalAnalysis`
- `Upwork`
- `Gmail compose`
- `client message`
- `proposal angle`
- `send-ready verdict`

Platform Core may know only neutral runtime identifiers such as `product_id`, `frontend_id`, `scenario_id`, `scenario_session_id`, `workflow_id`, `workflow_version`, `action_type`, `action_config_id`, `prompt_ref`, `provider_policy_ref`, `job_id`, `artifact_id`, `handoff_id`, `guest_id`, `tenant_id`, `region`, and `event_type`.

## Runtime State

Definitions live in YAML/Markdown in the repo. Runtime state lives in PostgreSQL.

MVP-A runtime tables:

- `platform.scenario_sessions`
- `platform.jobs`
- `platform.action_runs`
- `platform.provider_calls`
- `platform.artifacts`
- `platform.event_log`
- `platform.guest_identities`
- `platform.guest_quota_usage`
- `platform.email_captures`
- `platform.paywall_intents`
- `platform.product_handoffs`

Do not add DB tables for products, workflow definitions, action definitions, action configurations, prompt versions, subscriptions, wallets, ledger entries, or admin users in MVP-A.

## Minimal API

```text
POST /v1/identity/guest
GET  /v1/products/{product_id}/quota
POST /v1/email-captures
POST /v1/paywall-intents

GET  /v1/products/{product_id}/runtime-config
POST /v1/products/{product_id}/scenarios/{scenario_id}/start
GET  /v1/scenario-sessions/{scenario_session_id}
POST /v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id}

GET /v1/jobs/{job_id}
GET /v1/artifacts/{artifact_id}
GET /v1/results/{artifact_id}

POST /v1/handoffs
GET  /v1/handoffs/{handoff_token}
POST /v1/handoffs/{handoff_token}/accept
POST /v1/handoffs/{handoff_token}/decline

POST /v1/client-events
```

## Kernel Demo

`kernel_demo` is an internal smoke-test product only. It is not a user product and not part of Freelancer Suite.

Required smoke scenarios:

- `kernel_demo.single_action_smoke_v1`
- `kernel_demo.multi_step_workflow_smoke_v1`
- `kernel_demo.quota_exhausted_smoke_v1`
- `kernel_demo.handoff_smoke_v1`, implemented as source and target sessions where useful

The multi-step smoke workflow should exercise:

```text
text.extract_structured_fields
-> text.detect_issues_by_taxonomy
-> document.generate_from_template
```

## CE Kit

MVP-A needs shared `packages/frontend/ce-kit`; MVP-B must not copy API/job/quota/handoff code across CEs.

Required kit capabilities:

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

## Web Mirror

MVP-A web mirror pages:

- `/r/{artifact_id}`
- `/handoff/{handoff_token}`
- `/paywall/{product_id}`
- `/onboarding/{product_id}`

Web mirror must not become a user dashboard.

## Event Taxonomy

MVP-A platform events:

- `guest.created`
- `product.opened`
- `quota.checked`
- `quota.consumed`
- `quota.exhausted`
- `email_capture.submitted`
- `paywall.shown`
- `waitlist.intent_submitted`
- `scenario.started`
- `scenario.checkpoint_reached`
- `scenario.completed`
- `scenario.failed`
- `workflow.started`
- `workflow.canceled`
- `workflow.succeeded`
- `workflow.failed`
- `action.started`
- `action.succeeded`
- `action.failed`
- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`
- `artifact.created`
- `handoff.created`
- `handoff.viewed`
- `handoff.accepted`
- `handoff.declined`
- `handoff.consumed`
- `client.result_copied`
- `client.next_action_clicked`

Product-specific events begin in MVP-B.

## Development Sequence

1. Contracts and config loader.
2. Runtime storage and event log.
3. Provider gateway and structured output.
4. Action runner and first atom definitions.
5. Workflow runner.
6. Scenario runtime.
7. Guest quota and email capture.
8. Handoff core.
9. Web mirror, CE kit, and kernel demo CE.
10. All 11 atom definitions.

## MVP-A Definition Of Done

MVP-A is complete when:

- backend starts and validates configs
- runtime DB tables exist for sessions, jobs, actions, artifacts, and events
- generic action runner exists
- provider gateway exists
- structured output validation exists
- workflow runner exists
- every scenario start creates `scenario_session_id`
- artifact storage exists
- event log exists
- guest quota exists
- email capture exists
- paywall/waitlist intent exists
- handoff token flow exists
- web mirror supports result and handoff
- shared CE kit exists
- kernel demo CE exists
- all 11 atom action types are registered and runnable
- one-action smoke workflow exists
- three-action smoke workflow exists
- smoke handoff links source session to target session

## MVP-B Scope

MVP-B adds product-level assets only:

- product configs
- product prompts
- product schemas
- product workflows
- product-specific action configs
- CE wrappers
- CE product UX
- result renderers
- handoff maps
- product events

MVP-B must not change `platform-core`. It is undesirable for MVP-B to change workflow runner, action runner, provider/scenario/event/quota/handoff kernel modules, or to add product-specific backend endpoints.

## MVP-B Products And Order

1. ProposalAI: `A06` / `text.compose_persuasive_text`
2. Acceptance Builder: `A01 + A07 + A10`
3. Case Study + Upsell: `A01 + A09 + A07 + A10`
4. Scope Guard: `A01 + A04 + A11 + A07`
5. Task Finder: `A01 + A11 + A02 + A09`
6. Send-Ready: `A04 + A11 + A02 + A08`
7. Brief Decoder: `A01 + A04 + A05 + A10`
8. Persuasion Lens: `A03 + A04 + A09 + A08 + A06`

ProposalAI is the first real MVP-B product after the kernel because it uses one workflow and one atom, proves the CE path quickly, and gives a clear `result copied` aha moment.

## Scope Protection

Do not say: "Let's build this like ProposalAI / Send-Ready / Brief Decoder."

Say: "Let's verify whether the kernel can run this as a config-defined workflow."

Everything that knows Freelancer product meaning belongs in MVP-B. Everything that runs atoms, workflows, scenario sessions, events, artifacts, quota, and handoff belongs in MVP-A.
