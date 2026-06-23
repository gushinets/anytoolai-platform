# Execution Plan: A02 Config Loader And Registry Validation

## Status

- State: active
- Owner: agent
- Created: 2026-06-16
- Last updated: 2026-06-23

## Goal

Implement a read-only MVP-A config registry in `platform-core` that loads repo definitions in a
deterministic order, returns immutable objects, fails fast on duplicate ids and broken references,
and is reused by both API startup and `validate_configs.py`.

## Scope

### In scope

- Deterministic config discovery and loader orchestration under `platform-core/config`.
- Read-only registry access for product, scenario, workflow, action configuration, prompt, and
  provider policy definitions.
- Shared validation layer for duplicates, missing references, and missing prompt/schema assets.
- Startup wiring so invalid config aborts API boot before traffic is served.
- Config-shape cleanup in `configs/kernel` where current files do not support strict loading.
- Tests for happy path and required failure modes.

### Out of scope

- DB-backed config storage or any runtime editing path.
- Admin APIs or admin UI.
- Product-specific Freelancer behavior.
- Broader runtime execution work beyond config bootstrap and validation.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/config-model.md`
- `docs/generated/config-registry.md`

## Contracts touched

- API: app startup/bootstrap only; invalid config must prevent serving.
- DB: none.
- Config: kernel defaults, regions, provider policies, action definitions, product configs, prompt
  manifests/assets, schema manifests/assets.
- Events: none.
- Frontend: none directly, but registry output later feeds runtime-config responses.

## Implementation steps

- [ ] Add a `ConfigRegistry` domain object plus a single loader entrypoint in
  `packages/backend/platform-core/src/anytoolai_platform_core/config`.
- [ ] Define immutable internal registry payloads using frozen core models plus immutable container
  normalization for nested lists and mappings.
- [ ] Introduce structured config errors with `file_path`, `config_id`, `ref_type`, and
  `ref_value`, plus duplicate-id and missing-file variants.
- [ ] Implement deterministic load order:
  `default_tenant` -> `regions` -> `provider_policies` -> `action_definitions` -> product folders
  -> prompt/schema manifests and assets -> cross-reference validation.
- [ ] Normalize `configs/kernel` ownership rules so each definition type has one owning file or
  manifest and no silent merge behavior.
- [ ] Add explicit prompt and schema manifests instead of inferring ids from filenames.
- [ ] Remove loader fallback from `product.yaml` for `frontends` and `analytics`; dedicated child
  files own those definitions.
- [ ] Require explicit `quota_policy_ref` whenever `quotas.yaml` defines quota policies.
- [ ] Require explicit provider-policy tuning fields in repo config instead of loader defaults.
- [ ] Replace the ad hoc `scripts/agent/validate_configs.py` logic with the shared loader or the
  same validation layer.
- [ ] Wire API/bootstrap startup to build the registry before the app can serve requests.
- [ ] Add focused unit/integration tests for valid load and each required failure mode.
- [ ] Refresh generated/config docs if they describe loader paths or validation guarantees.

## Validation

- [ ] `.venv\Scripts\python.exe scripts/agent/runner.py validate-configs`
- [ ] `.venv\Scripts\python.exe scripts/agent/runner.py validate-architecture`
- [ ] `.venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests`
- [ ] `.venv\Scripts\python.exe -m pytest apps/platform-api/tests`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-16 | Keep the registry in `platform-core/config` and expose it through app/bootstrap wiring only. | The registry is kernel infrastructure and must remain product-neutral; `apps/platform-api` is the composition root that decides when it is loaded. |
| 2026-06-16 | Use one shared loader/validation path for both startup and `validate_configs.py`. | Prevents drift between CI validation and runtime behavior. |
| 2026-06-16 | Make prompt and schema ids explicit through manifests, not filename inference. | Current refs already exceed safe inference, and explicit manifests give stable ids, file ownership, and better error messages. |
| 2026-06-16 | Treat product child files as the owners of their definition types and avoid field-level merge magic. | The repo favors explicit, searchable contracts over clever implicit rules. |
| 2026-06-16 | Fail on any duplicate id or broken reference during bootstrap, before FastAPI serves traffic. | This is a source-of-truth registry, not a best-effort loader. |
| 2026-06-16 | Keep the registry read-only with no DB fallback and no runtime mutation hooks. | Matches MVP-A scope and protects the platform boundary for MVP-B. |
| 2026-06-23 | `frontends.yaml` is required for every product, and `product.yaml` must not embed frontend definitions. | Frontend ownership must be explicit and read from one file only. |
| 2026-06-23 | `analytics.yaml` is optional, but when analytics are configured it is the exclusive owner; `product.yaml` must not embed analytics. | This preserves optional analytics without hidden fallback from unrelated product fields. |
| 2026-06-23 | `quota_policy_ref` is explicit whenever quota policies exist; the loader must not infer a single available quota policy. | The registry should not silently pick config-owned references. |
| 2026-06-23 | Provider-policy tuning fields are explicit config-owned values, not loader defaults. | Removes hidden runtime behavior and makes the source of truth traceable in repo config. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-16 | Reviewed architecture docs, MVP scope docs, current loader placeholders, startup wiring, and config layout. | Draft implementation and rollout sequence. |
| 2026-06-16 | Ran repo checks with the documented Python fallback; config and architecture validation passed from `.venv`. | Implement loader, tests, and startup failure wiring in small reviewable slices. |
| 2026-06-19 | Confirmed invalid enum values now enter `RegistryLoadError.errors`, but still lack `ref_type` and `ref_value` on the nested `InvalidConfigShapeError`. | Add structured enum diagnostics and focused regression tests for every enum conversion path called out in review. |
| 2026-06-23 | Completed the loader tightening slice: `product.yaml` fallback for frontends/analytics is rejected, `quota_policy_ref` is explicit when quotas exist, provider-policy tuning fields are explicit, and prompt/schema ids now come from manifests instead of asset filenames. Also confirmed `scripts/agent/validate_configs.py` is the shared validation entrypoint and local validation must use `uv` with a workspace-owned `UV_CACHE_DIR` because `just` is unavailable here and the default `uv` cache path is access-blocked. | Keep the docs, focused tests, and shared validation path aligned with the tightened loader contract. |

## Open questions

None. This plan intentionally resolves the current prompt/schema ownership ambiguity by introducing
explicit manifests.

## Follow-up debt

- Add generated-doc automation for config registry contents after the loader stabilizes.
- Consider exposing frontend/quota/handoff lookups from the registry once the runtime-config API
  slice is implemented.
