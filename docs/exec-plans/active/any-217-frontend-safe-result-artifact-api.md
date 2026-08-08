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
- Safe `404` responses that never leak artifact/job internals, prompts, or provider/model
  identifiers in the body: `result_artifact_not_found` (unknown id or out-of-tenant/region) vs
  `result_artifact_unavailable` (exists in-scope but not an available canonical result). The two
  codes intentionally differ (see decision log); the guarantee is no cross-tenant/region
  existence oracle, not a blanket no-oracle claim.
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
  - [x] Add `_contains_forbidden_key` denylist backstop (a dedicated, results-specific set of
        exact-match provider/model/prompt-lineage key names, matched after normalizing
        `-`/`_`/camelCase key separators) after review found the endpoint returns the full output
        object verbatim against workflow output schemas that may still be
        `additionalProperties: true`.
  - [x] Switched the matcher from substring to whole-key matching and added the actual bare
        internal field names (`prompt`, `provider`, `model`, `provider_call_id`,
        `gateway_model`, etc.) to the list after a review found substring matching both let those
        bare names through and rejected unrelated compound domain fields
        (`vehicle_model_id`, `business_trace_id`, ...) that merely contained a marker substring.
  - [x] Added `litellm_debug_info`/`parent_trace_id` exact entries and fixed
        `_CAMEL_CASE_BOUNDARY` to also split acronym-run -> capitalized-word transitions (not just
        lower/digit -> upper), after a review of the whole-key-matching switch found (a) it
        narrowed coverage for compound leak-shaped keys with no exact-match entry, and (b) an
        all-caps-prefixed spelling (`GATEWAYModel`) had no lower-to-upper transition and
        normalized to one unsplit token, bypassing the exact match.
  - [x] Replaced the camelCase-boundary-insertion regex entirely with separator-stripped
        canonical-form equality (`_canonical_key`: strip `-`/`_`, casefold, compare) after a
        review found the regex-patching approach was fundamentally incomplete: fully-uppercase
        spellings (`TRACEID`, `GATEWAYMODEL`) have no lowercase letter to anchor a boundary on,
        and multi-acronym PascalCase (`LiteLlmDebugInfo`) splits into more words than its marker.
        Comparing canonical forms sidesteps word-boundary detection entirely instead of adding
        another special-cased regex rule.
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

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py quick-check` (config/architecture/docs validation,
      `generate-docs --check`, and the DB-free backend pytest subset)
- [x] `python scripts/agent/runner.py postgresql-check` (full postgres-gated suite: results API,
      the worker-driven A12 vertical test, and handoffs regression, all in one canonical run)
- [x] `python scripts/agent/runner.py frontend-check` (typecheck, `ce-kit` unit tests,
      `generate-api-types:check` OpenAPI-contract drift, build)
- [x] `uv run ruff check` on all touched files (no dedicated runner subcommand wraps ruff; run
      directly)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-07 | Extract the canonical-artifact guard into a shared `artifacts/canonical.py` helper instead of duplicating `HandoffPayloadBuilder`'s logic | The plan explicitly called for reusing the existing guard pattern; both consumers must reject non-canonical artifacts identically |
| 2026-08-07 | Duplicate `ArtifactRepository.get_in_scope`'s tenant/region-scoped SELECT idiom from `ScenarioSessionRepository` rather than introducing a shared repository mixin | Only 2 call sites exist repo-wide; a shared abstraction for 2 callers is premature, and the plan directed copying the existing pattern |
| 2026-08-07 | Reject frontend-safety via a `ResultService`-only denylist backstop, not a closed-schema (`additionalProperties: false`) requirement in the shared canonical guard | A first attempt requiring closed schemas broke `test_handoff_preview_is_allowlisted_and_bounded`, which deliberately keeps the shared source schema open because handoffs' safety model is an explicit per-field allowlist mapping, not schema strictness. Results API safety needed a mechanism scoped to the one consumer that returns the full object verbatim |
| 2026-08-07 | First built the denylist from `common.logging.SENSITIVE_KEY_PARTS` plus a few compound markers, not bare words like `model`/`provider`/`debug` | A review found bare generic markers would false-positive on legitimate fields (`car_model`, `insurance_provider`) and duplicated an existing, unsynced list |
| 2026-08-07 | Replaced `SENSITIVE_KEY_PARTS` reuse with a dedicated, results-specific marker list, and normalized `-`/`_`/camelCase key separators before matching | A later review found (a) `SENSITIVE_KEY_PARTS`'s own broad single-word markers (`email`, `token`, `handoff`, `secret`, `prompt`) would false-positive on legitimate fields like `email_subject`/`token_count`, and log-redaction/API-rejection have different false-positive tolerances; (b) the matcher only lowercased keys, so `provider-model`/`providerModel`/`pydantic-run-id` bypassed the underscore-form markers entirely |
| 2026-08-07 | Switched the denylist matcher from substring to whole-key matching, and added the actual bare internal field names (`prompt`, `provider`, `model`, `provider_call_id`, `gateway_model`, `litellm_response_id`, ...) to the list | A review found the substring matcher was both under- and over-inclusive: it deliberately left bare `prompt`/`provider`/`model`/`provider_call_id`/`gateway_model` (the real field names used for provider/prompt lineage elsewhere in the platform) off the list to avoid colliding with `car_model`/`insurance_provider`, which let those exact internal names leak through; and separately, its remaining compound markers (`model_id`, `model_version`, `provider_name`, `trace_id`) still matched as substrings of unrelated legitimate fields (`vehicle_model_id`, `car_model_version`, `insurance_provider_name`, `business_trace_id`), 404ing valid results. Whole-key matching fixes both without reintroducing either failure mode |
| 2026-08-07 | Use the same tenant/region 404 code (`result_artifact_not_found`) for both unknown ids and out-of-scope ids, and a distinct `result_artifact_unavailable` for in-scope-but-non-canonical | `getScenarioSession()` only ever surfaces a non-null `result_artifact_id` once the job has succeeded, so this is not a "not ready yet" polling distinction; it lets a caller holding a previously-valid id (e.g. from before a config redeploy changed the workflow's output schema/version) tell "wrong id" apart from "was valid, no longer an available canonical result." The safety guarantee is scoped to no cross-tenant/region existence oracle, not a blanket no-oracle claim |
| 2026-08-08 | Added `litellm_debug_info`/`parent_trace_id` as explicit exact-match entries, and extended `_CAMEL_CASE_BOUNDARY` to also split acronym-run -> capitalized-word transitions | A post-merge review of the whole-key-matching switch found two residual gaps: named compound leak-shapes with no exact entry weren't caught, and an all-caps-prefixed spelling (`GATEWAYModel`) had no lower-to-upper transition for the old single-rule regex to split, so it normalized to one token and bypassed the exact match |
| 2026-08-08 | Accepted, not fixed: bare `prompt`/`provider`/`model` as exact-match denylist entries can 404 a hypothetical future workflow whose legitimate schema output literally uses one of those field names | Same review flagged this as a real trade-off, but it is the same fundamental tension already tracked in Follow-up debt (denylist vs. closed/dedicated schema) — no key-name heuristic can perfectly separate "internal lineage field called `model`" from "domain field called `model`" without a schema-level contract per workflow |
| 2026-08-08 | Accepted, not fixed: the recursive forbidden/sensitive-key scan pattern now exists independently in `results/service.py`, `common/logging.py` (`_sensitive_key`/`SENSITIVE_KEY_PARTS`), and `events/emitter.py`, each with different marker sets and match semantics (substring vs. exact-whole-key) | Consistent with the earlier decision not to reuse `SENSITIVE_KEY_PARTS` here: log redaction, event redaction, and API rejection have different false-positive tolerances and should evolve independently; a shared helper would either force one tolerance on all three or need parameterization disproportionate to 3 call sites |
| 2026-08-09 | Replaced camelCase-boundary-insertion regex matching with separator-stripped canonical-form equality (`_canonical_key`); consolidated 4 near-duplicate key-variant tests into one parametrized test with added fully-uppercase/nested-acronym cases | A further review found the regex-patching approach (now 2 boundary rules) was fundamentally incomplete, not just missing one more case: fully-uppercase spellings (`TRACEID`, `MODELID`, `PARENTTRACEID`, `GATEWAYMODEL`) have no lowercase letter for any lower/digit->upper rule to anchor on, and multi-acronym PascalCase (`LiteLlmDebugInfo`) splits into more words than its marker (`litellm_debug_info`) has, so exact-match still failed after normalization. Since matching is against a small fixed marker list (not general text), comparing separator-stripped-and-casefolded forms of both sides sidesteps word-boundary detection instead of trying to solve it, closing the whole class of bypasses in one change instead of one regex rule per reported spelling |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-07 | Implemented the results API, shared canonical guard, router, schema, and initial test suite; regenerated docs/OpenAPI/TS client | Address first code-review pass (workflow_version bug, repository duplication note) |
| 2026-08-07 | Fixed `workflow_version` sourcing bug (was reading the live registry instead of the job-pinned value); added region-scope-miss and real jsonschema-mismatch regression tests per second review pass | Address team-lead review (job scope, frontend-safety denylist, test isolation, doc wording) |
| 2026-08-07 | Added artifact/job cross-scope guard, `ResultService` denylist backstop, split the raw/debug test into three isolated cases, reworded the 404-code doc claim | Address denylist follow-up review (false-positive risk, list duplication) and the two remaining P3 items |
| 2026-08-07 | Fixed denylist to reuse `SENSITIVE_KEY_PARTS` with compound markers instead of bare words; added the false-positive regression test; extended the worker-driven vertical test with a `GET /v1/results/{id}` assertion; added this execution plan and completed the PR description | Address team-lead review #1 (key-separator normalization, log-list reuse, plan/doc consistency) |
| 2026-08-07 | Replaced the `SENSITIVE_KEY_PARTS`-based denylist with a dedicated, results-specific marker list; normalized `-`/`_`/camelCase key separators before matching; added parametrized regression coverage for `provider-model`/`providerModel`/`ProviderModel`/`pydantic-run-id`/`pydanticRunId`; fixed this plan's self-contradictory "non-distinguishing 404" wording and its obsolete "not ready yet" polling rationale in the decision log | Address team-lead review #2 (self-referential timestamp assertion, stale plan wording, validation checklist not routed through canonical runner commands) |
| 2026-08-07 | Fixed the worker-driven vertical test's `created_at` assertion to compare against the DB-persisted `artifacts_table` row instead of the response echoing itself; updated this plan's implementation-step description of the denylist (stale `SENSITIVE_KEY_PARTS` reference) and rewrote the Validation checklist to route through `doctor`/`quick-check`/`postgresql-check`/`frontend-check` instead of raw `pytest`/`generate-docs`/`generate-api-types:check` invocations | Address team-lead review #4 (bare internal field names bypassing the denylist, substring-match collisions with legitimate compound fields, stale PR description wording) |
| 2026-08-07 | Switched the denylist matcher to whole-key matching and expanded it with the real bare internal field names (`prompt`, `provider`, `model`, `provider_call_id`, `gateway_model`, `litellm_response_id`, ...); added regression tests for both the newly-blocked bare names and the previously-false-positived compound domain fields (`vehicle_model_id`, `business_trace_id`, ...); updated `frontend-boundaries.md` and this plan's decision log; fixed the PR description's stale "non-distinguishing 404s" line | Address post-merge review of the whole-key-matching switch (residual compound coverage gaps, acronym-boundary regex gap, cross-module duplication note) |
| 2026-08-08 | Added `litellm_debug_info`/`parent_trace_id` exact entries; fixed `_CAMEL_CASE_BOUNDARY` to split acronym-run -> capitalized-word transitions and added a `GATEWAYModel` regression test; documented the bare-marker-vs-legitimate-field and cross-module-duplication findings as accepted, tracked trade-offs rather than code changes | Address further review of the regex-based normalizer (fully-uppercase and nested-acronym spellings still bypass it, stale doc claim, duplicate tests, unmemoized hot path) |
| 2026-08-09 | Replaced the camelCase-boundary regex with separator-stripped canonical-form equality (`_canonical_key`), closing the fully-uppercase and nested-acronym-PascalCase bypass classes in one change instead of another regex rule; consolidated 4 near-duplicate key-variant tests into one parametrized test and added the new bypass spellings as cases; corrected the frontend-boundaries.md claim that no longer held; declined to memoize `_canonical_key` (would cache on unbounded request-controlled key strings) | None; ready for merge |

## Open questions

- None.

## Follow-up debt

- Shipped workflow output schemas (`kernel_demo.extract_output_v1`, `kernel_demo.report_output_v1`,
  and future product schemas) are not uniformly closed (`additionalProperties: false`). The
  `ResultService` denylist is a backstop, not a substitute for closing schemas or introducing a
  dedicated public/frontend-safe schema per workflow. Revisit once ANY-251 (A01/A04 contract
  hardening) lands and a decision is made on whether handoffs' allowlist-mapping safety model
  should be replaced or complemented by closed output schemas platform-wide.
  - Concretely, this denylist is a finite, hand-maintained list with no mechanism keeping it in
    sync with the platform's actual internal field names, so it will keep needing point fixes as
    new ones are found (already true across 4 revisions). It also cuts both ways: it can 404 a
    legitimate output field that happens to share an exact internal name (`prompt`, `model`,
    `provider`). A dedicated public/frontend-safe schema per workflow is the only way to close
    both gaps at once.
- CE-kit's `getResult()` still needs to be wired to this endpoint (A15c / ANY-226).
