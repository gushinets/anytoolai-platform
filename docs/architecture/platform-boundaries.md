# Platform Boundaries

Platform Core is product-neutral. It may know runtime identifiers such as `product_id`, `frontend_id`, `scenario_id`, `scenario_session_id`, `workflow_id`, `workflow_version`, `action_type`, `action_config_id`, `prompt_ref`, `provider_policy_ref`, `job_id`, `artifact_id`, `handoff_id`, `guest_id`, `tenant_id`, `region`, and `event_type`.

It must not know product semantics such as ProposalAI, Brief, Upwork, Scope Creep, or Acceptance Document.

## Allowed in platform-core

- identity/guest identity
- product registry mechanics
- scenario sessions
- workflow runner
- action runner
- provider gateway
- artifacts
- events
- quotas
- handoffs

## Forbidden in platform-core

- FreelancerProfile
- ExternalTask
- Proposal
- Brief
- ScopeCreep
- AcceptanceDocument
- CaseStudy
- RhetoricalAnalysis
- Upwork/Gmail-specific logic
- client message
- proposal angle
- send-ready verdict
- `generate_proposal` as a platform action type
- product prompts

Everything that knows Freelancer product meaning belongs in MVP-B Freelancer Suite. Everything that
runs atoms, workflows, scenario sessions, events, artifacts, quota, and backend handoff belongs in
MVP-A1 Platform Core. Frontend-safe result consumption, CE-kit, web mirror, shared handoff consent,
and Kernel Demo CE/browser proof belong in MVP-A2 Client Surfaces; the result/artifact API and
backend state remain owned by Platform Core.

Each Freelancer product owns its product bundle/workflow and a separate Chrome Extension. Product
extensions use CE-kit and contain no prompts, provider/model selection, or workflow logic. They do
not depend on the web mirror.

## Composition

`apps/platform-api` wires platform runtime and product bundles. Product bundles use `platform-sdk`.
