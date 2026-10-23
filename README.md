# AnytoolAI Platform

This repository contains the AnytoolAI platform monorepo and its current MVP-A/MVP-B implementation.

The repo is intentionally agent-friendly: short `AGENTS.md`, repo-local docs, executable plans,
validation scripts, architecture tests, config validation, CI, and generated documentation are kept
alongside the implementation.

## Quick start

```bash
python scripts/agent/runner.py doctor
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
```

`python scripts/agent/runner.py <command>` is the canonical cross-platform interface. Use
`python3` where that is the Python 3 executable. `make <target>` recipes are optional thin
aliases over the runner (see `Makefile`); on Windows without native GNU Make, run `make` via
git-bash/WSL or call the runner directly.
The baseline gate includes:

- config validation
- architecture validation
- a DB-free backend pytest subset

It intentionally excludes frontend checks and any test DB provisioning.
The script self-manages `.quick-check-venv` so it does not need to install packages into a system Python.
It always re-execs into `.quick-check-venv`, even if you started from another active virtualenv.
It strips caller-provided `PYTHONPATH`, so no manual `PYTHONPATH` setup is required.
GitHub Actions runs this same baseline command on both Linux and Windows, and the backend workflow is required on pull requests plus pushes to `main`.

`atoms-proof` and `live-canary` (see `docs/product-specs/mvp-a-platform-kernel.md`) also require
`.quick-check-venv` and launch their subprocess with its python, not the caller's own interpreter.
Run `quick-check` once first to bootstrap it; otherwise these two commands fail fast with a setup
instruction instead of a raw `No module named 'markdown_it'` error.

Python dependency management uses `uv`, not `pip`. Use `uv add <package>` for runtime dependencies,
`uv add --dev <package>` for dev dependencies, and do not hand-edit `uv.lock`.

Generated docs are written by `generate-docs`. Use `generate-docs --check` in review and CI to
detect drift without changing tracked files.

Use `dev-up`, `dev-status`, and `dev-down` through the runner for a worktree-isolated Compose
environment. The status command prints the derived API and database endpoints. `platform-api`
runs with hot-reload in this dev environment. For the production overlay (`prod-up`/`prod-status`/
`prod-down`) and the full dev/prod split, see `infra/deployment/README.md`.

When blocked, `collect-context` writes a privacy-sanitized JSON bundle under the ignored
`.agent/context/` directory. API and worker runtime logs are structured JSON and use the same
redaction rules.

`full-check` runs the baseline, locked frontend checks (typecheck, unit tests, generated
OpenAPI-contract drift check, build), and the implemented Freelancer suite tests. Kernel and browser
smoke commands will be added only when feature issues deliver real vertical slices.

## Security scanning

`.github/workflows/trivy.yml` runs Trivy on pull requests, pushes to `main`, weekly on Monday at
03:17 UTC, and manually through GitHub Actions. It scans the repository lockfiles, including dev
dependencies, and Dockerfile misconfigurations. Every run saves a `trivy-filesystem-sarif` artifact;
non-PR runs also publish results to GitHub Security under `trivy-filesystem`.

This workflow is advisory: findings use exit code 0 and it is not a required PR check. Scanner or
report-upload errors remain visible as workflow failures. Existing required checks are unchanged.
It does not build or scan production images; GitHub's existing secret scanning and push protection
remain separate.

SonarQube Cloud analyzes the repository as one public project on the **Free** plan:
[anytoolai-platform](https://sonarcloud.io/project/overview?id=gushinets_anytoolai-platform),
in the `gushinets` organization. Its GitHub App is installed with selected-repository access to
`gushinets/anytoolai-platform`; automatic import of other repositories is disabled.
SonarQube's automatic analysis runs on pushes to `main` and pull requests targeting `main`.
The initial import also analyzes up to five recently active pull requests.

SonarQube reports are advisory. Its native Quality Gate check may report findings, but it is not a
required check in the `protect main` ruleset and does not block merging PRs. No scanner workflow,
`SONAR_TOKEN`, or Quality Gate waiting step is needed for this automatic integration. Automatic
analysis does not import test coverage or external analyzer reports. To add those later, switch
the project to CI-based analysis and disable automatic analysis first; the two methods must not
run together. See [SonarQube automatic analysis](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/automatic-analysis).

## MVPs

- MVP-A1: Atom Runtime Proof — backend proof of all 11 typed atoms individually and in composite workflows, with deterministic and live-provider evidence.
- MVP-A2: Client Surfaces — shared CE-kit, web mirror, consent/paywall/onboarding surfaces, kernel-demo CE, and browser evidence.
- MVP-B: Freelancer Validation Bundle v0 — five web-first Freelancer product bundles added through configs, prompts, schemas, workflows, result renderers, handoff maps, and product events; product Chrome Extensions are optional.

## First places to read

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/core-beliefs.md`
- `docs/agent/harness-engineering-map.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-a2-client-surfaces.md`
- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
