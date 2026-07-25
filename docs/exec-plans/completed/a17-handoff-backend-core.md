# Execution Plan: A17 Handoff Backend Core

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Last updated: 2026-07-22
- Review date: 2026-07-22
- Next action: A18 may consume the token-based preview/accept/decline API from the consent UI
- Blocker: none

## Goal

Implement a backend-owned, tokenized, user-confirmed handoff that safely maps a completed source
workflow artifact into a linked target scenario session and optionally queues the target workflow.

## Research completed

- Reviewed the MVP scope/kernel specs and the handoff, scenario-session, runtime-storage, event,
  job, workflow, config, frontend, structured-output, and LLM architecture documents.
- Reviewed completed A04 runtime-storage, A05 event-log, and A12 scenario-runtime plans.
- Inspected all runtime migrations, SQLAlchemy metadata, session/job/artifact/event repositories and
  services, config loader/registry/SDK contracts, API routing/error patterns, worker lineage, tests,
  generated docs, and token-sensitive request logging.

## Contracts touched

- API: create, preview, accept, and decline handoff endpoints.
- DB: `platform.product_handoffs` in `0004` plus compatibility migration after `0007`.
- Config: target frontend, immediate/deferred start policy, target context mapping, preview mapping.
- Events: full handoff lifecycle including expired and failed.
- Scenario runtime: linked target sessions and jobless deferred-session retrieval.

## Implementation steps

- [x] Implement handoff config/domain models, persistence table, migration, and guarded repository.
- [x] Implement canonical artifact payload/preview building and handoff lifecycle service.
- [x] Add linked scenario-session creation for immediate and deferred policies.
- [x] Add safe API schemas/routes/errors and token-safe request logging.
- [x] Add repository, service, API, concurrency, lineage, and generated-contract tests.
- [x] Update architecture/product documentation and generated docs.
- [x] Run focused validation and the canonical non-slow baseline selection, then move this plan to
  completed.

## Decisions

- Tokens use 32 random bytes, are valid for 30 minutes, and are stored only as SHA-256 hashes.
- Immediate means queue a `created` target job for the existing worker; it never executes inline.
- Immediate handoffs become consumed when the target job is durably queued; deferred handoffs stay
  accepted with a `waiting_for_user` target session and no job/quota consumption.
- Existing databases stamped beyond placeholder `0004` receive a forward compatibility migration.

## Validation

- [x] Focused handoff/storage/scenario/API/worker/config/contract tests.
- [x] PostgreSQL concurrent double-accept test added; execution remains conditional because
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is not configured locally.
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] Canonical non-slow test selection: `323 passed, 3 deselected`. The wrapper command itself
  remains affected by the already-recorded Windows ACL papercut at
  `.quick-check-tmp/pytest/pytest-of-jackd`; the same isolated environment and exact test targets
  passed with a fresh explicit `--basetemp`.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-22 | Implemented persistence, token lifecycle, safe payload mapping, API, linked sessions, events, tests, docs, and generated contracts; final baseline passed. | A18 consent UI integration. |
