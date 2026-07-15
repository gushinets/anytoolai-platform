# AGENTS.md

You are working in the AnytoolAI monorepo.

This repo is optimized for Codex and other coding agents. Treat the repository as the source of truth. If context is not in the repo, it does not exist for future agents.

## Start here

Read these first:

1. `ARCHITECTURE.md`
2. `docs/index.md`
3. `docs/product-specs/mvp-scope-source-of-truth.md`
4. `docs/core-beliefs.md`
5. `docs/architecture/platform-boundaries.md`
6. `docs/architecture/package-layering.md`
7. `docs/architecture/llm-runtime.md`
8. `docs/product-specs/mvp-a-platform-kernel.md`
9. `docs/agent/harness-engineering-map.md`

## Current MVP

MVP-A: Platform Kernel.
MVP-B: Freelancer Validation Bundle v0.

MVP-A builds the platform execution kernel. MVP-B validates it with thin product bundles and separate Chrome Extensions.

The controlling concept source for MVP-A/MVP-B scope is mirrored in `docs/product-specs/mvp-scope-source-of-truth.md`. Keep repo-local docs and scaffold aligned with that file.

## LLM runtime decision

MVP-A uses both PydanticAI and LiteLLM:

- PydanticAI is only for structured LLM action execution and validation retries inside `StructuredLlmActionExecutor`.
- LiteLLM is used as an in-process SDK behind Provider Gateway for provider/model access.
- LiteLLM Proxy is not part of MVP-A, but remains the scale path.
- Transport retries belong to AnytoolAI ProviderGateway around LiteLLM SDK calls.
- Validation retries belong to PydanticAI.
- LiteLLM SDK hidden retries stay disabled in MVP-A; each physical ProviderGateway attempt must create a provider-call ledger row.

Deep rules live in `docs/architecture/llm-runtime.md`.

## Non-negotiable architecture boundaries

- `packages/backend/platform-core` must not import `product-platforms`.
- `packages/backend/platform-actions` must not import `product-platforms`.
- `apps/platform-api` is the composition root that wires platform + bundles.
- Extensions must not contain system prompts.
- Frontend must not choose provider/model.
- Provider calls must go through `packages/backend/platform-core/src/anytoolai_platform_core/providers/gateway.py` and provider adapters.
- `litellm` imports are allowed only in the Provider Gateway/provider adapter layer.
- `pydantic_ai` imports are allowed only in `platform-actions` structured LLM executor code.
- Direct `openai`, `anthropic`, `google.genai`, `@google/genai`, `cohere`, and `mistralai` imports outside approved provider boundaries are forbidden.
- Every scenario start must create `scenario_session_id`.
- Events must include required dimensions where applicable.
- Definitions live in YAML/Markdown; runtime state lives in PostgreSQL.
- Handoff is backend-owned and user-confirmed.
- `kernel_demo` is the only MVP-A product surface and exists only for smoke testing the kernel.
- Freelancer product meaning belongs to MVP-B config, prompts, schemas, renderers, and CE wrappers.

## Before coding

For any non-trivial work:

1. Create or update an execution plan in `docs/exec-plans/active/`.
2. Run `python scripts/agent/runner.py doctor`.
3. Read the relevant architecture docs.
4. Keep changes small and reviewable.

Feature PRs own the tests and documentation for the behavior they introduce. Do not use placeholders,
silent skips, permanent expected failures, or ignored failures as evidence that unfinished MVP-A/MVP-B
behavior works.

`python scripts/agent/runner.py <command>` is the canonical Windows/Linux command interface.
`just` recipes are optional thin aliases.

Python package management uses `uv`, not `pip`.

- Use `uv add <package>` for runtime dependencies.
- Use `uv add --dev <package>` for dev dependencies.
- Use `python scripts/agent/runner.py <command>` for repository checks.
- Do not hand-edit `uv.lock`.

Linux alias when Python 3 is exposed as `python3`: `python3 scripts/agent/runner.py <command>`

## Validation commands

Fast check:

```bash
python scripts/agent/runner.py quick-check
```

Baseline quick-check includes config validation, architecture validation, and a DB-free backend pytest subset.
It does not provision a test DB and does not include frontend checks.
The Python entrypoint self-manages `.quick-check-venv` instead of installing into a system interpreter.
It must re-exec into that environment even if the caller already has another virtualenv active.
It strips caller-provided `PYTHONPATH`, so no manual `PYTHONPATH` setup is required.
GitHub Actions runs this same command on Linux CI and Windows PowerShell, and the backend workflow is required on pull requests and pushes to `main`.

Full check:

```bash
python scripts/agent/runner.py full-check
```

Use full check or dedicated smoke commands for broader validation outside the baseline gate.
`full-check` runs the baseline, locked frontend checks, and implemented product-suite tests. Smoke
checks become required only after a feature issue supplies a real vertical slice.

Config validation:

```bash
python scripts/agent/runner.py validate-configs
```

Architecture validation:

```bash
python scripts/agent/runner.py validate-architecture
```

Documentation and generated-artifact validation:

```bash
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
```

Frontend checks:

```bash
python scripts/agent/runner.py frontend-check
```

## If stuck

Do not guess. Update the execution plan with the blocker, run `scripts/agent/collect-context.sh`, and ask for the missing contract or decision.

## Agent style

Prefer boring, explicit, searchable code. Avoid clever abstractions until a second product or workflow proves the need.
