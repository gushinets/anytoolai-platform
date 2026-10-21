# Execution Plan: ANY-697 Runtime Versions (PostgreSQL 18, Node 24)

## Status

- State: active
- Owner: agent
- Created: 2026-10-21
- Last updated: 2026-10-21
- Review date: 2026-10-21
- Next action: merge and deploy this tooling revision to prod and Atom Lab, then open the
  follow-up that switches their overlays to PostgreSQL 18 (see "Staged rollout").
- Blocker: none

## Goal

Run PostgreSQL 18 and Node 24 everywhere; Python stays 3.12. Node source of truth is `.nvmrc`,
PostgreSQL source of truth is the base `infra/compose/docker-compose.yml`.

## Changes

- `web-mirror.Dockerfile`: `node:24-slim` in both stages.
- `postgres:18` in base and agent compose and the `backend.yml` service container.
- Prod and Atom Lab overlays stay on `postgres:16` with their existing volumes in this revision
  (see "Staged rollout").
- `tests/architecture/test_runtime_versions_match.py` fails on version drift.
- Runbook: "Upgrading PostgreSQL 16 to 18" in `infra/deployment/README.md`.
- Runner: `prod-quiesce` and `prod-recovery-postgres-up`, sharing the drain and PostgreSQL-only
  helpers with `atom-lab-quiesce`/`atom-lab-recovery-postgres-up`, so the production cut-over
  runs on locked, bounded, fail-closed commands instead of hand-written shell. Aborting a quiesce
  goes through `prod-up`/`prod-ready`; no separate `prod-resume`.

## Staged rollout

Step 1 of the cut-over runs `prod-quiesce` on the revision still running PostgreSQL 16, so that
command must be deployed before the switch. This PR is the tooling revision; the follow-up is the
switch revision:

- set `postgres:18` in the prod and Atom Lab overlays (or drop their `image:` pin), mount
  `postgres18-data` / `atom-lab-postgres18-data` at `/var/lib/postgresql`;
- empty `STAGED_POSTGRES_MAJORS` in `tests/architecture/test_runtime_versions_match.py`;
- deploy only with the runbook in `infra/deployment/README.md`.

## Out of scope

Python dependency updates, Portal (ANY-710), minor/digest pins, the VPS cut-over itself.
