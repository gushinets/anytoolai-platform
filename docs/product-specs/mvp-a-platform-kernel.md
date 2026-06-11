# MVP-A Platform Kernel

## Goal

Build the minimum AnytoolAI platform runtime that can launch config-defined scenarios and workflows from typed atom actions.

MVP-A answers one question:

```text
Can the backend read product/scenario/workflow/action config, create scenario_session_id, run the chain, store artifacts, emit events, apply quota, and return a frontend-safe result?
```

MVP-A is not ProposalAI, Send-Ready, Brief Decoder, or any other Freelancer product. Freelancer Suite is absent from MVP-A except for package placeholders that are not imported by the kernel.

## Runtime Flow

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

## In Scope

### Platform Core

- config loader
- product registry
- frontend registry
- scenario registry
- workflow registry
- action registry
- prompt registry
- provider policy registry

Registries may be read-only and loaded from repo YAML/Markdown. Runtime editing and admin UI are not part of MVP-A.

### Runtime

- `scenario_session_id`
- workflow runner
- action runner
- job model
- action run model
- provider call logging
- structured output validation
- artifact storage
- event log

Every user-facing run must have `scenario_session_id`. No `scenario_session_id` means no user journey.

### Access-Lite

- guest identity
- guest quota
- quota exhausted state
- email capture
- waitlist/paywall intent

This validates:

```text
guest usage -> quota exhausted -> email capture -> waitlist/paywall intent -> early access
```

### Continuity And Handoff

- product handoff entity
- handoff token
- handoff consent page
- `source_scenario_session_id`
- `target_scenario_session_id`
- link between source and target sessions through `handoff_id`

MVP-A only needs one smoke handoff inside `kernel_demo`.

### Frontend Support

- minimal web mirror
- shared `ce-kit`
- one reference `kernel-demo-ce`

Do not build a unified CE for all products. MVP-B products each get separate Chrome Extensions that use the shared `ce-kit`.

## Out Of Scope

- real Freelancer products as full user releases
- eight production Chrome Extensions
- full admin
- billing
- Stripe / YooKassa
- subscriptions
- registered auth through OTP or magic link
- Talent OS
- dashboards
- DSPy engine as mandatory runtime
- Content Critic
- Spanish Accent Tutor
- file/audio/video processing
- CRM
- visual workflow builder
- full multitenancy
- full regional deployment
- product-specific domain tables

## Required Action Types

All 11 atom action types must be registered and runnable through the generic action runner.

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

`A06 generate_proposal` must not become a platform action type. The platform action is `text.compose_persuasive_text`; ProposalAI uses it through product-specific action config in MVP-B.

## Runtime DB

Definitions live in YAML/Markdown. Runtime state lives in PostgreSQL.

MVP-A tables:

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

Do not create MVP-A tables for product definitions, workflow definitions, action definitions, action configurations, prompt versions, subscriptions, wallets, ledger entries, or admin users.

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

## Definition Of Done

Platform Kernel is done when:

- Backend starts and validates configs.
- Runtime DB tables exist for sessions, jobs, actions, artifacts, and events.
- Generic action runner exists.
- Provider gateway exists.
- Structured output validation exists.
- Workflow runner exists.
- Every scenario start creates `scenario_session_id`.
- Artifact storage exists.
- Event log exists.
- Guest quota exists.
- Email capture exists.
- Paywall/waitlist intent exists.
- Handoff token flow exists.
- Web mirror supports result and handoff.
- Shared `ce-kit` exists.
- `kernel-demo-ce` exists.
- All 11 atom action types are registered and runnable.
- One-action smoke workflow exists.
- Three-action smoke workflow exists.
- Smoke handoff links source session to target session.

The most important acceptance criterion: the first real Freelancer CE can be added without changing `platform-core`.
