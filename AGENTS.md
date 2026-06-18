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
7. `docs/product-specs/mvp-a-platform-kernel.md`
8. `docs/agent/harness-engineering-map.md`

## Current MVP

MVP-A: Platform Kernel.
MVP-B: Freelancer Validation Bundle v0.

MVP-A builds the platform execution kernel. MVP-B validates it with thin product bundles and separate Chrome Extensions.

The controlling concept source for MVP-A/MVP-B scope is mirrored in `docs/product-specs/mvp-scope-source-of-truth.md`. Keep repo-local docs and scaffold aligned with that file.

## Non-negotiable architecture boundaries

- `packages/backend/platform-core` must not import `product-platforms`.
- `packages/backend/platform-actions` must not import `product-platforms`.
- `apps/platform-api` is the composition root that wires platform + bundles.
- Extensions must not contain system prompts.
- Frontend must not choose provider/model.
- Provider calls must go through `platform-core/providers/gateway.py` and provider adapters.
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

`just` is the preferred local command interface. If `just` is unavailable or a shell integration fails,
use the shell-independent fallback command that matches the task:

- baseline backend checks: `python3 scripts/agent/quick_check.py`
- other repo commands: `python3 scripts/agent/runner.py <command>`

Windows fallback for baseline backend checks: `python scripts/agent/quick_check.py`
Secondary Windows fallback when the Python launcher is configured: `py -3 scripts/agent/quick_check.py`

## Validation commands

Fast check:

```bash
just quick-check
```

Baseline quick-check includes config validation, architecture validation, and a DB-free backend pytest subset.
It does not provision a test DB and does not include frontend checks, `tests/e2e`, or `kernel-smoke`.
The Python entrypoint self-manages `.quick-check-venv` instead of installing into a system interpreter.
It must re-exec into that environment even if the caller already has another virtualenv active.

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
python3 scripts/agent/quick_check.py
```

Windows fallback:

```powershell
python scripts/agent/quick_check.py
```

## If stuck

Do not guess. Update the execution plan with the blocker, run `scripts/agent/collect-context.sh`, and ask for the missing contract or decision.

## Agent style

Prefer boring, explicit, searchable code. Avoid clever abstractions until a second product or workflow proves the need.
