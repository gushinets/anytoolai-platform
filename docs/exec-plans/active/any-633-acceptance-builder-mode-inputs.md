# Execution Plan: ANY-633 Acceptance Builder mode inputs

## Status

- State: active
- Owner: agent
- Created: 2026-11-27
- Last updated: 2026-11-27
- Review date: 2026-11-27
- Next action: User-approved push and review of the remediation.
- Blocker: none for ticket acceptance; additional backend quick-check has three reproduced baseline/environment failures.

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
| 2026-11-27 | Review round 1: confirmed loss of server rejection identity during Check → Draft → Check. New product-level regression failed on the pushed revision (2 starts instead of 1). Changed the visit snapshot to retain the normalized rejected input and error keys alongside raw values; recompute matching errors on remount. Unknown attachment inputs do not update the visit's rejection identity. | Verify |
| 2026-11-27 | Three focused product suites passed 265/265, then added two more regression cases for fresh visits and unknown attachments (both passed individually). Focused typecheck and lint passed. Retried real fake-provider smoke: 12/12 passed, accepted handoff passed in current report, no skips/flakes. | Canonical frontend gate and baseline |
| 2026-11-27 | First frontend-check attempt passed lint/typecheck but unrelated CE-kit ESLint fixture test timed out at 5 seconds during concurrent build. Retry without concurrent smoke/build planned. | Rerun |
| 2026-11-27 | Additional `quick-check`: config, architecture, docs and generated docs passed; pytest 4380 passed, 3 failed, 12 skipped, 723 deselected. Three unchanged runner tests failed: `test_prod_stack_running_reflects_compose_ps_output`, `test_prod_stack_running_propagates_timeout` (local `.env.prod` triggers an unexpected mocked Compose config probe), `test_activation_marker_is_readable_by_non_root_api_user` (passwordless sudo unavailable). All three reproduced on an archived clean c92e3524 revision with a harmless placeholder `.env.prod`, without copying credentials; unrelated to this frontend fix. | Finish frontend gate |
| 2026-11-27 | Final retry of canonical `frontend-check` passed (exit 0): lint/typecheck; web-mirror 1196/1196, Atom Lab browser 349/349, CE-kit 423/423, shared-ui 55/55; generated API contract current and builds passed. Final three-product focused rerun 267/267. Documentation validation passed. | User-approved push and review |
