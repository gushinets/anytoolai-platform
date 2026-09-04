# Core Beliefs

## 1. Platform first, products second

MVP-A1 proves Platform Kernel without a UI dependency. MVP-A2 delivers shared client contracts and
the multi-product web host. MVP-B validates web-first product bundles on top of those contracts;
dedicated Chrome Extensions are optional product surfaces.

## 2. Backend-defined workflows

Frontends call approved scenarios only. Frontends do not choose action chains, prompts, providers, or models.

## 3. Actions are stateless, scenarios are stateful

Action implementations do not own scenario state. Scenario state belongs to Platform Runtime.

## 4. Product-specific meaning stays out of Platform Core

No FreelancerProfile, Proposal, Brief, ScopeCreep, AcceptanceDocument, CaseStudy, Upwork, or Gmail-specific semantics inside platform-core.

## 5. Runtime state goes to PostgreSQL, definitions go to config

In MVP, definitions are YAML/Markdown and runtime state is database-backed.

## 6. Every scenario has scenario_session_id

No scenario_session_id, no user journey.

## 7. Event log is not optional

Every important runtime transition emits an event.

## 8. Handoff is backend-owned and user-confirmed

No direct trusted CE-to-CE raw data transfer.

## 9. Typed contracts at boundaries

No YOLO JSON probing. Validate input/output at boundaries.

## 10. Agent legibility beats cleverness

Prefer boring, explicit, searchable code over clever abstractions. Agents should be able to read the repo and understand the domain.

## 11. Scope protection beats premature product pull

Do not build MVP-A "like ProposalAI" or any other Freelancer product. First prove the kernel can run
the need as a config-defined workflow; product meaning belongs in MVP-B. A capability inventory is
not a release plan, and shared UI abstractions are extracted only after a second product proves the
repetition.
