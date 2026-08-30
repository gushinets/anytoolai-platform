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
  upload with `if-no-files-found: error` (fail-closed, see Progress log — team-lead review round).
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
    setup-python/setup-uv/`uv sync`/optional bootstrap/`dev-up`/check-command/log-dump/teardown/
    optional evidence-upload. Checkout is deliberately **not** one of the action's
    responsibilities: each calling job performs its own `actions/checkout` step before invoking
    the local action (see the checkout-ordering fix logged below — a local action reference can
    only be resolved by the runner after the repo is already checked out). Verified
    `docker-compose.yml` already defaults
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
      composite action directly -- this gap turned out load-bearing, see below.
- [x] Real PR run (PR #90) caught a bug `yaml.safe_load`/structural tests couldn't:
      `compose-smoke-dev`/`atoms-proof` both failed in ~3s with "Can't find action.yml ... did you
      forget to run actions/checkout" -- a local action reference (`uses: ./.github/actions/...`)
      can only be resolved by the runner after the repo is checked out, but `actions/checkout` was
      placed *inside* the composite action itself (chicken-and-egg). Fixed: removed checkout from
      `action.yml`, restored as a job-level step before the composite-action call in all three
      callers; updated the two affected tests for the resulting 2-step (checkout + action-call)
      shape. Re-ran targeted suite (7 passed) and `quick-check` (955 passed).
- [x] Confirmed the job runs green on PR #90 after the checkout-ordering fix (11/11 atoms, 3/3
      composites, evidence artifact uploaded).
- [x] Team-lead code review: two findings verified against current code and fixed —
  - `if-no-files-found: ignore` -> `error` on the evidence-upload step. Verified
    `write_evidence_report()` runs (and its exception isn't swallowed) on every `atoms_proof.py`
    exit path except the three early-return error paths, all of which already return non-zero and
    redden the job via the check-command step itself — so `error` cannot fire differently from
    today's outcome on any currently-reachable path, while guarding against a future
    artifact-path misconfiguration going unnoticed. Updated
    `test_compose_stack_check_action_shape`'s assertion.
  - `astral-sh/setup-uv` pin: confirmed via the action's own bundled source (`KNOWN_CHECKSUMS` in
    v8.1.0's `dist/setup/index.cjs`) that v8.1.0 has no checksum entry for uv `0.11.16`, so
    checksum verification is silently skipped (`debug("No checksum found ...")`, not a warning or
    failure) on every job that pins this uv version today. v8.2.0's changelog confirms it added
    `0.11.16`'s checksum. Bumped the pin to
    `astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0` (verified against the
    live `v8.2.0` tag) in all 6 repo occurrences, not just this ticket's new file — round 2 already
    rejected bumping only the new composite action as creating a version split; bumping everywhere
    at once avoids that split instead of recreating it.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-28 | New job lives inside `backend.yml`, not a new workflow file. | `backend.yml`'s triggers already match the ticket's requirement verbatim; `client-handoff-smoke.yml` is a separate file specifically because it's path-filtered and not required — the opposite of this ticket's goal. |
| 2026-08-28 | New job boots its own dev Compose stack rather than adding a step to `compose-smoke-dev`. | Ticket AC: "do not run two checks against the same stack instance." GitHub Actions jobs already run on separate runners by default, so a new job gets isolation for free. |
| 2026-08-28 (round 1, superseded) | Did not extract the duplicated `quick-check --bootstrap-only` step into a composite action. | Only two call sites for that one line existed; adding an abstraction for a single shared line would be premature. Superseded once round 2 review found the *whole* boot/teardown sequence (not just this line) was duplicated three ways. |
| 2026-08-28 (round 2) | Extracted `.github/actions/compose-stack-check` and migrated `compose-smoke-dev`/`live-canary`/`atoms-proof` onto it, touching already-working CI outside this ticket's narrow scope. | User's explicit choice when asked, given three real call sites (past the classic "rule of three" threshold) rather than the two round 1 considered. |
| 2026-08-28 (round 2) | `compose-smoke-prod` left un-migrated. | Not named in the round-2 finding; different command pair (`prod-up`/`prod-down`), no log-dump-on-failure step today — migrating it would need extending the action's contract, better done as its own deliberate follow-up. |
| 2026-08-28 | Moved `actions/checkout` out of `compose-stack-check/action.yml` back to a job-level step in all three callers. | PR #90's real CI run failed in ~3s: a local action reference can't be resolved before the repo is checked out, so checkout can't itself live inside that same local action. Neither `yaml.safe_load` nor the structural tests model this GitHub Actions resolution-order semantic. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-28 | Implemented per `plans/ANY-391.md`: `atoms-proof` job in `backend.yml`, regression test, docs update. Verified end-to-end locally (quick-check green, real dev-up/atoms-proof/dev-down cycle green). | Await/act on code review. |
| 2026-08-28 | `/code-review high` round 1 found 3 gaps (missing `timeout-minutes`, no exec plan, duplicated bootstrap step). Fixed the first two; documented the third as accepted duplication. Filed this exec plan. | Re-run `quick-check` and targeted suite to confirm still green, then commit. |
| 2026-08-28 | `/code-review high` round 2 found the duplication was broader than round 1 addressed (whole boot/teardown sequence, 3 call sites). Asked the user; they chose to extract a composite action now. Built `.github/actions/compose-stack-check`, migrated all 3 named jobs onto it, rewrote the affected tests. `quick-check` green (955 passed), targeted suite green (7 passed). Committed and pushed (PR #90). | Check PR #90's real CI run. |
| 2026-08-28 | PR #90's CI failed: `compose-smoke-dev`/`atoms-proof` both errored in ~3s ("Can't find action.yml ... did you forget to run actions/checkout") because `actions/checkout` was placed inside the composite action instead of at job level, so the local action reference couldn't resolve. Fixed: checkout moved back to a job-level step before the composite-action call in all three callers; updated the two tests that assumed a single-step job. `quick-check` green (955 passed), targeted suite green (7 passed). | Push the fix, recheck PR #90's CI, then mark this plan `completed/` once green. |
| 2026-08-28 | PR #90 confirmed green after the checkout fix. Three inline-comment findings triaged (1 fixed: stale exec-plan text; 2 rejected with documented reasoning). A self-review ("me #1") flagged the real blocker: `atoms-proof` isn't yet in the `protect main` ruleset's required status checks, so ANY-391's acceptance criteria aren't fully met — GitHub API access available here (`repo`/`workflow` scopes) returned 404 on the PUT needed to fix it, so this needs someone with repo-admin access; the request text and payload were prepared for them. | Await admin action on the ruleset; separately, await/act on further review. |
| 2026-08-28 | Team-lead review round found two more issues in `.github/actions/compose-stack-check/action.yml`: `if-no-files-found: ignore` should fail closed, and the `setup-uv` pin lacks a checksum for the requested uv version. Both verified against actual code/upstream source (not taken on faith) and confirmed real. Fixed: `if-no-files-found: error` (plus test update); `setup-uv` bumped to v8.2.0 across all 6 repo pins (not just this file, to avoid recreating the version-split round 2 already rejected). `quick-check` green (955 passed), targeted suite green (7 passed). | Recheck PR CI, then mark this plan `completed/` once green and the ruleset is updated. |

## Open questions

- None.

## Follow-up debt

- `compose-smoke-prod` still duplicates its own boot/run/teardown sequence rather than using
  `.github/actions/compose-stack-check`. If it ever needs a log-dump-on-failure step or other
  parity with the other jobs, extend the composite action's contract to cover the
  `prod-up`/`prod-down` command pair and migrate it too.
