# MVP-A1, MVP-A2, And MVP-B Linear Delivery Map

## Status

- State: active
- Owner: product/engineering
- Created: 2026-06-23
- Last updated: 2026-08-06
- Review date: 2026-08-06
- Next action: deliver A20a-c and the MVP-A1 Atom Runtime Proof children.
- Blocker: none

## Delivery Model

- **MVP-A1 — Atom Runtime Proof** is owned by the Linear project
  [Platform Core](https://linear.app/paveldik/project/platform-core-20bcc974a1c7/overview).
- **MVP-A2 — Client Surfaces** is owned by the Linear project
  [Client Surfaces](https://linear.app/paveldik/project/client-surfaces-83fa5c03954f/overview).
- **MVP-B — Freelancer Validation Bundle** is owned by the Linear project
  [Freelancer Suite](https://linear.app/paveldik/project/freelancer-suite-7671004850e2/overview).

Platform Core owns runtime state and frontend-safe backend contracts. Client Surfaces owns shared
CE-kit, web mirror, and shared browser journeys. Freelancer Suite owns product bundles and eight
product-specific Chrome Extensions. Web mirror is not a dependency of MVP-A1 or an individual
Freelancer product.

LLM runtime rules apply across all projects: PydanticAI only inside the structured executor,
LiteLLM only behind ProviderGateway adapters, hidden LiteLLM retries disabled, and one
`provider_calls` row per physical attempt.

## MVP-A1 — Atom Runtime Proof

### Delivered Foundation

| Slice | Linear | State |
|---|---|---|
| A01 Platform contracts | ANY-14 | Done |
| A02 Config loader | ANY-46 | Done |
| A03 Canonical checks | ANY-44 | Done |
| A04 Runtime storage | ANY-19 | Done |
| A05 Event log | ANY-34 | Done |
| A06 API bootstrap | ANY-33 | Done |
| A07 Provider Gateway/fake provider | ANY-40 | Done |
| A08 Structured output | ANY-50 | Done |
| A09 Action runner/first atoms | ANY-13 | Done |
| A10 Sequential workflow runner | ANY-15 | Done |
| A11 Job/worker lifecycle | ANY-31 | Done |
| A12 Scenario runtime API | ANY-22 | Done |
| A13 Guest identity/quota | ANY-23 | Done |
| A17 Backend handoff core | ANY-20 | Done |

### Required Proof Work

| Slice | Linear | Depends on |
|---|---|---|
| A12b Frontend-safe result API | ANY-217 | ANY-22 |
| A20a Reply/document/questions atoms | ANY-37 | ANY-13 |
| A20b Scoring/classification atoms | ANY-49 | ANY-13 |
| A20c Persuasion/angle/rewrite atoms | ANY-45 | ANY-13 |
| A21a Atom Runtime Proof parent | ANY-24 | A12/A13/A20a-c |
| A21a1 11-atom standalone matrix | ANY-218 | ANY-37/49/45/217 |
| A21a2 Composite workflow proof | ANY-219 | ANY-218 |
| A21a3 CLI/evidence report | ANY-220 | ANY-218/219/217 |
| A21a4 Live-provider canary | ANY-221 | ANY-218/220 |
| MVP-A1 release gate | ANY-5 | Done |
| A22b Generated docs | ANY-7 | MVP-A1 gate |
| A22c Boundary audit | ANY-25 | MVP-A1 gate |

The deterministic gate reports 11/11 standalone and 3/3 composite workflows. The live canary is
credentialed manual/scheduled evidence; baseline CI remains credential-free. A14 email/paywall
backend enablement (ANY-36) and A21b backend handoff E2E (ANY-43) remain Platform Core work but do
not block Atom Runtime Proof.

## MVP-A2 — Client Surfaces

| Slice | Linear | State/dependency |
|---|---|---|
| A15 CE-kit parent | ANY-8 | Done |
| A15a client/storage foundation | ANY-170 | Done |
| A15b quota/start/polling | ANY-171 | Done; merged in PR #52 |
| A15c result client | ANY-226 | Done; merged in PR #62 |
| A16 web result/paywall/onboarding | ANY-11 | ANY-217 and ANY-36 |
| A18 client handoff parent | ANY-6 | ANY-8 and ANY-20 |
| A18a handoff CE helpers | ANY-222 | Done |
| A18b web consent surface | ANY-223 | Done |
| A18c client handoff smoke | ANY-224 | Done |
| A19 kernel-demo CE client proof | ANY-39 | ANY-8/222/223 |
| MVP-A2 release gate | ANY-225 | A15/A16/A18/A19 |

Client Surfaces consumes Platform Core contracts and never owns provider/model choice, prompts,
workflow definitions, quota authority, artifact state, or handoff state.

## MVP-B — Freelancer Validation Bundle

B01 (ANY-32) defines the product template and bundle loader. B06 (ANY-26) owns declarative
cross-product handoff maps. B11 (ANY-17) owns shared product events and deterministic fixtures.

Each product parent has exactly three children: bundle/workflow, dedicated Chrome Extension, and
runtime E2E/QA.

| Product parent | Bundle child | CE child | E2E child | Workflow |
|---|---|---|---|---|
| ProposalAI ANY-35 | ANY-227 | ANY-235 | ANY-243 | A06 |
| Acceptance Builder ANY-28 | ANY-228 | ANY-236 | ANY-244 | A01 → A07 → A10 |
| Scope Guard ANY-9 | ANY-229 | ANY-237 | ANY-245 | A01 → A04 → A11 → A07 |
| Send-Ready ANY-12 | ANY-230 | ANY-238 | ANY-246 | A04 → A11 → A02 → A08 |
| Task Finder ANY-10 | ANY-231 | ANY-239 | ANY-247 | A01 → A11 → A02 → A09 |
| Brief Decoder ANY-27 | ANY-232 | ANY-240 | ANY-248 | A01 → A04 → A05 → A10 |
| Case Study ANY-16 | ANY-233 | ANY-241 | ANY-249 | A01 → A09 → A07 → A10 |
| Persuasion Lens ANY-38 | ANY-234 | ANY-242 | ANY-250 | A03 → A04 → A09 → A08 → A06 |

Dependency rules:

- bundle children depend on B01, the MVP-A1 release gate (ANY-5), and the required A20 atom packs;
- CE children depend on their bundle plus A15b/A15c and, where needed, A18a;
- E2E children depend on bundle plus CE and, for configured handoffs, B06/A18c;
- product parents complete only after all three children;
- B12a (ANY-29) depends on P0/P1 E2E children ANY-243…248 and B11;
- B12b (ANY-48) depends on P2 E2E children ANY-249/250;
- B12c (ANY-30) performs the final no-core-change audit.

## Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-08-06 | Split MVP-A into A1 Atom Runtime Proof and A2 Client Surfaces. | Backend proof must not wait for UI delivery. |
| 2026-08-06 | Create Client Surfaces as a separate Linear project. | Shared clients and web journeys have a distinct release gate and ownership boundary. |
| 2026-08-06 | Give every Freelancer product three child slices. | Bundle, CE, and E2E work have different dependencies and completion evidence. |
| 2026-08-06 | Make web mirror optional for product CEs. | Product extensions complete through CE-kit and the frontend-safe result API. |

## Validation

- Linear project/parent/dependency audit.
- `python scripts/agent/runner.py validate-docs`
- `python scripts/agent/runner.py generate-docs --check`
- `python scripts/agent/runner.py validate-architecture`
- `python scripts/agent/runner.py quick-check`
