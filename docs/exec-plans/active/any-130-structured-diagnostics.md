# Execution Plan: ANY-130 Structured Diagnostics and Safe Context

## Status

- State: active
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: validate JSON logging redaction and cross-platform context collection.
- Blocker: GitHub authentication is required to publish the prepared branch.
- Linear: ANY-130

## Goal

Make existing API and worker behavior diagnosable through privacy-safe JSON logs and a useful
repository-local context bundle.

## Scope

- Structured standard-library JSON logging for existing API and worker paths.
- Existing request, job, scenario, workflow, action, and provider identifiers when available.
- Redaction for all named sensitive categories.
- Best-effort Python context collection for tools, Git, plans, Compose, endpoints, logs, and failures.
- No metrics, traces, external log stack, or missing domain-flow implementation.

## Validation

- [x] logging and redaction tests
- [x] context collection tests
- [x] API and worker regression tests
- [x] python scripts/agent/runner.py collect-context
- [x] python scripts/agent/runner.py quick-check (248 passed)
- [x] python scripts/agent/runner.py full-check (248 baseline + frontend + 2 Freelancer tests)

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-15 | Added parseable redacted JSON logs for existing API/worker paths and a sanitized best-effort context bundle under .agent/context. | Publish after GitHub authentication is restored. |
