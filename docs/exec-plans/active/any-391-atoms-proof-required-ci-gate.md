# Execution Plan: ANY-391 atoms-proof Required CI Gate

## Status

- State: active
- Owner: agent
- Created: 2026-08-28
- Last updated: 2026-08-28
- Review date: 2026-08-28
- Next action: none — implementation and two rounds of code-review fixes landed; move to
  `completed/` once merged and the job is confirmed green on a real PR.
- Blocker: none

## Goal

Run the deterministic, credential-free `atoms-proof` command (`scripts/agent/runner.py`) in CI on
every pull request and every push to `main`, with the same boot/run/log-dump/teardown shape this
repo already uses for `compose-smoke-dev`/`live-canary.yml`, so a PR cannot pass the kernel CI gate
if the 11-atom/composite-workflow proof fails.

## Scope

### In scope

- New `atoms-proof` job in `.github/workflows/backend.yml`, under the file's existing
  `pull_request` / `push: branches: [main]` triggers (no new trigger config needed).
- Own disposable dev Compose stack (own `dev-up`/`dev-down`), not shared with `compose-smoke-dev`.
- `quick-check --bootstrap-only` step before `dev-up` (same as `live-canary.yml`), since
  `uv sync --frozen --group dev` alone does not install `anytoolai_platform_core`, and
  `atoms_proof.py` imports it.
- Compose log dump on failure, teardown in `if: always()`, `.agent/atoms-proof/` evidence artifact
  upload with `if-no-files-found: ignore`.
- `timeout-minutes: 30`, matching `live-canary.yml`'s identical job shape.
- Regression test in `tests/test_runner.py` parsing `backend.yml` to assert the job's shape.
- `docs/product-specs/mvp-a-platform-kernel.md` Proof Surface note.

- `.github/actions/compose-stack-check/` composite action, extracted round 2 to de-duplicate the
  boot/run/log-dump/teardown/upload sequence across `compose-smoke-dev`, `live-canary`, and
  `atoms-proof` (see Decision log — this reverses round 1's narrower "don't extract yet" call,
  by explicit user choice, after round 2 review found the duplication was broader than round 1's
  fix addressed).

### Out of scope

- Marking the new job as a required branch-protection status check — manual GitHub Settings
  change outside this repo, for someone with repo-settings access (see
  `docs/handoffs/postgresql-required-gate-coverage.md` precedent for the same pattern).
- Any change to `atoms_proof.py`/`_run_proof_script()` themselves — both already satisfy this
  ticket's credential-free/evidence/DB-URL-via-env requirements as-is (see `plans/ANY-391.md`).
- Migrating `compose-smoke-prod` onto the new composite action — round 2 review named exactly
  `compose-smoke-dev`/`live-canary`/`atoms-proof`; `compose-smoke-prod` uses a different
  command pair (`prod-up`/`prod-down`) and has no log-dump-on-failure step today, so it wasn't
  folded in. Tracked as follow-up debt below.

## Relevant docs

- `plans/ANY-391.md` (issue + implementation plan + code-review findings, both rounds)
- `docs/product-specs/mvp-a-platform-kernel.md` (Proof Surface)
- `docs/handoffs/postgresql-required-gate-coverage.md` (required-status-check precedent)

## Contracts touched

