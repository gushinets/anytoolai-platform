# Execution Plan: Document LLM Runtime Decisions

## Status

- State: active
- Owner: agent
- Created: 2026-06-23
- Last updated: 2026-06-23

## Goal

Promote the PydanticAI + LiteLLM SDK runtime decisions from planning conversation into repository-local, searchable, mechanically enforced documentation so future Codex/agent runs can implement MVP-A without relying on external chat history.

## Scope

### In scope

- Update root agent map with the accepted LLM runtime decision.
- Add architecture documentation for the PydanticAI / LiteLLM SDK split.
- Record an ADR for the decision.
- Cross-link the decision from the repository knowledge map.
- Clarify Provider Gateway, structured-output, action-model, and package-layering boundaries.
- Add architecture validation for forbidden direct LLM/provider imports.

### Out of scope

- Installing `pydantic-ai-slim` or `litellm`.
- Implementing `StructuredLlmActionExecutor`.
- Implementing the LiteLLM SDK ProviderGateway adapter.
- Changing database migrations.
- Running real provider calls.

## Relevant docs

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/action-model.md`
- `docs/architecture/package-layering.md`
- `docs/adr/0004-llm-runtime-pydanticai-litellm-sdk.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none.
- DB: documentation only; `platform.provider_calls` semantics clarified as one row per ProviderGateway physical attempt.
- Config: provider policy retry fields documented, not implemented.
- Events: provider request events referenced, not changed.
- Frontend: no runtime change; frontend remains forbidden from provider/model choice.

## Implementation steps

- [x] Create branch `docs/llm-runtime-decisions`.
- [x] Update `AGENTS.md` first with the accepted LLM runtime decision and deep-doc pointer.
- [x] Add `docs/architecture/llm-runtime.md` as the detailed source of truth.
- [x] Add ADR 0004 for the library and SDK/proxy decision.
- [x] Update architecture docs that own related boundaries.
- [x] Encode the import boundary in `scripts/agent/validate_architecture.py`.
- [x] Create this execution plan.
- [ ] Open PR for human/agent review.

## Validation

- [ ] `just quick-check`
- [ ] `just validate-configs`
- [ ] `just validate-architecture`
- [ ] `just kernel-smoke`

Local validation was not run in this environment because the repo could not be cloned from GitHub through the container network. The PR is documentation plus a Python architecture-validator update; reviewers should run `just validate-architecture` and `just quick-check` in the normal repo environment.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-23 | Use both PydanticAI and LiteLLM. | PydanticAI fits typed structured output and validation retries; LiteLLM fits provider/model access and future routing/fallback. |
| 2026-06-23 | Use LiteLLM as an in-process SDK for MVP-A. | Avoid an extra service in the first kernel slice while keeping a future proxy path. |
| 2026-06-23 | Disable hidden LiteLLM SDK retries in MVP-A. | Provider-call ledger must stay deterministic: one ProviderGateway physical attempt equals one row. |
| 2026-06-23 | Split retries by failure type. | Avoid retry multiplication between validation and transport layers. |
| 2026-06-23 | PydanticAI owns structured-output retry; AnytoolAI final-validates. | Library ergonomics should not replace platform contracts, artifacts, or user-safe errors. |
| 2026-06-23 | Enforce import boundaries mechanically. | Harness Engineering requires rules to live in docs and validation, not just chat history. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-23 | Added docs, ADR, cross-links, and import-boundary validator changes. | Open PR and run normal repo validation in a connected checkout. |

## Open questions

None for documentation. Implementation follow-up must choose the exact PydanticAI adapter shape for in-process LiteLLM SDK calls.

## Follow-up debt

- Add implementation tests listed in `docs/architecture/llm-runtime.md`.
- Add provider policy schema changes for split retry budgets.
- Add `pydantic-ai-slim` and `litellm` through `uv add` during implementation, not in this docs PR.
