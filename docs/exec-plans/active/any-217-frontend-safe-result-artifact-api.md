# Execution Plan: ANY-217 Frontend-Safe Result Artifact API

## Status

- State: active
- Owner: agent
- Created: 2026-08-07
- Last updated: 2026-08-07
- Review date: 2026-08-07
- Next action: none; implementation, review remediation, and validation are complete. Move to
  `completed/` once the PR merges.
- Blocker: none

## Goal

Expose `GET /v1/results/{result_artifact_id}` so frontends (CE-kit, product Chrome Extensions,
the eventual web mirror) can fetch the normalized workflow result surfaced by
`startScenario()`/`getScenarioSession()` without ever seeing prompts, provider/model identifiers,
raw/debug artifacts, or state from another tenant/region.

## Scope

### In scope

- `GET /v1/results/{result_artifact_id}`: tenant/region-scoped lookup, canonical-artifact guard
  (job/workflow/schema consistency + re-validation against the workflow's output schema), and a
  frontend-safety denylist backstop on the returned output.
- A shared `anytoolai_platform_core.artifacts.canonical.resolve_canonical_workflow_result` guard,
  extracted out of `HandoffPayloadBuilder.build()`, so handoffs and the results API reject
  non-canonical artifacts (raw/debug type, wrong role, cross-scope artifact/job pairing, stale
  workflow/schema version, schema-invalid content) identically.
- Safe, non-distinguishing `404` responses: `result_artifact_not_found` (unknown id or
  out-of-tenant/region) vs `result_artifact_unavailable` (exists in-scope but not an available
  canonical result).
- Focused API tests (hand-seeded fixtures covering every guard branch) plus one true worker-driven
  vertical test proving a genuinely `WorkflowRunner`-produced artifact satisfies every invariant
  the endpoint checks.
- `docs/architecture/frontend-boundaries.md` contract documentation and generated
  OpenAPI/TS-client regeneration.

### Out of scope

- Rewriting shipped workflow output schemas to be closed (`additionalProperties: false`)
  platform-wide — `kernel_demo.extract_output_v1`/`report_output_v1` intentionally stay open
  because handoffs' safety model relies on an explicit per-field allowlist mapping
  (`context_mapping`/`preview_mapping`) rather than schema strictness; changing that is a
  separate, larger design decision affecting both consumers.
- CE-kit's `getResult()` client wiring (owned by A15c / ANY-226).
- Any change to A01/A04 atom contracts (ANY-251's scope).

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/handoff-model.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/scenario-session-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/exec-plans/completed/a12-scenario-runtime-api.md`
- `docs/exec-plans/completed/a17-handoff-backend-core.md`

## Contracts touched

- API: `GET /v1/results/{result_artifact_id}` (new)
- DB: read-only against existing `platform.artifacts`, `platform.jobs` (no migration)
- Config: none (reads existing workflow/schema registry entries)
- Events: none emitted by this endpoint (read-only)
- Frontend: new `ce-kit` contract surface consumed by `getResult()` (ANY-226, separate slice);
  `docs/generated/openapi.json`/`.md` and `packages/frontend/ce-kit/src/api/generated/platformApi.ts`
  regenerated

## Implementation steps

- [x] Add `ArtifactRepository.get_in_scope(artifact_id, tenant_id, region)`.
- [x] Extract `resolve_canonical_workflow_result` into
      `anytoolai_platform_core/artifacts/canonical.py` and refactor
      `HandoffPayloadBuilder.build()` to use it (behavior-preserving; verified via existing
      handoffs regression tests).
  - [x] Add artifact/job cross-scope check (`tenant_id`/`region`/`product_id`/`frontend_id`) to
        the shared guard after a team-lead review found the linked job was loaded globally with
        no comparison against the artifact's scope.
- [x] Add `anytoolai_platform_core/results/service.py` (`ResultService`,
      `ResultArtifactNotFoundError`, `ResultArtifactUnavailableError`, `ResultArtifactView`).
  - [x] Add `_contains_forbidden_key` denylist backstop (built from
        `common.logging.SENSITIVE_KEY_PARTS` plus compound provider/model-lineage markers) after
        review found the endpoint returns the full output object verbatim against workflow
        output schemas that may still be `additionalProperties: true`.
- [x] Add `apps/platform-api/src/anytoolai_platform_api/routers/results.py` and
      `ResultArtifactResponse` schema; wire the router in `main.py`.
- [x] Add focused API tests covering: happy path, unknown id, out-of-tenant scope, out-of-region
      scope, raw/debug artifact type, action-scoped artifact, non-workflow-result role,
      artifact/job scope mismatch, schema/version drift, leak-shaped content under an open
      schema, generic-word key substrings (false-positive guard), unfinished job, and
      workflow-version-reflects-job-not-live-config.
- [x] Extend the existing worker-driven A12 vertical test
      (`test_start_then_real_worker_execution_preserves_a12_runtime_correlation`) with
      `GET /v1/results/{processed.result_artifact_id}` to prove a real
      `WorkflowRunner._create_final_artifact` record round-trips through
      `resolve_canonical_workflow_result` without drift.
- [x] Update `docs/architecture/frontend-boundaries.md` with the A12b contract section.
- [x] Regenerate `docs/generated/openapi.json`/`.md` and
      `packages/frontend/ce-kit/src/api/generated/platformApi.ts`.
- [x] Add this execution plan and complete the PR #59 description.

## Validation

- [x] `uv run pytest apps/platform-api/tests/test_results_api.py -q` (14 passed)
- [x] `uv run pytest apps/platform-api/tests/test_scenario_runtime_api.py -q` (worker-driven
      vertical test included)
- [x] `uv run pytest apps/platform-api/tests/test_handoffs_api.py packages/backend/platform-core/tests/unit/test_handoffs.py -q`
      (no regressions from the shared canonical-guard change)
- [x] `uv run pytest -m postgresql -q` (full postgres-gated suite)
- [x] `uv run ruff check` on all touched files
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `pnpm --filter @anytoolai/ce-kit generate-api-types:check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-07 | Extract the canonical-artifact guard into a shared `artifacts/canonical.py` helper instead of duplicating `HandoffPayloadBuilder`'s logic | The plan explicitly called for reusing the existing guard pattern; both consumers must reject non-canonical artifacts identically |
| 2026-08-07 | Duplicate `ArtifactRepository.get_in_scope`'s tenant/region-scoped SELECT idiom from `ScenarioSessionRepository` rather than introducing a shared repository mixin | Only 2 call sites exist repo-wide; a shared abstraction for 2 callers is premature, and the plan directed copying the existing pattern |
| 2026-08-07 | Reject frontend-safety via a `ResultService`-only denylist backstop, not a closed-schema (`additionalProperties: false`) requirement in the shared canonical guard | A first attempt requiring closed schemas broke `test_handoff_preview_is_allowlisted_and_bounded`, which deliberately keeps the shared source schema open because handoffs' safety model is an explicit per-field allowlist mapping, not schema strictness. Results API safety needed a mechanism scoped to the one consumer that returns the full object verbatim |
| 2026-08-07 | Build the denylist from `common.logging.SENSITIVE_KEY_PARTS` plus a few compound markers, not bare words like `model`/`provider`/`debug` | A follow-up review found bare generic markers would false-positive on legitimate fields (`car_model`, `insurance_provider`) and duplicated an existing, unsynced list |
| 2026-08-07 | Use the same tenant/region 404 code (`result_artifact_not_found`) for both unknown ids and out-of-scope ids, and a distinct `result_artifact_unavailable` for in-scope-but-non-canonical | Distinguishing "not ready yet" from "wrong id" is useful for legitimate same-tenant frontend polling; the safety guarantee is scoped to no cross-tenant/region existence oracle, not a blanket no-oracle claim (documented explicitly after review flagged the original wording as overclaiming) |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-07 | Implemented the results API, shared canonical guard, router, schema, and initial test suite; regenerated docs/OpenAPI/TS client | Address first code-review pass (workflow_version bug, repository duplication note) |
| 2026-08-07 | Fixed `workflow_version` sourcing bug (was reading the live registry instead of the job-pinned value); added region-scope-miss and real jsonschema-mismatch regression tests per second review pass | Address team-lead review (job scope, frontend-safety denylist, test isolation, doc wording) |
| 2026-08-07 | Added artifact/job cross-scope guard, `ResultService` denylist backstop, split the raw/debug test into three isolated cases, reworded the 404-code doc claim | Address denylist follow-up review (false-positive risk, list duplication) and the two remaining P3 items |
| 2026-08-07 | Fixed denylist to reuse `SENSITIVE_KEY_PARTS` with compound markers instead of bare words; added the false-positive regression test; extended the worker-driven vertical test with a `GET /v1/results/{id}` assertion; added this execution plan and completed the PR description | None; ready for merge |

## Open questions

- None.

## Follow-up debt

- Shipped workflow output schemas (`kernel_demo.extract_output_v1`, `kernel_demo.report_output_v1`,
  and future product schemas) are not uniformly closed (`additionalProperties: false`). The
  `ResultService` denylist is a backstop, not a substitute for closing schemas or introducing a
  dedicated public/frontend-safe schema per workflow. Revisit once ANY-251 (A01/A04 contract
  hardening) lands and a decision is made on whether handoffs' allowlist-mapping safety model
  should be replaced or complemented by closed output schemas platform-wide.
- CE-kit's `getResult()` still needs to be wired to this endpoint (A15c / ANY-226).
