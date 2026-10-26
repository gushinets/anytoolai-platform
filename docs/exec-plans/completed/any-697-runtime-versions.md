# Execution Plan: ANY-697 Runtime Versions (PostgreSQL 18, Node 24)

## Status

- State: completed
- Owner: agent
- Created: 2026-10-21
- Last updated: 2026-10-25
- Review date: 2026-10-25
- Next action: none. The operator-run VPS data migration follows the runbook in
  `infra/deployment/README.md` and is not tracked by this plan.
- Blocker: none

## Goal

Run PostgreSQL 18 and Node 24 everywhere; Python stays 3.12. Node source of truth is `.nvmrc`,
PostgreSQL source of truth is the base `infra/compose/docker-compose.yml`.

## Changes

- `web-mirror.Dockerfile`: `node:24-slim` in both stages.
- `postgres:18` in base and agent compose and the `backend.yml` service container.
- Prod and Atom Lab overlays moved to PostgreSQL 18 in the switch revision (ANY-714): volumes
  `postgres18-data` / `atom-lab-postgres18-data` mounted at `/var/lib/postgresql`; the old
  PostgreSQL 16 volumes stay for rollback.
- `tests/architecture/test_runtime_versions_match.py` fails on version drift.
- Runbook: "Upgrading PostgreSQL 16 to 18" in `infra/deployment/README.md`.
- Runner: `prod-quiesce` and `prod-recovery-postgres-up`, sharing the drain and PostgreSQL-only
  helpers with `atom-lab-quiesce`/`atom-lab-recovery-postgres-up`, so the production cut-over
  runs on locked, bounded, fail-closed commands instead of hand-written shell. Aborting a quiesce
  goes through `prod-up`/`prod-ready`; no separate `prod-resume`.

## Staged rollout

Step 1 of the cut-over runs `prod-quiesce` on the revision still running PostgreSQL 16, so the
command had to be deployed before the switch. It landed in two revisions:

- tooling revision (ANY-713, PR #194): Node 24, PostgreSQL 18 for dev/agent/CI, `prod-quiesce`,
  `prod-recovery-postgres-up`, the runbook, and the drift test with prod and Atom Lab staged on 16;
- switch revision (ANY-714, PR #195): prod and Atom Lab overlays on PostgreSQL 18 and the new
  volumes, `STAGED_POSTGRES_MAJORS` emptied.

## Out of scope

Python dependency updates, Portal (ANY-710), minor/digest pins, the VPS cut-over itself.
