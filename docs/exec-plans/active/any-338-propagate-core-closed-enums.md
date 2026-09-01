# Execution Plan: ANY-338 Propagate Core Closed Enums Through OpenAPI and CE-kit Boundaries

## Status

- State: active
- Owner: agent
- Created: 2026-09-02 (backfilled — implementation and three code-review rounds had already
  landed before this file existed; see `docs/exec-plans/active/any-305-validator-ref-config-registry.md`'s
  own round-1 finding for why this file exists at all: ANY-338's round-3 review flagged the same
  "no exec plan for non-trivial work" gap).
- Last updated: 2026-09-02
- Review date: 2026-09-02
- Next action: none — implementation and code-review rounds 1-3 addressed; move to `completed/`
  once merged.
- Blocker: none

## Goal

Closed backend vocabularies (frontend type, quota unit/period/dimension, scenario session status,
handoff status) were weakened to arbitrary `str` across the platform-api HTTP boundary and the
CE-kit client boundary, even though real `StrEnum`s already existed for all of them in
`platform-core`. Generated OpenAPI emitted bare `"type": "string"`, CE-kit DTOs and parsers only
checked `typeof x === "string"`, and an unknown value (e.g. a scenario status of `"cancelled"`)
passed parsing — for `pollScenarioSession`, this meant polling would spin until `maxDurationMs`
instead of stopping immediately, and `HandoffConsent.tsx` carried a hand-written, hand-synced
`TERMINAL_STATUSES` set with its own `ponytail:` warning comment about exactly this hazard. Type
the six response fields with their real Core enums end-to-end (backend → OpenAPI → CE-kit → web
consumers) so unknown values fail parsing (`invalid_response`) instead of silently propagating.

## Scope

### In scope

- `apps/platform-api/src/anytoolai_platform_api/schemas.py`: retype `RuntimeFrontendResponse.type`
  → `FrontendType`; `RuntimeQuotaSummaryResponse.unit/period/dimension` and
  `QuotaStateResponse.unit/period/quota_dimension` → `QuotaUnit`/`QuotaPeriod`/`QuotaDimension`;
  `ScenarioStartResponse.status`/`ScenarioSessionResponse.status` → `ScenarioSessionStatus`;
  `HandoffCreateResponse.status`/`HandoffPreviewResponse.status` → `HandoffStatus`.
- Regenerate `docs/generated/openapi.json`/`.md` and CE-kit's `api/generated/platformApi.ts`.
- Four new CE-kit alias+guard modules, one per semantic enum, derived from
  `components["schemas"]["<Enum>"]`: `runtime/frontendType.ts`, `quota/quotaEnums.ts` (shared by
  `parseQuotaState.ts` and `parseRuntimeConfig.ts` — one runtime mirror per quota enum, not two),
  `scenarios/scenarioSessionStatus.ts`, `handoffs/handoffStatus.ts`.
- Narrow `runtime/types.ts`, `quota/types.ts`, `scenarios/types.ts`, `handoffs/types.ts` and their
  parsers (`parseRuntimeConfig.ts`, `parseQuotaState.ts`, `parseScenarioSessionSnapshot.ts`,
  `parseHandoffCreated.ts`, `parseHandoffPreview.ts`) to reject unknown enum values; update each
  file's `AssertExactSchemaShape` check to reference the generated enum component instead of
  `string`.
- Retype `pollScenarioSession.ts`'s `POLL_STOP_STATUSES` as `ReadonlySet<ScenarioSessionStatus>`
  (round 1), then as an exhaustive `Record<ScenarioSessionStatus, boolean>` (round-1 review fix).
- `apps/web-mirror/src/components/HandoffConsent.tsx`: retype `TERMINAL_STATUSES` against
  `HandoffStatus`, delete the `ponytail:` hand-sync comment; later replaced with an exhaustive
  `Record<HandoffStatus, boolean>` (round-1 review fix, see Progress log).
- Backend test: `ValidationError` on an off-enum string for all six retyped fields; extend
  `tests/test_docs_generation.py` with an enum-values/`$ref` assertion for all six fields.
- CE-kit: one malformed-membership negative case per touched `parse*.test.ts`.
- Shared `makeEnumGuard<T extends string>()` helper in `api/parsing.ts` (round-1 review fix,
  replacing 4 duplicated hand-written guard bodies).

### Out of scope

- A global error-code enum.
- Typing `allowed_next_actions` as an enum.
- Changing `renderQuotaState`/`renderJobStatus` stubs.
- Handoff lifecycle behavior or new A18 endpoints/helpers.
- PydanticAI structured-output binding.
- Adding a runtime-schema dependency (e.g. zod/io-ts) — confirmed in round-2 review as the reason
  `makeEnumGuard`'s value lists must still be hand-written: `openapi-typescript` only emits
  type-level string unions, which erase at runtime, and closing that gap fully would require a
  runtime-schema dependency this ticket explicitly forbids.

## Relevant docs

- `plans/ANY-338.md` (issue + implementation plan + all three code-review rounds, gitignored —
  local-only, not part of the git history).
