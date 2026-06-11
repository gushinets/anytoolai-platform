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

Everything that knows Freelancer product meaning belongs in MVP-B. Everything that runs atoms, workflows, scenario sessions, events, artifacts, quota, and handoff belongs in MVP-A.

## Composition

`apps/platform-api` wires platform runtime and product bundles. Product bundles use `platform-sdk`.
