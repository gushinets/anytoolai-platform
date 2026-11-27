# Execution Plan: ANY-633 Acceptance Builder mode inputs

## Status

- State: active
- Owner: agent
- Created: 2026-11-27
- Last updated: 2026-11-27
- Review date: 2026-11-27
- Next action: Local commit, user-approved push, and product acceptance.
- Blocker: none

## Goal and scope

Keep raw Draft and Check form values independently for the mounted product visit. New task clears only the active mode; a fresh visit starts empty. Preserve session attachment, quota, validation and mode locks. No browser persistence, backend, or visual changes. Client Update Writer retains its existing tab-local recovery.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/product-specs/mvp-a2-client-surfaces.md`

## Implementation steps

- [x] Reproduce loss with a product integration test.
- [x] Add opt-in shared visit-scoped retention (ANY-632 prerequisite absent on branch) and enable it for Acceptance Builder.
- [x] Cover reset, field clearing, fresh mount and attachment isolation.
- [x] Run focused product suites, frontend checks and fake-provider browser smoke.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-27 | Baseline 26128baa3ae87ad9213906af18697feafff28470; doctor passed with .venv Python 3.12.13. System Python lacks pytest/pydantic. | Regression test |
| 2026-11-27 | Baseline focused regression: 1 failed at the expected Draft value (empty instead of exact whitespace-preserving brief). | Implement retention |
| 2026-11-27 | Shared per-scenario map and raw edit/reset callbacks added; Acceptance Builder opted in. Both product suites passed, 147 tests. | Frontend gate and handoff smoke |
| 2026-11-27 | Frontend gate lint caught an unsafe callback argument inherited from the heterogeneous mode definition type; explicitly typed the callback. Lint and typecheck then passed. Browser stage was interrupted after repeated Chromium sandbox launch failures (Operation not permitted). | Retry browser-capable checks outside sandbox |
| 2026-11-27 | Existing dev stack uses the live-provider Compose override. Started isolated fake-provider Compose project on API 18783 / PostgreSQL 16215 using cached development images, without changing the live stack. Readiness passed. | Run real handoff smoke |
| 2026-11-27 | Isolated fake-provider `acceptance-builder-smoke` (API 18783, PostgreSQL 16215): 12/12 passed, no skips. Named accepted handoff passed (same-tab redirect, queued Draft, empty editable brief, no additional start, consumed token, owner replay reuses result); declined handoff passed too. | Finish canonical frontend check |
| 2026-11-27 | `validate-docs` passed after filling required execution-plan metadata. | Finish verification |
| 2026-11-27 | Focused suites rerun after lint type annotation: 147/147 passed. Repository search confirmed Acceptance Builder and Client Update Writer are the only multi-mode consumers; the latter already retains drafts. | Finish canonical frontend gate |
| 2026-11-27 | Final canonical `frontend-check` outside the restricted Chromium sandbox passed (exit 0): lint, typecheck, all workspace tests (web-mirror 1193/1193, CE-kit 423/423, shared-ui 55/55, Atom Lab browser 349/349), generated API types and builds. | Local commit and user-approved push |
| 2026-11-27 | Removed only isolated smoke containers and network; retained its test database volume. Existing live-provider stack untouched. | Product acceptance |
