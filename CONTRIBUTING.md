# Contributing

This repository is built for AI-assisted development with Codex. Humans steer; agents execute.

## Workflow

1. Create or update an execution plan under `docs/exec-plans/active/`.
2. Run `python scripts/agent/runner.py doctor`.
3. Implement in small PR-sized increments.
4. Run `python scripts/agent/runner.py quick-check` before pushing.
5. Run `python scripts/agent/runner.py validate-configs` after changing YAML/Markdown definitions.
6. Run `python scripts/agent/runner.py validate-architecture` after touching imports, package layout, providers, extensions, or product bundles.
7. Update generated docs when schemas, OpenAPI, actions, or events change.

`python scripts/agent/runner.py <command>` is the canonical local interface. `just` recipes are
optional thin aliases.

For Python dependencies, use `uv`, not `pip`: `uv add <package>` for runtime dependencies,
`uv add --dev <package>` for dev dependencies, and never hand-edit `uv.lock`.

## Guardrails

- Do not add product-specific logic to `platform-core`.
- Do not store prompts in extensions.
- Do not call providers outside Provider Gateway.
- Do not invent workflow steps in frontend.
- Do not add runtime DB tables for product definitions during MVP-A; definitions are config-first.

## Review philosophy

Review contracts, boundaries, runtime events, tests, and validation output first. Style nits are less important than legibility and invariants.