- New composite action interface: `.github/actions/compose-stack-check/action.yml`'s `inputs:`
  (`bootstrap-quick-check`, `check-command`, `check-step-name`, `openai-api-key`,
  `live-canary-token`, `upload-evidence`, `evidence-artifact-name`, `evidence-artifact-path`, plus
  `python-version`/`uv-version`/`dev-up-ready-timeout` defaults). Any future change to this
  contract must update all three call sites (`backend.yml`'s `compose-smoke-dev`/`atoms-proof`,
  `live-canary.yml`'s `live-canary`) together.

## Implementation steps

- [x] Add `atoms-proof` job to `.github/workflows/backend.yml`.
- [x] Add regression test `test_required_backend_workflow_runs_atoms_proof` to
      `tests/test_runner.py`.
- [x] Update `docs/product-specs/mvp-a-platform-kernel.md` Proof Surface section.
- [x] Local end-to-end sanity check: `dev-up` -> `atoms-proof` -> `dev-down`, confirmed exit 0 and
      `.agent/atoms-proof/` evidence file written.
- [x] Code review (`/code-review high`, 2026-08-28) found 3 gaps:
  - Missing `timeout-minutes` on the new job — every PR/push run, unlike `live-canary.yml`'s
    weekly schedule, so a hang would consume GitHub's 360-minute default instead of failing fast.
    Fixed: added `timeout-minutes: 30`, matching `live-canary.yml`'s identical job shape. Also
    added a test assertion for it.
  - No exec plan under `docs/exec-plans/active/` for this non-trivial change (new required CI job
    + regression test + docs update), per AGENTS.md's "before coding" requirement. Fixed: this
    file.
  - `quick-check --bootstrap-only` duplicated verbatim across `live-canary.yml` and `backend.yml`.
    Root cause (`uv sync --frozen --group dev` not installing `anytoolai_platform_core`) not
    eliminated — no existing composite-action/reusable-workflow precedent in this repo to justify
    extracting one for a single shared line yet. Left as-is, tracked below (superseded round 2).
- [x] Code review round 2 (`/code-review high`, 2026-08-28) found the duplication was broader than
      round 1's fix addressed: the *entire* boot/run/log-dump/teardown/upload sequence (not just
      the one bootstrap line) was now duplicated across `compose-smoke-dev`, `live-canary`, and
      `atoms-proof`. Asked the user how to proceed (fixing this means touching the already-working
      required-gate job and the credentialed weekly job, beyond this ticket's narrow scope) — user
      chose to extract a composite action now rather than defer. Fixed:
  - New `.github/actions/compose-stack-check/action.yml`: parameterized composite action covering
    checkout/setup-python/setup-uv/`uv sync`/optional bootstrap/`dev-up`/check-command/log-dump/
    teardown/optional evidence-upload. Verified `docker-compose.yml` already defaults
    `OPENAI_API_KEY`/`ANYTOOLAI_LIVE_CANARY_TOKEN` via `${VAR:-}`, so passing empty-string inputs
    for credential-free callers is behavior-preserving.
  - `compose-smoke-dev`, `atoms-proof` (`backend.yml`), and `live-canary` (`live-canary.yml`)
    rewritten to a single `uses: ./.github/actions/compose-stack-check` step each with the
    appropriate `with:` inputs.
  - The round-1 secret-scoping code-review finding (secrets confined to exactly the dev-up and
    check-command steps) re-verified at the new architectural layer: scoping now lives inside
    `action.yml`, confirmed by a new dedicated test.
  - Tests rewritten for the new structure: added
    `test_compose_stack_check_action_scopes_secrets_to_exactly_two_steps`,
    `test_compose_stack_check_action_shape`,
    `test_live_canary_workflow_delegates_to_compose_stack_check_with_secrets`; updated
    `test_required_backend_workflow_runs_atoms_proof` for the single-step-with-inputs shape.
  - `compose-smoke-prod` intentionally left un-migrated (not named in the round-2 finding, uses a
    different command pair, no log-dump-on-failure step today) — tracked below.

## Validation

- [x] `uv run pytest tests/test_runner.py -k "compose_stack_check or atoms_proof or
      postgresql_check_runs_canonical or live_canary_workflow"` — 7 passed.
- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py quick-check` — 955 passed.
- [x] Manual end-to-end (pre-composite-action refactor): `dev-up` -> `atoms-proof` (11/11 atoms +
      3/3 composites passed, exit 0, evidence file written) -> `dev-down`. The composite-action
      refactor only changes how CI *wires* these same `runner.py` commands, not the commands
      themselves, so this run remains representative.
- [x] YAML syntax validated for `action.yml`, `backend.yml`, `live-canary.yml` via
      `yaml.safe_load`. No `actionlint`/`act` available in this environment to lint/execute the
      composite action directly.
- [ ] Confirm the job runs green on a real PR in GitHub Actions, including the artifact upload and
      the composite-action call itself (only observable once opened against GitHub).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-28 | New job lives inside `backend.yml`, not a new workflow file. | `backend.yml`'s triggers already match the ticket's requirement verbatim; `client-handoff-smoke.yml` is a separate file specifically because it's path-filtered and not required — the opposite of this ticket's goal. |
| 2026-08-28 | New job boots its own dev Compose stack rather than adding a step to `compose-smoke-dev`. | Ticket AC: "do not run two checks against the same stack instance." GitHub Actions jobs already run on separate runners by default, so a new job gets isolation for free. |
| 2026-08-28 (round 1, superseded) | Did not extract the duplicated `quick-check --bootstrap-only` step into a composite action. | Only two call sites for that one line existed; adding an abstraction for a single shared line would be premature. Superseded once round 2 review found the *whole* boot/teardown sequence (not just this line) was duplicated three ways. |
| 2026-08-28 (round 2) | Extracted `.github/actions/compose-stack-check` and migrated `compose-smoke-dev`/`live-canary`/`atoms-proof` onto it, touching already-working CI outside this ticket's narrow scope. | User's explicit choice when asked, given three real call sites (past the classic "rule of three" threshold) rather than the two round 1 considered. |
| 2026-08-28 (round 2) | `compose-smoke-prod` left un-migrated. | Not named in the round-2 finding; different command pair (`prod-up`/`prod-down`), no log-dump-on-failure step today — migrating it would need extending the action's contract, better done as its own deliberate follow-up. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-28 | Implemented per `plans/ANY-391.md`: `atoms-proof` job in `backend.yml`, regression test, docs update. Verified end-to-end locally (quick-check green, real dev-up/atoms-proof/dev-down cycle green). | Await/act on code review. |
| 2026-08-28 | `/code-review high` round 1 found 3 gaps (missing `timeout-minutes`, no exec plan, duplicated bootstrap step). Fixed the first two; documented the third as accepted duplication. Filed this exec plan. | Re-run `quick-check` and targeted suite to confirm still green, then commit. |
| 2026-08-28 | `/code-review high` round 2 found the duplication was broader than round 1 addressed (whole boot/teardown sequence, 3 call sites). Asked the user; they chose to extract a composite action now. Built `.github/actions/compose-stack-check`, migrated all 3 named jobs onto it, rewrote the affected tests. `quick-check` green (955 passed), targeted suite green (7 passed). | Re-confirm on a real PR once opened; commit. |

## Open questions

- None.

## Follow-up debt

- `compose-smoke-prod` still duplicates its own boot/run/teardown sequence rather than using
  `.github/actions/compose-stack-check`. If it ever needs a log-dump-on-failure step or other
  parity with the other jobs, extend the composite action's contract to cover the
  `prod-up`/`prod-down` command pair and migrate it too.
