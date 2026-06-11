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

- [ ] `just quick-check`
- [ ] `just validate-configs`
- [ ] `just validate-architecture`
- [ ] `just kernel-smoke`

## Follow-up debt

-
