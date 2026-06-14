# Contributing

This repository is built for AI-assisted development with Codex. Humans steer; agents execute.

## Workflow

1. Create or update an execution plan under `docs/exec-plans/active/`.
2. Run `just doctor`.
3. Implement in small PR-sized increments.
4. Run `just quick-check` before pushing.
5. Run `just validate-configs` after changing YAML/Markdown definitions.
6. Run `just validate-architecture` after touching imports, package layout, providers, extensions, or product bundles.
7. Update generated docs when schemas, OpenAPI, actions, or events change.

`just` is the preferred local interface. If `just` is unavailable or shell integration fails, use
`python scripts/agent/runner.py <command>` with the same command names, for example
`python scripts/agent/runner.py quick-check`.

## Guardrails

- Do not add product-specific logic to `platform-core`.
- Do not store prompts in extensions.
- Do not call providers outside Provider Gateway.
- Do not invent workflow steps in frontend.
- Do not add runtime DB tables for product definitions during MVP-A; definitions are config-first.

## Review philosophy

Review contracts, boundaries, runtime events, tests, and validation output first. Style nits are less important than legibility and invariants.
