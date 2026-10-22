# Execution Plan: Trivy CI in report-only mode (ANY-716)

## Status

- State: active
- Owner: agent
- Created: 2026-10-22
- Last updated: 2026-10-22
- Review date: 2026-10-29
- Next action: confirm the PR Trivy run and finish local quick-check; merge remains owner-controlled.
- Blocker: none
- Linear: https://linear.app/paveldik/issue/ANY-716/podklyuchit-trivy-v-ci-anytoolai-platform-bez-blokirovki-pr

## Goal

Run Trivy in CI and expose dependency and Dockerfile findings without making them a PR gate.

## Scope

- Add `.github/workflows/trivy.yml` for PRs, main pushes, weekly scans and manual runs.
- Scan repository dependencies, including dev dependencies, and Dockerfile misconfigurations.
- Preserve SARIF as an artifact on every run; upload to GitHub Security only outside PR events.
- Document report-only behavior in `README.md`.
- Deduplicate Linear remediation tasks against Platform Kernel, Client Surfaces and cross-project
  search results, including archived issues. Payment Portal issues cover another repository.

No application, lockfile, branch-protection or runtime-container changes. Production image scanning
and enforcement are follow-up scope, not claims made by this filesystem scan.

## Relevant docs

- `docs/agent/coding-conventions.md`
- `docs/agent/codex-operating-model.md`
- `docs/architecture/platform-boundaries.md`

## Contracts touched

- Config: GitHub Actions workflow only; no runtime contracts.
- API / DB / Events / Frontend: unchanged.

## Implementation steps

- [x] Add SHA-pinned Trivy action with explicit scanner version, dev coverage and exit-code 0.
- [x] Publish SARIF artifact and main-branch Code Scanning results with minimal permissions.
- [x] Document triggers, coverage and non-blocking behavior.
- [x] Create only missing Linear tasks for current dependency and Dockerfile findings.
- [ ] Finish repository quick-check; workflow validation and the scan with known findings passed.
- [ ] Review the final diff and open a PR; confirm actual GitHub scan evidence.

## Validation

- Doctor: passed in the isolated worktree.
- Baseline experiment on main `6a0c3427`: Trivy 0.74.0 with a fresh DB matched all 24 Dependabot
  alerts exactly and found two High and three Low Dockerfile misconfigurations.
- [x] actionlint 1.7.12; local SARIF scan exited 0 with 29 findings, including Critical certifi.
- [ ] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py validate-docs`
- [ ] Actual PR workflow run: successful scan and downloadable SARIF artifact.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-22 | Findings use exit-code 0; scanner/upload errors remain visible in an optional workflow. | User explicitly requested no PR blocking. Existing required checks stay unchanged. |
| 2026-10-22 | Upload Code Scanning only for non-PR runs. | Fork and Dependabot PRs retain artifact reports without needing a write token. |
| 2026-10-22 | Use Trivy 0.76.1 and trivy-action v0.36.0 pinned by SHA. | Latest published stable versions verified against upstream GitHub releases. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-10-22 | Implemented the workflow; actionlint, docs checks, report-only SARIF experiment and independent review passed. Created and read back ANY-717 through ANY-726. | Confirm actual PR scan and local quick-check; main publication follows merge. |

## Remediation coverage

All ten issues were read back: correct project, exactly one type label and one function label,
no directory labels. Eight dependency tasks cover all 24 open Dependabot alerts; the other two
cover the five Dockerfile findings. No existing issue was changed.

- [ANY-717](https://linear.app/paveldik/issue/ANY-717/critical-obnovit-certifi-vo-vseh-python-lock-fajlah-platformy): certifi.
- [ANY-718](https://linear.app/paveldik/issue/ANY-718/high-obnovit-vite-i-ustranit-pyat-uyazvimostej-dev-servera): vite.
- [ANY-719](https://linear.app/paveldik/issue/ANY-719/high-obnovit-sharp-v-web-runtime-platformy-do-0355): sharp.
- [ANY-720](https://linear.app/paveldik/issue/ANY-720/high-ustranit-source-map-js-121-v-cepochke-magicast): source-map-js.
- [ANY-721](https://linear.app/paveldik/issue/ANY-721/medium-obnovit-nextjs-platformy-i-ustranit-cache-poisoning): next.
- [ANY-722](https://linear.app/paveldik/issue/ANY-722/medium-obnovit-multidict-vo-vseh-python-lock-fajlah-platformy): multidict.
- [ANY-723](https://linear.app/paveldik/issue/ANY-723/medium-obnovit-mako-i-ustranit-windows-path-traversal): Mako.
- [ANY-724](https://linear.app/paveldik/issue/ANY-724/medium-obnovit-vitest-i-vitestmocker-do-ispravlennyh-versij): vitest.
- [ANY-725](https://linear.app/paveldik/issue/ANY-725/high-zapuskat-worker-i-web-kontejnery-platformy-bez-root): nonroot.
- [ANY-726](https://linear.app/paveldik/issue/ANY-726/low-razobrat-preduprezhdeniya-trivy-o-healthcheck-v-dockerfile): healthchecks.

## Follow-up debt

- Production image vulnerability scanning is outside this initial filesystem integration.
- Enforcement remains disabled until separately requested by the owner.
