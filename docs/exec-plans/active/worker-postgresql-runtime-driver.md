# Execution Plan: Worker PostgreSQL Runtime Driver

## Status

- State: completed
- Owner: agent
- Created: 2026-07-12
- Last updated: 2026-07-12

## Goal

The production worker image starts with its compose PostgreSQL URL and reaches the polling loop with
a synchronous PostgreSQL DBAPI installed in the worker package environment.

## Scope

### In scope

- Worker runtime dependency and lockfile.
- Worker compose database dialect.
- Focused startup regression coverage.
- Worker image/build and compose boot validation where locally available.

### Out of scope

- Converting runtime storage to SQLAlchemy async APIs.
- Changing platform API packaging or database composition.
- Database schema or migration changes.

## Relevant docs

- `docs/architecture/runtime-storage.md`
- `docs/architecture/package-layering.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- API: none
- DB: PostgreSQL DBAPI/dialect selection only; no schema change
- Config: worker compose `DATABASE_URL`
- Events: none
- Frontend: none

## Implementation steps

- [x] Trace worker package, image, startup, engine creation, compose URL, and existing drivers.
- [x] Add a synchronous PostgreSQL DBAPI to the worker runtime package and lockfile.
- [x] Make the worker compose URL select that DBAPI explicitly.
- [x] Add focused regression coverage for production worker composition.
- [x] Validate package sync, tests, image build, and compose boot where available.
- [x] Write the task summary document and structured handoff.

## Validation

- [x] `uv sync --project apps/platform-worker --frozen --no-dev`
- [x] worker focused tests
- [x] `python scripts/agent/quick_check.py` (validators passed; pytest blocked by local temp permissions)
- [ ] worker image build (Docker daemon unavailable)
- [ ] compose-level worker boot (Docker daemon unavailable)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-12 | Use Psycopg 3 and `postgresql+psycopg://` for the worker. | The worker uses SQLAlchemy's synchronous engine/session APIs. Existing `asyncpg` is async-only, while an explicit Psycopg dialect avoids relying on the legacy `postgresql://` default of psycopg2. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-12 | Completed repository orientation and runtime dependency trace. `just` is unavailable; the documented Python fallback doctor ran and reported missing global Python modules, while `uv` and Docker are available. | Update worker dependency/config and add regression coverage. |
| 2026-07-12 | Added worker-scoped Psycopg runtime dependency, explicit compose dialect, and startup regression coverage. Production sync/probe and all 6 worker tests pass. Compose config renders successfully. Docker daemon is unavailable; baseline pytest is environment-blocked by temp-directory permissions after validators pass. | Re-run image/compose boot on a Docker-enabled host. |

## Open questions

None.

## Follow-up debt

The platform API's independent image/dependency setup is outside this worker-scoped task and should
be audited separately before production deployment.
