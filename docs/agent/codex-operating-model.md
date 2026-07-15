# Codex Operating Model

## Human role

Humans prioritize work, define acceptance criteria, decide product scope, and validate outcomes.

## Agent role

Agents read the repo, update an execution plan, implement small increments, run validation, summarize failures, and prepare PRs.

## Default loop

1. Read `AGENTS.md` and relevant docs.
2. Create/update an execution plan.
3. Run `python scripts/agent/runner.py doctor`.
4. Implement the smallest useful slice.
5. Run `python scripts/agent/runner.py quick-check`.
6. Run targeted validation.
7. Update docs/generated if needed.
8. Update the plan with progress and debt.

## Python environment rule

This repo uses `uv` for Python dependency management. Agents should treat `uv` as required and should not generate `pip install` commands for repo setup, CI, or lockfile maintenance.

- Use `uv add <package>` for runtime dependencies.
- Use `uv add --dev <package>` for dev dependencies.
- Use `python scripts/agent/runner.py <command>` as the canonical cross-platform command interface.
- Treat `just` recipes as optional thin aliases.
- Do not hand-edit `uv.lock`; update it only through `uv` commands.

## CI rule

GitHub workflows that need repo Python dependencies should install `uv` instead of invoking `pip` directly.
CI must call the same `python scripts/agent/runner.py <command>` interface documented for local use.

## Escalation

Escalate to humans for product scope, ambiguous contracts, security/privacy judgment, monetization rules, and architectural boundary changes.