- `docs/architecture/platform-boundaries.md`, `docs/architecture/package-layering.md`.
- `packages/frontend/ce-kit/src/api/driftAssertions.ts` (the `AssertExactSchemaShape` pattern this
  ticket relies on to catch future drift).

## Contracts touched

- Wire contract: JSON field names, enum wire values, and HTTP behavior are unchanged — only the
  declared *type* of six existing response fields narrows from `string` to a named enum. Verified
  every construction site already passes real enum-derived values (`.value` off a domain enum),
  so no route could actually emit an off-enum literal.
- OpenAPI: `docs/generated/openapi.json` gains `FrontendType`, `QuotaUnit`, `QuotaPeriod`,
  `QuotaDimension`, `ScenarioSessionStatus`, `HandoffStatus` components; the six response fields
  become `$ref`s to them instead of `"type": "string"`.
- CE-kit generated types: `packages/frontend/ce-kit/src/api/generated/platformApi.ts` regenerated
  from the above (committed, gated by `generate-api-types:check` in `full-check`).
- CE-kit public API: new exports from `@anytoolai/ce-kit` — `FrontendType`/`isFrontendType`,
  `QuotaUnit`/`QuotaPeriod`/`QuotaDimension`/`isQuotaUnit`/`isQuotaPeriod`/`isQuotaDimension`,
  `ScenarioSessionStatus`/`isScenarioSessionStatus`, `HandoffStatus`/`isHandoffStatus`.

## Implementation steps

- [x] Backend: import the four `platform-core` enum modules into `schemas.py`, retype the six
      fields, verify every route construction site already passes enum-derived values (grep +
      manual read of `scenario_runtime.py`, `identity_quota.py`, `demo.py`, `handoffs.py`,
      `runtime_config.py`/`bootstrap/runtime_config.py`).
- [x] Regenerate `docs/generated/openapi.json`/`.md` (`generate-docs`) and
      `platformApi.ts` (`pnpm --filter @anytoolai/ce-kit generate-api-types`).
- [x] Four new CE-kit alias+guard modules (`frontendType.ts`, `quotaEnums.ts`,
      `scenarioSessionStatus.ts`, `handoffStatus.ts`).
- [x] Narrow `runtime/types.ts`, `quota/types.ts`, `scenarios/types.ts`, `handoffs/types.ts` and
      all five parsers; update every `AssertExactSchemaShape` `Shape` literal.
- [x] Retype `pollScenarioSession.ts`'s `POLL_STOP_STATUSES`; export new aliases/guards from
      `ce-kit/src/index.ts`.
- [x] `HandoffConsent.tsx`: retype `TERMINAL_STATUSES`, delete the `ponytail:` comment.
- [x] Backend test module `test_schemas_enum_validation.py` (`ValidationError` for all six
      fields); extend `tests/test_docs_generation.py` with
      `test_openapi_exposes_closed_enums_for_the_boundary_fields`.
- [x] CE-kit: one malformed-membership negative case in each of
      `parseRuntimeConfig.test.ts`/`parseQuotaState.test.ts`/`parseScenarioSessionSnapshot.test.ts`/
      `parseHandoffPreview.test.ts`/`createHandoff.test.ts` (also fixed a pre-existing
      `createHandoff.test.ts` fixture that used `"pending"`, which was never a real `HandoffStatus`
      member — the exact class of bug this ticket exists to catch, already latent in the tests).
- [x] Committed as `8ac9fb7`.
- [x] Code review round 1 (2026-09-02) found 3 gaps, all fixed (see Decision log):
  - `TERMINAL_STATUSES`/`POLL_STOP_STATUSES` retyped as `ReadonlySet<Enum>` only catches foreign
    literals, not a *new* enum member silently missing from the set — replaced both with exhaustive
    `Record<Enum, boolean>` maps (`HANDOFF_STATUS_IS_TERMINAL`,
    `SCENARIO_SESSION_STATUS_STOPS_POLLING`) that fail to compile until every member is classified.
  - 4 guard modules duplicated the same `satisfies Record<T, true>` + `Object.hasOwn` body —
    extracted shared `makeEnumGuard<T extends string>()` in `api/parsing.ts`; verified in isolation
    that the `Record<T, true>` parameter still rejects a missing/extra key at the call site.
  - Fixed a drift this rename caused: `classify.ts`'s docstring named `TERMINAL_STATUSES` by
    name — updated to `HANDOFF_STATUS_IS_TERMINAL`.
  - Committed as `89c6055`.
- [x] Code review round 2 (2026-09-02, 4 finder agents + verifier) — correctness angles (enum
      value lists, real producers, Set→Record migration correctness) came back clean; only 2 soft
      cleanup findings, both confirmed non-blocking and left as-is (see Decision log): enum value
      lists are still hand-written (unfixable without a forbidden runtime-schema dependency), and
      `quotaEnums.ts` bundles 3 enums while the other 3 files hold 1 each (matches the ticket's own
      "do not create two runtime mirrors" requirement for quota specifically).
- [x] Code review round 3 (2026-09-02) — only finding: this exec plan didn't exist. Backfilled as
      this file.

## Validation

