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
2. Run `just doctor`.
3. Read the relevant architecture docs.
4. Keep changes small and reviewable.

Feature PRs own the tests and documentation for the behavior they introduce. Do not use placeholders,
silent skips, permanent expected failures, or ignored failures as evidence that unfinished MVP-A/MVP-B
behavior works.

`just` is the preferred local command interface. If `just` is unavailable or a shell integration fails,
use the shell-independent fallback command that matches the task:

- canonical baseline backend checks: `python scripts/agent/quick_check.py`
- repo checks in the managed environment: `uv run python scripts/agent/runner.py <command>`

Python package management uses `uv`, not `pip`.

- Use `uv add <package>` for runtime dependencies.
- Use `uv add --dev <package>` for dev dependencies.
- Use `uv run python scripts/agent/runner.py <command>` for repo checks through the managed environment.
- Do not hand-edit `uv.lock`.

Linux alias when Python 3 is exposed as `python3`: `python3 scripts/agent/quick_check.py`
Windows PowerShell fallback when the Python launcher is configured: `py -3 scripts/agent/quick_check.py`

## Validation commands

Fast check:

```bash
just quick-check
```

Baseline quick-check includes config validation, architecture validation, and a DB-free backend pytest subset.
It does not provision a test DB and does not include frontend checks, `tests/e2e`, or `kernel-smoke`.
The Python entrypoint self-manages `.quick-check-venv` instead of installing into a system interpreter.
It must re-exec into that environment even if the caller already has another virtualenv active.
It strips caller-provided `PYTHONPATH`, so no manual `PYTHONPATH` setup is required.
GitHub Actions runs this same command on Linux CI and Windows PowerShell, and the backend workflow is required on pull requests and pushes to `main`.

Full check:

```bash
just full-check
```

Use full check or dedicated smoke commands for broader validation outside the baseline gate.
`just full-check` currently runs the same baseline and then `tests/e2e`.
Those e2e placeholders are DB-free today; when DB-backed coverage is introduced, use an explicit test-only DB contract there instead of changing quick-check.

Config validation:

```bash
just validate-configs
```

Architecture validation:

```bash
just validate-architecture
```

Kernel smoke:

```bash
just kernel-smoke
```

Fallback form:

```bash
python scripts/agent/quick_check.py
```

Linux alias:

```bash
python3 scripts/agent/quick_check.py
```

## If stuck

Do not guess. Update the execution plan with the blocker, run `scripts/agent/collect-context.sh`, and ask for the missing contract or decision.

## Agent style

Prefer boring, explicit, searchable code. Avoid clever abstractions until a second product or workflow proves the need.
