# A11 — Job Lifecycle And Worker Integration

## Brief task description

Connect DB-backed jobs to a runnable worker and the sequential workflow runtime while preserving
session correlation, idempotent claims, safe terminal state, lifecycle events, and result artifacts.

## Implementation summary

Implemented a PostgreSQL-polling worker composition and entrypoint; made claim/start and
cancel/event persistence atomic; guaranteed complete safe failure fields; added
`workflow.canceled`; and added production-composed end-to-end storage/event/correlation coverage.
