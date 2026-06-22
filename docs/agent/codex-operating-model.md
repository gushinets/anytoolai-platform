# Codex Operating Model

## Human role

Humans prioritize work, define acceptance criteria, decide product scope, and validate outcomes.

## Agent role

Agents read the repo, update an execution plan, implement small increments, run validation, summarize failures, and prepare PRs.

## Default loop

1. Read `AGENTS.md` and relevant docs.
2. Create/update an execution plan.
3. Run `just doctor`.
4. Implement the smallest useful slice.
5. Run `just quick-check`.
6. Run targeted validation.
7. Update docs/generated if needed.
8. Update the plan with progress and debt.

## Python environment rule

This repo uses `uv` for Python dependency management. Agents should treat `uv` as required and should not generate `pip install` commands for repo setup, CI, or lockfile maintenance.

- Use `uv add <package>` for runtime dependencies.
- Use `uv add --dev <package>` for dev dependencies.
- Use `uv run python scripts/agent/runner.py <command>` for repo-managed Python commands when working outside `just`.
- Keep `python3 scripts/agent/quick_check.py` as the narrow shell-independent baseline fallback when `just` integration is unavailable.
- Do not hand-edit `uv.lock`; update it only through `uv` commands.

## CI rule

GitHub workflows that need repo Python dependencies should install `uv`, sync from `uv.lock`, and run checks through `uv run` instead of invoking `pip`.

## Escalation

Escalate to humans for product scope, ambiguous contracts, security/privacy judgment, monetization rules, and architectural boundary changes.
