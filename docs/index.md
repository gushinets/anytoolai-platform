# AnytoolAI Repository Knowledge Map

This directory is the system of record for agents. Keep it current. If a decision is not here, future Codex runs cannot reliably use it.

## Core orientation

- `../AGENTS.md` — short map for agents.
- `../ARCHITECTURE.md` — top-level system map.
- `product-specs/mvp-scope-source-of-truth.md` — repo-local mirror of the controlling MVP-A/MVP-B concept source.
- `core-beliefs.md` — golden principles.
- `glossary.md` — common terms.

## Architecture

- `architecture/platform-boundaries.md`
- `architecture/package-layering.md`
- `architecture/action-runner.md`
- `architecture/action-model.md`
- `architecture/workflow-model.md`
- `architecture/job-lifecycle.md`
- `architecture/scenario-session-model.md`
- `architecture/event-taxonomy.md`
- `architecture/handoff-model.md`
- `architecture/config-model.md`
- `architecture/provider-gateway.md`
- `architecture/structured-output.md`
- `architecture/llm-runtime.md`
- `architecture/runtime-storage.md`
- `architecture/quota-model.md`
- `architecture/frontend-boundaries.md`

## Architecture decisions

- `adr/0001-monorepo.md`
- `adr/0002-config-first-registry.md`
- `adr/0003-short-agents-md.md`
- `adr/0004-generic-structured-llm-executor.md`
- `adr/0005-separate-product-chrome-extensions.md`
- `adr/0006-event-log-as-core.md`
- `adr/0007-llm-runtime-pydanticai-litellm-sdk.md`

## Product specs

- `product-specs/mvp-a-platform-kernel.md`
- `product-specs/mvp-b-freelancer-validation-bundle.md`
- `product-specs/mvp-scope-source-of-truth.md`
- `product-specs/kernel-demo.md`
- `product-specs/freelancer-suite-v0.md`

## Agent operations

- `agent/harness-engineering-map.md`
- `agent/codex-operating-model.md`
- `agent/prompting-guidelines.md`
- `agent/review-checklist.md`
- `agent/task-sizing.md`
- `agent/failure-recovery.md`
- `agent/repo-navigation.md`

## Executable plans

- `exec-plans/template.md`
- `exec-plans/active/`
- `exec-plans/completed/`

## Task handoffs

- `tasks/a11-job-lifecycle-and-worker-integration.md`
- `handoffs/a11-job-lifecycle-worker-review-remediation.md`

## Generated docs

- `generated/db-schema.md`
- `generated/openapi.md`
- `generated/config-registry.md`
- `generated/action-registry.md`
- `generated/event-catalog.md`

## Maintenance

- `quality-score.md`
- `tech-debt-tracker.md`
