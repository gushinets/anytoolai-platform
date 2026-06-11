# Harness Engineering Map for First Commit

This document maps each major lesson from OpenAI's harness engineering article into concrete repository assets.

## 1. Start with an agent-shaped scaffold

Repo asset:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `pyproject.toml`
- `package.json`
- `.github/workflows/*`
- `scripts/agent/*`
- app/package skeletons

Reason: the first commit should give Codex structure, CI, formatting rules, package setup, and application framework.

## 2. Humans steer, agents execute

Repo asset:

- `docs/exec-plans/template.md`
- `docs/agent/codex-operating-model.md`
- `.github/ISSUE_TEMPLATE/agent-task.md`
- `.github/pull_request_template.md`

Reason: humans specify intent, acceptance criteria, and constraints; agents implement and validate.

## 3. Increase application legibility

Repo asset:

- `scripts/agent/run-kernel-smoke.sh`
- `scripts/agent/collect-context.sh`
- structured logs requirement in docs
- `docs/generated/*`
- `infra/compose/docker-compose.agent.yml`

Reason: Codex must be able to boot, inspect, query, and validate the system.

## 4. Repository knowledge is the system of record

Repo asset:

- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/*`
- `docs/product-specs/*`
- `docs/references/*`

Reason: knowledge outside the repo does not exist for future agent runs.

## 5. AGENTS.md is a map, not a manual

Repo asset:

- short root `AGENTS.md`
- deep docs in `docs/`

Reason: prevent context bloat and stale mega-instructions.

## 6. Plans are first-class artifacts

Repo asset:

- `docs/exec-plans/active/`
- `docs/exec-plans/completed/`
- `docs/exec-plans/template.md`

Reason: complex work needs versioned progress and decision logs.

## 7. Enforce architecture and taste mechanically

Repo asset:

- `tests/architecture/*`
- `scripts/agent/validate-architecture.py`
- `.github/workflows/architecture.yml`

Reason: documentation alone cannot stop drift in an agent-generated codebase.

## 8. Use strict boundaries and predictable structure

Repo asset:

- fixed packages: `platform-core`, `platform-actions`, `platform-sdk`, `product-platforms`
- `docs/architecture/package-layering.md`
- import boundary tests

Reason: agents move faster when the allowed dependency graph is explicit.

## 9. Parse data at boundaries

Repo asset:

- `docs/architecture/structured-output.md`
- config schemas and validation tests
- action definitions with input/output schemas

Reason: no guessed JSON shapes; typed boundaries are mandatory.

## 10. Throughput changes merge philosophy

Repo asset:

- small execution plans
- PR template
- quick-check/full-check commands

Reason: PRs should be small, validated, and short-lived.

## 11. Agent-generated means everything

Repo asset:

- docs, scripts, CI, tests, tooling, and starter code are all in repo

Reason: agents can modify and improve the whole harness, not just product code.

## 12. Increasing autonomy requires validation loops

Repo asset:

- `just quick-check`
- `just full-check`
- `just kernel-smoke`
- `scripts/agent/summarize-failures.sh`

Reason: Codex should validate current state, implement, re-run checks, and iterate.

## 13. Entropy and garbage collection

Repo asset:

- `docs/quality-score.md`
- `docs/tech-debt-tracker.md`
- `docs/exec-plans/active/weekly-doc-gardening.md`

Reason: agent-created patterns drift unless cleanup is continuous and mechanical.

## 14. Golden principles

Repo asset:

- `docs/core-beliefs.md`
- architecture tests that enforce selected principles

Reason: human taste should be encoded once and enforced continuously.