- [x] `pnpm --filter @anytoolai/ce-kit exec tsc --noEmit` (after round 1's implementation and
      after round 1's review fixes).
- [x] `pnpm --filter @anytoolai/web-mirror exec tsc --noEmit` (same two points).
- [x] `pnpm --filter @anytoolai/ce-kit test` — 287 passed.
- [x] `pnpm --filter @anytoolai/web-mirror test` — 26 passed.
- [x] `python scripts/agent/runner.py quick-check` — 987 passed.
- [x] `python scripts/agent/runner.py full-check` — backend baseline, frontend typecheck/tests/
      build, `generate-docs --check`, `generate-api-types:check`, freelancer-suite product tests —
      all green (run twice: after the initial implementation and after the round-1 review fixes).
- [x] Manual isolated `tsc` check confirming `Record<T, true>`/`Record<T, boolean>` parameters
      genuinely reject a missing key at the call site (not just structurally-compatible-looking).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-02 | Retype exactly the six fields the issue names; leave `allowed_next_actions` and error codes untouched. | Ticket's explicit non-goals; scope creep into adjacent closed-set-shaped fields would expand the diff beyond what was asked and reviewed. |
| 2026-09-02 | `quota/quotaEnums.ts` bundles all three quota enums in one file; the other three enums each get their own file. | Ticket scope explicitly requires "Reuse quota aliases/guards between quota state and runtime config; do not create two runtime mirrors" — quota has two real consumers of the same enum set, the other three enums have one consumer each, so splitting quota would either duplicate the guard or need a shared file anyway. Confirmed inconsistent-but-intentional in round-2 review. |
| 2026-09-02 | `TERMINAL_STATUSES`/`POLL_STOP_STATUSES` became exhaustive `Record<Enum, boolean>` maps instead of staying `ReadonlySet<Enum>`. | Round-1 review: a `ReadonlySet<Enum>` only constrains *elements*, not completeness — the compiler doesn't fail when the enum gains a member (e.g. a future `revoked` `HandoffStatus`) that never gets added to the set, silently reproducing the exact hand-sync bug the deleted `ponytail:` comment warned about. `Record<Enum, boolean>` requires a key for every member, so a new member fails compilation until explicitly classified terminal/non-terminal. |
| 2026-09-02 | Did not attempt to derive `makeEnumGuard()`'s runtime value lists from `platformApi.ts` (e.g. via a codegen step or a runtime-schema library). | Round-2 review raised this as a residual gap. `openapi-typescript` only emits these enums as TS string-literal unions, which erase at runtime — there is no runtime array to derive from without either extending codegen (out of scope, not asked for) or adding a runtime-schema dependency, which the ticket explicitly forbids ("Adding a runtime-schema dependency"). Residual risk is bounded: `makeEnumGuard`'s `Record<T, true>` parameter still catches a hand-written list that drifts from `T` at the call site. |
| 2026-09-02 | Backfilled this exec plan after implementation, rather than blocking further review rounds on writing it first. | Round-3 review found no exec plan existed under `docs/exec-plans/active/`, per `CLAUDE.md`'s "before coding" requirement — a genuine process gap for a 30-file, cross-cutting-mechanism diff. Code was already implemented, reviewed three times, and committed by the time this was caught; user asked to backfill rather than revert and redo the process, which would have discarded validated work for no correctness benefit. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-02 | Implemented per `plans/ANY-338.md`'s design: backend enum retyping, OpenAPI/CE-kit regeneration, four new guard modules, narrowed DTOs/parsers/drift-checks, `pollScenarioSession` retype, `HandoffConsent.tsx` retype, backend + CE-kit tests. `quick-check` (987 passed) and `full-check` green. Committed as `8ac9fb7`. | Await code review. |
| 2026-09-02 | Code review round 1 found 3 gaps (non-exhaustive terminal/stop status sets x2, duplicated guard pattern x4 files). Fixed all three: `Record<Enum, boolean>` maps, shared `makeEnumGuard()`, fixed a stale `TERMINAL_STATUSES` name reference in `classify.ts`. Verified `Record<T, true>`-as-parameter still catches drift via an isolated `tsc` check. Both packages' typecheck/tests and `full-check` re-run green. Committed as `89c6055`. | Await round-2 review. |
| 2026-09-02 | Code review round 2 (4 finder agents + verifier) found 2 soft cleanup items (hand-written enum value lists, inconsistent file granularity), both confirmed non-blocking and intentional/unfixable-in-scope. No code changes. | Await round-3 review. |
| 2026-09-02 | Code review round 3 found this exec plan was missing (`CLAUDE.md` "before coding" requirement). Backfilled this file. | Move to `completed/` once merged. |

## Open questions

- None.

## Follow-up debt

- `makeEnumGuard()`'s runtime value lists (`frontendType.ts`, `quotaEnums.ts`,
  `scenarioSessionStatus.ts`, `handoffStatus.ts`) are hand-written and cannot currently be derived
  from `platformApi.ts` (type-only, erases at runtime). If a future ticket adds a runtime-schema
  dependency or extends `generate-api-types.mjs` to also emit runtime value arrays, these four
  files could switch to importing generated values instead of restating them — out of scope here
  per the ticket's explicit non-goal.
