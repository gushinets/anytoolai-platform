# Execution Plan: Handoff Uvicorn Access-Log Security

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Last updated: 2026-07-22
- Review date: 2026-07-22
- Next action: none
- Blocker: none

## Goal

Prevent opaque handoff bearer tokens from appearing in Uvicorn access logs while retaining the
existing structured, route-template-safe AnytoolAI request log.

## Research

- Before this change, the supported API runtime launched Uvicorn from
  `infra/docker/platform-api.Dockerfile` with default access logging enabled.
- Uvicorn logs the raw request target independently of FastAPI middleware.
- The application middleware already emits structured completion/failure events through
  `_safe_request_path()`, covering all token-bearing preview, accept, and decline routes.

## Implementation and validation

- [x] Disable Uvicorn access logging in the supported platform API launch command.
- [x] Test the actual `uvicorn.access` logger configuration and the Docker launch contract.
- [x] Document why structured application request logs remain authoritative.
- [x] Run focused API logging/security tests and repository validation checks.

## Validation result

- Actual Uvicorn access-logger regression: 1 passed.
- Full platform API suite: passed with 2 existing skips.
- Canonical DB-free aggregate: 327 passed, 3 deselected.
- Config, architecture, docs, generated-doc freshness, formatting, lint, and diff checks passed.
