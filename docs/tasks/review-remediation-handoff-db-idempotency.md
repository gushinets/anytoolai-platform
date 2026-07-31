# Review Remediation: Handoff, Test DB, and Idempotency

## Brief task description

Address verified review findings in handoff payload validation, disposable PostgreSQL test-database
lifecycle handling, and idempotency HTTP/OpenAPI coverage.

## Relevance assessment

- Handoff target-schema taxonomy: confirmed. Runtime previously presented malformed target schemas as
  ordinary mapped-payload failures; schema assets also lacked load-time JSON Schema validation.
- Disposable database setup cleanup: confirmed. Database creation occurred before the cleanup
  `try/finally`, so a post-create setup error could leak a database.
- Database teardown race: confirmed in principle. PostgreSQL 16 is used in CI, so `DROP DATABASE
  ... WITH (FORCE)` removes the terminate/drop reconnect window.
- Idempotency coverage: partially valid. Domain behavior and router mapping existed, but fast tests
  for the mapping/OpenAPI example and a PostgreSQL HTTP conflict test were absent.

## Implementation summary

- Separate malformed target-schema errors from invalid mapped handoff data and reject invalid JSON
  Schema assets at config-load time.
- Guarantee best-effort database cleanup after any creation attempt, preserve the original setup
  error, and use PostgreSQL force-drop semantics.
- Add fast idempotency mapping/OpenAPI-contract tests and PostgreSQL API conflict coverage.

## Validation results

- `packages/backend/platform-core/tests/unit/test_config_loader.py -k malformed_json_schema`,
  `tests/test_db_support.py`, and `apps/platform-api/tests/test_scenario_runtime_router.py`: passed
  (`4 passed`).
- `validate-configs` and `validate-architecture`: passed through the repository `.venv`.
- PostgreSQL-marked handoff and API tests were collected but skipped locally because
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset; they remain required in the PostgreSQL CI gate.
