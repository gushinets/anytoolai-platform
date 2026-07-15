# Execution Plan: ANY-130 Structured Diagnostics and Safe Context

## Status

- State: active
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: complete fresh CI on PR #29, then merge.
- Blocker: None. The PR was rebased onto current `main` after ANY-129 merged; it inherits the
  pinned pnpm setup required by full-check CI.
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
| 2026-07-15 | Rebased PR #29 onto merged ANY-129; previous red full-check was CI tool provisioning, not diagnostics behavior. | Push with lease and verify fresh CI. |
