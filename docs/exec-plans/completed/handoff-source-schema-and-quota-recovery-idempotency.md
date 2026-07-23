# Handoff Source Schema and Quota Recovery Idempotency

## Status

- State: completed
- Owner: agent
- Created: 2026-07-23
- Last updated: 2026-07-23
- Review date: 2026-07-23
- Next action: run the PostgreSQL-marked concurrency test in CI or a configured local environment
- Blocker: none; local PostgreSQL execution was unavailable because
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was unset and Docker was not running

## Scope

Verify and fix two A17 integrity gaps:

1. revalidate the complete mutable source workflow-result artifact against the source workflow's
   declared output schema before handoff mappings;
2. make quota-exhaustion rollback recovery single-owner for concurrent accepts of one handoff.

## Research

Reviewed `ARCHITECTURE.md`, the repository knowledge map and core architecture guidance, plus the
handoff, structured-output, quota, event, runtime-storage, scenario-session, and LLM-runtime docs.
Inspected the handoff payload builder/service/repository and API transaction boundary; scenario
linked-session and ordinary start behavior; quota consume and rollback recovery; event replay
storage; structured-output validation; SQLite service/API tests; and existing PostgreSQL quota and
handoff concurrency coverage.

Both findings are present on the current branch:

- handoff creation verifies artifact provenance metadata but validates only mapped target context;
- handoff quota recovery unconditionally recreates `quota.checked` and `quota.exhausted` after each
  rolled-back claimant.

## Implementation

- Reuse the structured-output validator to normalize and validate the full artifact body with the
  source workflow output schema before applying context or preview mappings. Preserve target input
  schema validation.
- Add an atomic handoff quota-recovery reservation using the existing safe `error_code` field.
  Acceptance CAS will require that no recovery is reserved. For a real handoff, only the recovery
  transaction that changes the marker will ensure quota state and emit the recovered audit pair;
  non-handoff scenario-start recovery behavior remains unchanged.
- Keep the router's existing separate `mark_failed()` transaction as the owner of the terminal
  `failed` transition and `handoff.failed` event.
- Add a source-schema regression test and PostgreSQL parallel exhausted-accept coverage, plus
  focused repository/quota tests as needed.
- Update the handoff, structured-output, quota/event durability documentation and complete this
  plan after validation.

## Validation

Run focused platform-core and platform-api handoff/quota tests, the PostgreSQL concurrency test when
`ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is available, documentation/generated checks, and canonical
quick-check.

## Validation result

- Focused structured-output, handoff, quota, and API tests: 36 passed.
- Full platform-core suite: passed.
- Full platform-api suite: passed with the three PostgreSQL-marked tests skipped.
- New PostgreSQL concurrency test collected successfully; execution requires the documented
  maintenance database URL and was unavailable locally.
- Config, architecture, documentation, generated-doc freshness, source lint, and format checks
  passed.
- Exact canonical DB-free aggregate: 335 passed.
