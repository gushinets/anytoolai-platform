# Execution Plan: ANY-61 ADR 0007 Provider Policy Backfill

## Status

- State: completed
- Owner: agent
- Created: 2026-06-26
- Last updated: 2026-06-26

## Goal

Align the MVP-A provider policy contracts, kernel config, and config-loader validation with ADR 0007 so retry ownership is explicit, old retry shapes fail fast with structured diagnostics, and non-provider-registry configs cannot carry raw provider/model/LiteLLM request fields.

## Scope

### In scope

- Update SDK and core `ProviderPolicy` contracts to the ADR 0007 split retry shape.
- Update `configs/kernel/provider_policies.yaml` to the new retry structure.
- Strengthen config-loader validation for provider policy shape and forbidden raw provider/model/LiteLLM fields outside provider policy ownership.
- Refresh provider-policy/config-registry docs and generated config docs.
- Add config-loader and contract tests for valid parsing and invalid config rejection.

### Out of scope

- ProviderGateway execution changes beyond contract compatibility.
- Live provider integration or credential work.
- LiteLLM Proxy or fallback routing implementation.
- Broad config-registry redesign beyond this backfill.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/config-model.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/llm-runtime.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`
- `docs/generated/config-registry.md`
- `docs/exec-plans/active/a01-platform-contracts-public-sdk-models.md`
- `docs/exec-plans/active/a02-config-loader-and-registry-validation.md`
- `docs/exec-plans/active/document-llm-runtime-decisions.md`
- `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`

## Contracts touched

- API: none directly.
- DB: none.
- Config: provider policy contract, provider policy YAML, loader validation for products/frontends/scenarios/workflows/action configs/prompts.
- Events: none.
- Frontend: validation only; frontend configs remain forbidden from provider/model choice.

## Implementation steps

- [ ] Replace flat provider-policy retry fields with ADR 0007 split retry contract models in SDK/core.
- [ ] Update config loading to require the split retry shape, reject old retry fields, and enforce MVP-A `litellm_num_retries_per_attempt: 0`.
- [ ] Reject raw provider/model/LiteLLM request fields outside provider policy/model-registry ownership while preserving `provider_policy_ref`.
- [ ] Update kernel provider policy YAML and relevant docs/generated docs.
- [ ] Add regression tests and run config-focused validation plus quick-check.

## Validation

- [ ] `just doctor`
- [ ] `python -m pytest packages/backend/platform-core/tests/unit/test_config_loader.py`
- [ ] `python -m pytest packages/backend/platform-core/tests/unit -k config`
- [ ] `python scripts/validate_configs.py`
- [ ] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-26 | Keep the implementation dependency-free. | The repo already has the needed Pydantic/dataclass/config-error machinery, and this backfill is contract/validation work rather than a new runtime integration. |
| 2026-06-26 | Fail old retry shapes explicitly instead of silently mapping them. | ADR 0007 makes retry ownership part of the source-of-truth registry contract, so ambiguous fields must not keep working. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-26 | Reviewed architecture docs, ADR 0007, A01/A02 plans, generated config docs, current provider-policy YAML, loader code, and loader/contract tests. | Implement contract and loader updates, then refresh docs/tests. |
| 2026-06-26 | `just doctor` could not run because `just` is not installed in this shell (`CommandNotFoundException`). | Use the documented Python fallback commands for validation after implementation and record that constraint in the summary. |

## Open questions

None at the contract level. The current task only needs the config boundary to be explicit enough for future ProviderGateway work.

## Follow-up debt

- Add model-registry-specific validation once a separate model registry exists in repo config.
- Add ProviderGateway/runtime tests for transport-attempt accounting and hard-cap enforcement when A07 lands.
