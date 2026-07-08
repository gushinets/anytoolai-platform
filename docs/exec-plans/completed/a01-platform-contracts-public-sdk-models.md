# Execution Plan: A01 Platform Contracts And Public SDK Models

## Status

- State: completed
- Owner: agent
- Created: 2026-06-15
- Last updated: 2026-06-15

## Goal

Implement product-neutral typed contracts for the MVP-A kernel runtime so current `kernel_demo`
definition YAML parses into stable public SDK models, with matching internal core model field
names and validation coverage.

## Scope

### In scope

- Public Pydantic v2 DTOs in `platform-sdk/contracts`.
- Mirrored field-compatible internal models in `platform-core`.
- Closed enums for current frontend types, execution modes, quota values, and runtime statuses.
- Tests for valid configs, required fields, invalid enums, metadata handling, and forbidden product terms.
- `docs/architecture/config-model.md` update.

### Out of scope

- Registry loading.
- SQLAlchemy runtime models or migrations.
- API endpoints.
- Human-in-the-loop runtime behavior.
- Product-specific Freelancer semantics.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/config-model.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/handoff-model.md`
- `docs/architecture/event-taxonomy.md`

## Contracts touched

- API: none.
- DB: none.
- Config: product, frontend, scenario, workflow, action definition, action configuration, prompt ref, provider policy, quota policy, handoff definition.
- Events: `EventEnvelope` DTO only.
- Frontend: public SDK/frontend config contracts only.

## Implementation steps

- [x] Add pinned SDK dependency using `uv` and update lock state if available.
- [x] Implement public SDK contract models and exports.
- [x] Implement mirrored platform-core models without SDK imports.
- [x] Add SDK/core/architecture tests.
- [x] Update config model docs.
- [x] Run uv-based validation commands.

## Validation

- [x] `uv run python scripts/agent/runner.py validate-configs`
- [x] `uv run python scripts/agent/runner.py validate-architecture`
- [x] `uv run python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-15 | Use `pydantic==2.13.4` in `platform-sdk`. | Public DTOs need runtime validation and exact dependency pinning. |
| 2026-06-15 | Keep core models separate from SDK models. | Avoid public/internal coupling and import cycles while preserving field compatibility. |
| 2026-06-15 | Keep enums closed per SDK version. | Future values such as mobile frontends or human-input job statuses should be explicit additive contract updates. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-15 | Plan created from A01 implementation request. | Run doctor, then implement models/tests/docs. |
| 2026-06-15 | Implemented SDK/core contract models, tests, docs, and uv lockfile. | Ready for review. |

## Open questions

None.

## Follow-up debt

- Future human-in-the-loop work must add statuses plus runtime transitions, timeout handling, APIs, events, and persistence in a separate task.
