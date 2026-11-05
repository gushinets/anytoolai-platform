# Execution Plan: ANY-732 Python build reproducibility

## Status

- State: active
- Owner: agent
- Created: 2026-11-03
- Last updated: 2026-11-04
- Review date: 2026-11-04
- Next action: Verify SonarCloud on the head with the targeted port-test build restriction
- Blocker: None for the workflow fixes; full local baseline still needs passwordless sudo

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

## Merge-regression follow-up — 2026-11-04

The merge from main dropped prod-fake-up and moved its environment onto the port test. It also
introduced a frozen uv run that fails the prepared-environment policy test. Restore the boot
step/environment, switch the port test to --no-sync, and add a lifecycle regression before
pushing the corrected PR head. Keep the existing unconditional teardown.

The workflow now runs the port test with --no-sync, boots prod with its original test
environment, then runs smoke and unconditional teardown. The new workflow regression checks
that ordering and environment placement. Local validation: 8 workflow-policy tests passed;
11 port/lifecycle/architecture tests passed; documentation validation and diff whitespace
checks passed. Changed test lines introduce no Ruff findings. Push the corrected head and use
its CI results for the full gate; the earlier head's statuses do not establish acceptance.

## SonarCloud follow-up — 2026-11-04

On 50e8a5ef the quality gate has one remaining annotation: the port-test invocation lacks
--no-build. Add it specifically to the --no-sync command, which uses dependencies prepared by
the earlier locked sync. Update the lifecycle regression and run the exact invocation.
Installation and editable/isolated build paths remain enabled with pinned build constraints.
No rule exclusions, issue-state changes or quality-gate threshold changes are needed.

Validation: the port-test command with uv 0.13.4 passed all 8 tests; the 8 related workflow
regressions passed. Documentation validation and git diff --check passed. Remote SonarCloud
status must be verified on the pushed fix; the previous failing check belongs to 50e8a5ef.
