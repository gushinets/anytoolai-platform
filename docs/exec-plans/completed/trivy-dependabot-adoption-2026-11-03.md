# Execution Plan: Trivy enforcement and Dependabot

## Status

- State: completed
- Owner: agent
- Created: 2026-11-03
- Last updated: 2026-11-04
- Review date: 2026-11-10
- Next action: review/merge after successful PR checks; confirm hosted Dependabot runs after merge.
- Blocker: none
- Linear: https://linear.app/paveldik/issue/ANY-813/enforce-trivy-dependency-gate-and-enable-dependabot-updates

## Goal

Make dependency vulnerabilities fail CI and propose dependency updates through Dependabot,
while preserving the existing security reports and Linear PR metadata requirements.

## Scope

- Enforce the existing pinned Trivy scanner for High/Critical dependency vulnerabilities,
  including dev dependencies; retain all severity levels in the report.
- Preserve Dockerfile misconfiguration reports, SARIF artifacts and weekly scans.
- Ensure the existing required CI gate cannot pass when the dependency scan fails.
- Configure weekly Dependabot updates for the actual uv, pnpm/npm, Actions and Docker manifests,
  with a release cooldown and no automatic merging.
- Document the commands, scan limits and manual Linear metadata triage for bot PRs.

Ruff, other tools, application behavior, dependency upgrades, automatic ticket creation and
repository administration settings are outside this change.

## Relevant docs

- `AGENTS.md`
- `docs/agent/coding-conventions.md`
- `docs/architecture/package-layering.md`
- `docs/exec-plans/active/any-716-trivy-ci-report-only.md`
- <https://github.com/mokevnin/dev-quality-gates/blob/main/docs/adopt.md>

## Contracts touched

- Config: Trivy/GitHub Actions and Dependabot only.
- API / DB / Events / Frontend: unchanged.

## Implementation steps

- [x] Inspect the current workflows, dependency manifests and PR metadata policy; run doctor.
- [x] Scan a clean source snapshot and record findings without creating silent exceptions.
- [x] Add Trivy enforcement and Dependabot configuration.
- [x] Validate the configuration and prove the scanner fails on a real vulnerable fixture.
- [x] Review the diff and document results and limits.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] Pinned Trivy scan of a clean source snapshot.
- [x] Deliberately vulnerable lockfile produces a nonzero scanner result.
- [x] GitHub workflow and Dependabot schema validation.
- [x] Relevant repository checks.

Trivy 0.76.1 was downloaded into the ignored temporary directory and its archive SHA-256 was
checked against the immutable upstream release. The vulnerability database was updated on
2026-11-03 at 13:13 UTC. A clean snapshot of `ce99f7ed` scanned all seven lockfiles and all three
Dockerfiles: no High/Critical dependency findings; two Medium `CVE-2026-118764` findings for
minimatch 5.1.9 and 10.2.6; one Low worker `DS-0026` misconfiguration, previously accepted in
ANY-726. All three findings remain visible, with no baseline or suppression files.

An assert-based self-check executed the gate command read from the workflow against the source
snapshot (exit 0) and an isolated dev-only lodash 4.17.20 lockfile (exit 1). Removing
`--include-dev-deps` made the same fixture exit 0, proving dev dependencies are included. The
fixture was kept outside tracked source and removed after verification.

Additional validation passed:

- actionlint 1.7.12 on both modified workflows (checksum-verified temporary binary).
- Current SchemaStore Dependabot schema, plus rejection of an invalid hourly schedule.
- Assert-based coverage of all seven Python manifests, weekly schedules and seven-day cooldowns.
- Required-status failure guard and reusable/scheduled scan configuration self-checks.
- `python scripts/agent/runner.py validate-docs`.
- `python scripts/agent/runner.py validate-architecture`.
- Existing runtime-version, Atom Lab workflow and PR-metadata tests.
- `git diff --check`.

The full application suite was not rerun locally for this CI/configuration change. The checks
above predate publication; hosted CI results are recorded on the PR linked from ANY-813.
Actual Dependabot update jobs start after the configuration reaches the default branch.

### Composite-action coverage fix (2026-11-04)

The GitHub Actions update entry now explicitly includes `/` and
`/.github/actions/compose-stack-check`. The root scope covers workflow files and root action
manifests, but does not recursively cover nested composite actions; see the
[Dependabot directory reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#directories-or-directory)
and [upstream file fetcher](https://github.com/dependabot/dependabot-core/blob/main/github_actions/lib/dependabot/github_actions/file_fetcher.rb).

The regression test discovers actual composite-action manifests under `.github/actions` and
requires their directories alongside the root workflow scope. It failed on the old configuration
with `/.github/actions/compose-stack-check` missing, then passed with the fix. The focused test and
existing runtime-version, PR-metadata and Atom Lab workflow tests passed (26 tests), as did doctor,
the current SchemaStore Dependabot schema, architecture validation, documentation validation and
`git diff --check`. Fresh hosted CI and independent reviews remain PR checks.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-03 | Apply only Trivy and Dependabot. | Explicit user scope after reviewing the adoption plan. |
| 2026-11-03 | Preserve Linear metadata checks for bot PRs. | A human must attach a real issue; a bot must not invent an issue ID or bypass the check. |
| 2026-11-03 | Gate High/Critical dependency findings; report every severity and Dockerfile finding. | Fresh database scan has no High/Critical findings. Two Medium minimatch findings and accepted worker DS-0026 stay visible without suppressions or dependency changes. |
| 2026-11-03 | Reuse the Trivy workflow from backend CI and explicitly fail `full-check` on scan failure. | Required checks stay named as before; a failed prerequisite must not leave a skipped required job. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-03 | Repository doctor passed; existing Trivy is report-only and no Dependabot config exists. | Inspect current scan findings and implement the two integrations. |
| 2026-11-03 | Implemented and locally validated the two integrations, including real scanner failure behavior. | Publish changes and verify hosted execution after merge. |

## Follow-up debt

- Production image scanning is outside the filesystem dependency gate.
