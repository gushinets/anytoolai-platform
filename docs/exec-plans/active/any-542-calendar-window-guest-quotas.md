# Execution Plan: ANY-542 calendar-window guest quotas

## Status

- State: active
- Owner: mixed
- Created: 2026-10-06
- Last updated: 2026-10-06
- Review date: 2026-10-13
- Next action: re-run `full-check` where passwordless sudo is available (only `test_activation_marker_is_readable_by_non_root_api_user` fails locally), then review.
- Blocker: none

## Goal

Platform Core supports `calendar_day`, `calendar_week` and `calendar_month` guest quota periods as
fixed UTC windows, resolved once per operation. No product is switched off `lifetime`.

## Scope

### In scope

- `resolve_quota_period`, injectable quota clock, single window snapshot in validate/consume/recovery/GET.
- `resets_at` on `QuotaState` and `QuotaStateResponse`; expanded `QuotaPeriod` in SDK, OpenAPI, CE-kit.
- Resolver, accepted-start and GET regression tests; recovery boundary regression on PostgreSQL.
- Docs: config-model, quota-model (including the client-first rollout order).

### Out of scope

- Switching any product YAML, migrations, reset jobs, rolling windows, per-user timezones.
- Web "Resets ..." line (optional in the ticket; add as a follow-up if wanted).

## Relevant docs

- `docs/architecture/quota-model.md`
- `docs/architecture/config-model.md`

## Contracts touched

- API: `QuotaStateResponse.resets_at` (nullable, optional for clients), expanded `QuotaPeriod`
- DB: none
- Config: `quotas.yaml` `period` accepts three new values
- Events: none
- Frontend: CE-kit `isQuotaPeriod`, `QuotaState.resetsAt`

## Implementation steps

- [x] Models, resolver, service, SDK enum.
- [x] API schema/payload, regenerate OpenAPI and `platformApi.ts`.
- [x] CE-kit guard, type, parser, tests.
- [x] Resolver, accepted-start and GET tests (no PostgreSQL).
- [x] PostgreSQL recovery boundary test.
- [x] Docs.
- [x] Validation: quick-check, frontend-check, quota PostgreSQL tests (full-check stops on the sudo-dependent runner test).

## Validation

- `python scripts/agent/runner.py quick-check`
- `python scripts/agent/runner.py full-check`
- `python scripts/agent/runner.py postgresql-check`

## Decision log

- 2026-10-06: accepted-start and GET regressions use in-memory doubles because the existing service
  tests all require PostgreSQL.
