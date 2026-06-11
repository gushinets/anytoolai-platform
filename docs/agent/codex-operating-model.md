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

## Escalation

Escalate to humans for product scope, ambiguous contracts, security/privacy judgment, monetization rules, and architectural boundary changes.
