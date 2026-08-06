# MVP-A1 Atom Runtime Proof

## Goal

Build and prove the minimum product-neutral AnytoolAI backend runtime that can launch all 11 typed
atoms individually and in config-defined composite workflows.

MVP-A1 answers one question:

```text
Can the backend read product/scenario/workflow/action config, create scenario_session_id, run every
generic atom and composite chain through the real worker/provider path, store auditable artifacts and
events, and return a frontend-safe result without depending on web or Chrome UI?
```

MVP-A1 is not ProposalAI, Send-Ready, Brief Decoder, or any other Freelancer product. Freelancer
Suite is absent except for package placeholders that are not imported by the kernel. Shared client
delivery belongs to MVP-A2 Client Surfaces.

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
-> Frontend-safe Result API
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

Registries may be read-only and loaded from repo YAML/Markdown. Runtime editing and admin UI are not part of MVP-A1.

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

### Access-Lite Backend

- guest identity
- guest quota
- quota exhausted state
- email capture and waitlist/paywall intent remain Platform Core backend contracts, but they are
  MVP-A2 enablement and do not gate the Atom Runtime Proof

This validates:

```text
guest usage -> quota exhausted -> email capture -> waitlist/paywall intent -> early access
```

Guest quota is enforced by the backend. The API creates opaque guest ids, frontends may store those
ids locally, and quota is consumed only when the backend accepts a scenario start by committing the
started scenario session and linked created job. Quota is not tied to frontend clicks, provider-call
count, retries, or LLM telemetry.

A13 delivers this backend guest identity/quota behavior. A15a/A15b in MVP-A2 delivered the CE-kit
integration: shared client storage, real `getQuota()`, idempotent `startScenario()`, bounded session
polling, guest-id propagation, and typed frontend handling for `429 quota_exhausted`.

### Continuity And Handoff Backend

- product handoff entity
- handoff token
- safe preview and accept/decline API
- `source_scenario_session_id`
- `target_scenario_session_id`
- link between source and target sessions through `handoff_id`

The implemented backend remains Platform Core-owned. API-only handoff E2E is tracked separately and
does not gate the MVP-A1 Atom Runtime Proof.

### Proof Surface

- frontend-safe `GET /v1/results/{artifact_id}`
- eleven deterministic standalone scenarios
- three composite workflows covering all 11 atoms
- `python scripts/agent/runner.py atoms-proof`
- credentialed live-provider canary, separate from baseline CI

Web mirror, shared CE-kit, kernel-demo CE, consent, paywall/onboarding, and browser smoke belong to
MVP-A2. MVP-B products each get separate product-owned Chrome Extensions.

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
- web mirror, Chrome Extension, or browser automation as an MVP-A1 release dependency

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

## Minimal MVP-A1 API

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

The required Atom Runtime Proof subset is scenario start/polling plus
`GET /v1/results/{artifact_id}`. Email/paywall, client-event, and handoff endpoints remain Platform
Core contracts but do not gate MVP-A1.

The handoff endpoints implement an opaque 30-minute token, safe mapped preview, guarded
created/viewed/accepted/declined/consumed/expired/failed lifecycle, and explicit source/target
session linkage. Accept always creates the target session; config decides whether a target job is
queued immediately or deferred.

## Definition Of Done

MVP-A1 Atom Runtime Proof is done when:

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
- All 11 atom action types are registered and runnable.
- Every atom passes one production-shaped deterministic standalone scenario.
- Three neutral composite workflows cover all 11 atoms with real input/output mappings.
- The frontend-safe result API returns only normalized canonical artifacts.
- `atoms-proof` reports 11/11 standalone and 3/3 composite evidence with runtime ledger checks.
- A recent manual live-provider canary proves schema-valid output for all 11 atoms.
- The completion gate has no dependency on CE-kit, web mirror, Chrome, consent, or email/paywall UI.

The most important acceptance criterion: a Freelancer product bundle can be added without changing
`platform-core`; its Chrome Extension consumes MVP-A2 CE-kit contracts without making web mirror a
prerequisite.
