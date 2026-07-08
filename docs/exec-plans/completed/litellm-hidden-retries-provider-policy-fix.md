# Execution Plan: LiteLLM Hidden Retries Provider Policy Fix

## Status

- State: completed
- Owner: agent
- Created: 2026-07-02
- Last updated: 2026-07-02

## Goal

Make the default provider policy comply with ADR-0007 so one ProviderGateway physical attempt
maps to one `platform.provider_calls` row with no hidden LiteLLM SDK retries.

## Scope

### In scope

- Fix `configs/kernel/provider_policies.yaml` so `default_text_generation_v1` sets
  `retry_policy.transport.litellm_num_retries_per_attempt` to `0` exactly once.
- Enforce MVP-A validation that rejects non-zero LiteLLM per-attempt retries.
- Reject duplicate YAML keys in config validation so silent override bugs cannot bypass policy
  checks.
- Realign unit tests around ProviderGateway-owned retry accounting.

### Out of scope

- Changing ProviderGateway retry semantics beyond enforcing the existing ADR-0007 contract.
- Enabling fallback/routing behaviors beyond the current MVP-A scope.
- Broad YAML-loader refactors outside the config-validation path.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`

## Contracts touched

- Config: `configs/kernel/provider_policies.yaml`
- Config validation: `ConfigLoader` YAML parsing and provider retry-policy validation
- Runtime: LiteLLM adapter request behavior under ProviderGateway-owned attempts
- Tests: config loader, provider gateway, and LiteLLM adapter unit coverage

## Implementation steps

- [x] Add duplicate-key detection to the config YAML loading path.
- [x] Remove the conflicting retry value from `default_text_generation_v1` and pin the effective
      LiteLLM per-attempt retry count to `0`.
- [x] Ensure the strict provider retry-policy parser is the only active parser in
      `ConfigLoader`.
- [x] Update tests to assert zero hidden retries and rejection of invalid retry config.
- [x] Run config validation, targeted unit tests, and quick-check.

## Validation

- [x] `python scripts/agent/validate_configs.py`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_config_loader.py -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-02 | Reject duplicate YAML keys in the config-loader path | Silent key overwrite can defeat config-contract enforcement, including retry accounting rules. |
| 2026-07-02 | Keep LiteLLM `num_retries` fixed at `0` per ProviderGateway attempt in MVP-A | ADR-0007 requires one provider-call row per physical attempt and keeps retry ownership in ProviderGateway/PydanticAI. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-02 | Inspected config loader, provider gateway, and tests; found a duplicate `_parse_provider_retry_policy()` definition that overrides the strict validator. | Remove the permissive duplicate parser, add duplicate-YAML-key detection, and realign tests. |
| 2026-07-02 | Removed the permissive parser override, added duplicate-key YAML rejection, set the default LiteLLM retry count to `0`, and passed config validation, targeted unit tests, and quick-check. | No further work for this fix. |

## Open questions

- None at the moment.

## Follow-up debt

- Consider reusing the duplicate-key YAML guard in other repo YAML readers that are outside the
  config-validation path if those files become contract-critical.
