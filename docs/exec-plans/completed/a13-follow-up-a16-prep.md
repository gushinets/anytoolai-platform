# Execution Plan: A13 Follow-Up And A16 Preparation

## Status

- State: completed
- Owner: agent
- Created: 2026-07-20
- Last updated: 2026-08-06
- Review date: 2026-07-20
- Next action: none; backend/API contract hardening is complete and the CE integration this plan
  deferred to A16 was subsequently delivered by A15/ANY-171.
- Blocker: none

## Decision

**A13 stayed backend-complete; at the time, CE integration was deferred to A16. A15/ANY-171 has since
delivered that CE-kit integration.**

A13 owns backend storage, policy resolution, server-side quota check/consume, events, and
frontend-safe API behavior. A13 did not complete the shared CE-kit Platform API client. At the time,
the `createGuestIdentity()` helper could create and locally persist an opaque guest id, but full
`startScenario()`/`getQuota()` HTTP integration, guest-id propagation, and typed frontend handling of
`429 quota_exhausted` were deferred as A16 work. A15/ANY-171 subsequently delivered this integration:
`PlatformApiClient`-backed `getQuota()`, `startScenario()`/`prepareScenarioStart()`,
`getScenarioSession()`/`pollScenarioSession()`, and `nextAction()` (see
`packages/frontend/ce-kit/README.md`).

## Reviewed

- Docs: `docs/architecture/quota-model.md`, `frontend-boundaries.md`,
  `scenario-session-model.md`, `job-lifecycle.md`, `runtime-storage.md`,
  `event-taxonomy.md`, `config-model.md`, MVP-A and MVP scope specs, completed A12/A13 plans, and
  generated OpenAPI/config docs.
- Backend/API: scenario runtime router/service, identity/quota router, API schemas/errors, quota
  service/repository, transaction boundary, A13 storage tables, scenario runtime tests, identity
  quota API tests, and quota service tests.
- Frontend: `packages/frontend/ce-kit/src/index.ts`, `identity/guestIdentity.ts`,
  `quota/getQuota.ts`, `scenarios/startScenario.ts`, and CE package scripts.

## Complete Now

- Add explicit `429 quota_exhausted` OpenAPI response metadata for scenario start.
- Tighten `422` OpenAPI docs for missing/unknown guest identity and add dedicated API tests.
- Add real parallel HTTP scenario-start concurrency coverage through the API and DB transaction path.
- Add a marked slow stress test for dozens of parallel starts with post-factum DB consistency checks.
- Update docs/specs/execution plans to say A13 is backend-complete with integration pending.
- Mark CE-kit `startScenario()` and `getQuota()` as A13 demo/deferred helpers without pretending
  they are the real A16 client.
- Regenerate generated OpenAPI docs after contract changes.

## A13 Backend Follow-Up

- Backend API contract documentation for `429` and `422`.
- Runtime/session/job docs for no session/job on quota exhaustion.
- Tests proving quota is consumed only on accepted starts and concurrency does not over-consume.

## A16 Deferral (Historical) -- All Delivered By A15/ANY-171

At the time, this plan deferred the following to A16. A15/ANY-171 has since delivered all of it (see
`packages/frontend/ce-kit/README.md`); none of it remains outstanding.

- [x] Central `PlatformApiClient`.
- [x] Real CE-kit `getQuota()` and `startScenario()`/`prepareScenarioStart()` HTTP implementations.
- [x] Caller-supplied opaque guest-id propagation into scenario start calls (`prepareScenarioStart()`
  forwards `request.guestId` into the request body; it does not read CE-kit identity storage
  automatically -- callers pass the id returned by `createGuestIdentity()` themselves).
- [x] Typed CE handling for `429 quota_exhausted`, `422`, polling
  (`getScenarioSession()`/`pollScenarioSession()`), and normalized API errors.
- [x] CE-kit integration tests for guest create + scenario start and frontend quota handling.

## Documentation Updates

- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/quota-model.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/job-lifecycle.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/exec-plans/active/a13-guest-identity-and-quota.md`
- `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`
- generated OpenAPI docs

## Validation Plan

- [x] Focused API tests for scenario runtime and identity/quota.
- [x] Focused quota service tests.
- [x] Slow stress test directly.
- [x] Documentation validation and generated docs check.
- [x] Frontend typecheck/build.
- [x] Baseline quick-check.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Added explicit scenario-start `429` OpenAPI response metadata, tightened `422` guest validation docs/tests, added parallel API and slow stress quota tests, marked CE-kit start/quota helpers as A16-deferred, regenerated OpenAPI docs, and moved A13 back to active with backend-complete/integration-pending scope status. | None for this follow-up; A16 owns full CE-kit integration. |
| 2026-08-06 | Reframed this plan's current-status sections as the historical A13/A16 deferral decision after confirming A15/ANY-171 delivered the CE-kit `PlatformApiClient`, `getQuota()`, `startScenario()`/`prepareScenarioStart()`, guest-id propagation, typed error handling, polling, and `nextAction()`. Preserved the 2026-07-20 entry as historical evidence. | None; superseded by A15/ANY-171. |
