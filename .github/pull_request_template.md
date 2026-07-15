## Summary

What changed?

## Execution plan

Link: `docs/exec-plans/active/...`

## Scope

In scope:

Out of scope:

## Architecture boundaries

- [ ] platform-core does not import product-platforms
- [ ] platform-actions does not import product-platforms
- [ ] extensions contain no prompts
- [ ] provider calls go through Provider Gateway

## Runtime guarantees

- [ ] scenario_session_id preserved where relevant
- [ ] events emitted
- [ ] artifacts saved
- [ ] user-safe errors

## Validation

- [ ] `python scripts/agent/runner.py quick-check`
- [ ] `python scripts/agent/runner.py frontend-check` when frontend code changes
- [ ] `python scripts/agent/runner.py validate-configs`
- [ ] `python scripts/agent/runner.py validate-architecture`
- [ ] real feature-owned smoke evidence when the changed vertical slice supports it

## Follow-up debt

-
