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
use the shell-independent fallback: `python scripts/agent/runner.py <command>`.

## Validation commands

Fast check:

```bash
just quick-check
```

Full check:

```bash
just full-check
```

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
python scripts/agent/runner.py quick-check
```

## If stuck

Do not guess. Update the execution plan with the blocker, run `scripts/agent/collect-context.sh`, and ask for the missing contract or decision.

## Agent style

Prefer boring, explicit, searchable code. Avoid clever abstractions until a second product or workflow proves the need.
