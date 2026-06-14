# AnytoolAI Agent-First Starter Repo

This is the first-commit starter repository for AnytoolAI MVP-A and MVP-B.

The repo is intentionally agent-friendly: short `AGENTS.md`, repo-local docs, executable plans, validation scripts, architecture tests, config validation, CI templates, and generated documentation placeholders are included from day one.

## Quick start

```bash
just doctor
just quick-check
just validate-configs
just validate-architecture
```

`just` is the preferred command interface. On systems where `just` or shell integration is unavailable,
run the cross-platform Python runner directly:

```bash
python scripts/agent/runner.py doctor
python scripts/agent/runner.py quick-check
```

## MVPs

- MVP-A: Platform Kernel — execution runtime for typed atoms, workflows, scenario sessions, artifacts, events, guest quota, email capture, and handoff.
- MVP-B: Freelancer Validation Bundle v0 — eight thin Freelancer CE-first products added through configs, prompts, schemas, workflows, result renderers, handoff maps, product events, and separate Chrome Extension wrappers.

## First places to read

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/core-beliefs.md`
- `docs/agent/harness-engineering-map.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
