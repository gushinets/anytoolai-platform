# Execution Plan: ANY-697 Runtime Versions (PostgreSQL 18, Node 24)

## Status

- State: active
- Owner: agent
- Created: 2026-10-21
- Last updated: 2026-10-21
- Review date: 2026-10-21
- Next action: run postgresql-check, full-check, atoms-proof, compose-smoke-prod; rehearse the
  16 -> 18 runbook on a local volume and record the result in the PR.
- Blocker: none

## Goal

Run PostgreSQL 18 and Node 24 everywhere; Python stays 3.12. Node source of truth is `.nvmrc`,
PostgreSQL source of truth is the base `infra/compose/docker-compose.yml`.

## Changes

- `web-mirror.Dockerfile`: `node:24-slim` in both stages.
- `postgres:18` in base and agent compose and the `backend.yml` service container.
- Prod and Atom Lab volumes mount at `/var/lib/postgresql` under new names
  (`postgres18-data`, `atom-lab-postgres18-data`); old PostgreSQL 16 volumes stay for rollback.
- `tests/architecture/test_runtime_versions_match.py` fails on version drift.
- Runbook: "Upgrading PostgreSQL 16 to 18" in `infra/deployment/README.md`.
- Runner: `prod-quiesce` and `prod-recovery-postgres-up`, sharing the drain and PostgreSQL-only
  helpers with `atom-lab-quiesce`/`atom-lab-recovery-postgres-up`, so the production cut-over
  runs on locked, bounded, fail-closed commands instead of hand-written shell. Aborting a quiesce
  goes through `prod-up`/`prod-ready`; no separate `prod-resume`.

## Out of scope

Python dependency updates, Portal (ANY-710), minor/digest pins, the VPS cut-over itself.
