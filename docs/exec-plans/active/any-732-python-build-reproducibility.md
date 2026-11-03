# Execution Plan: ANY-732 Python build reproducibility

## Status

- State: blocked
- Owner: agent
- Created: 2026-11-03
- Last updated: 2026-11-03
- Review date: 2026-11-03
- Next action: Run the complete gate on CI with passwordless sudo and Windows baseline
- Blocker: Host requires interactive sudo for an existing cross-user permissions test

## Goal

Automated Python installs reject stale locks and use fixed build tools, including isolated builds.

## Scope

CI workflows, Compose action, Python bootstrap/full-check, Docker images and packaging tests.
Keep independent project roots, editable installs and existing application dependencies.

## Implementation steps

- [x] Introduce one shared uv configuration with exact build constraints.
- [x] Use locked sync and prepared-environment execution across automation.
- [x] Apply the configuration explicitly to pip/build/sync and fingerprint it.
- [x] Test stale-lock rejection, build versions and packaging; run repository checks and builds.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-03 | Shared uv config for pip/build and ordinary tool installation; checked project metadata mirrors for sync | uv 0.13.4 sync uses project metadata, ignoring build constraints in --config-file. A regression enforces identical mirrors. |

## Validation

Pending focused tests, full-check, docs checks, and Docker builds. Initial system-Python doctor
failed (missing pytest/pydantic); existing managed environment uses Python 3.12.13.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-03 | Inventoried root/app locks, CI, runner, Docker and temporary package builds | Implement shared configuration and regressions |

## Implementation evidence

- uv 0.13.4 regenerated all five locks. Only lock revision and build-constraint metadata
  changed; every parsed application package entry matches HEAD.
- Build pins: setuptools 82.0.1, wheel 0.46.3, packaging 26.2. Project metadata mirrors
  are checked against the shared uv configuration on every baseline run.
- Clean-cache tests assert actual build-environment versions for wheel builds, editable
  pip installs, and locked project sync. Root/API/worker metadata drift is rejected without
  changing any lockfile. Bootstrap fingerprints include the pins and root pyproject.
- Final full-check build stage (product suite plus bootstrap/build regressions, including slow
  clean-cache probes): 247 passed. CI now runs those slow probes in full-check.
- Doctor passes with Python 3.12.13 and uv 0.13.4. Config, architecture, documentation and
  generated-document checks passed.
- Existing runner test requiring passwordless sudo to nobody fails on this host. No skip or
  error suppression was added. Windows CI has not been run from this session.
- The repository-wide prohibited local-skill-name scan found pre-existing references in other
  tickets' execution plans; those unrelated files were left unchanged.

- Final focused regressions: 276 passed, 12 existing skips, one known sudo-dependent test
  deselected after recording its failure. All nine Atom Lab architecture tests pass after
  updating their expected CI command.
- API dev/prod and worker Docker builds pass with final constraints. Local package imports
  pass inside each image using the prepared environment and --no-sync.

## Final validation disposition

Frontend-check passed completely on retry (the initial concurrent-build run timed out in an
existing five-second frontend lint test). Broad full-check baseline: 3007 passed, 12 skipped,
492 deselected, three failures. Two are resolved and individually verified: the architecture
assertion now expects --no-sync; refreshing bootstrap after changing pins resolves the readiness
marker failure (the final focused suite passes). The remaining failure is the pre-existing
cross-user activation-marker test requiring passwordless sudo. Therefore the complete gate is
not claimed green. Windows CI still needs to run. Implementation is complete; acceptance remains
blocked on that validation environment. No GitHub writes were made.

All changed Python lines pass the existing Ruff rules; pre-existing lint findings remain.
`git diff --check` passes. A sanitized context bundle was collected for the sudo failure.
