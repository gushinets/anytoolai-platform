# Execution Plan: ANY-248 Brief Decoder Web Runtime E2E And QA

## Status

- State: active
- Owner: agent
- Created: 2026-09-23
- Last updated: 2026-09-23
- Review date: 2026-09-30
- Next action: run full-check, review, then rebase onto main once ANY-232 (PR #141) merges.
- Blocker: none

## Goal

Prove the Brief Decoder vertical (A01 + A04 -> A05, composed through A10) through the shared
multi-product web host, reusing the ANY-453 shared runtime. Page, renderer and browser proof only.

## Scope

### In scope

- `apps/web-mirror/src/products/briefDecoder/`: product definition, four-part renderer, pure
  `briefDecoderResult.ts`, messages for all 7 locales; registry entry.
- Shared runtime: optional `ProductDefinition.emitsResultViewed` gating `web.result_viewed`.
- Vitest: `BriefDecoderProduct.test.tsx`, shared hook tests in `ProductRunPage.test.tsx`.
- `tests/e2e/brief-decoder-smoke` Playwright package, `brief-decoder-smoke` runner command and a
  path-filtered, non-required workflow.
- Docs: event-taxonomy, frontend-boundaries, add-product-recipe.

### Out of scope

Brief Decoder -> Acceptance Builder (ANY-26), Chrome Extension (ANY-240), any Platform Core, atom,
runner-semantics, Provider Gateway, handoff-runtime or mapping-DSL change (including a new
client-event property), backend bundle changes, selecting weak/no-issues fixtures from a real
browser run, a shared e2e helper package.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/event-taxonomy.md`
- `docs/product-specs/add-product-recipe.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none.
- DB: none (smoke reads `platform.jobs`, `action_runs`, `provider_calls`, `event_log`).
- Config: none; comments in `frontends.yaml` / `renderer_contract.yaml` updated.
- Events: `web.result_viewed` for Brief Decoder means a non-empty question list was rendered.
- Frontend: `emitsResultViewed` added to `ProductDefinition`.

## Design decisions

1. **Activation hook.** The spec activates Brief Decoder on a non-empty question list, but the shared
   runtime emitted `web.result_viewed` for every completed result and the client-event property
   allowlist cannot carry a count (a Platform Core change, forbidden here). An optional
   `emitsResultViewed(result)` (default true) gates only the event. Rejected: a `mode` vocabulary in
   a new `analytics.yaml` (misuses `mode`, adds backend config). Consequence: zero-question runs are
   absent from the `web.result_viewed` funnel; the backend still records completion.
2. **Fixtures are the single source of truth.** Vitest and the smoke compose results from the
   checked-in fake-provider fixtures exactly as the backend bundle test does.
3. **Real-stack limit.** A real HTTP run only serves the happy fixtures. Weak-input and
   zero-question browser tests run a real start and replace only the `GET /v1/results/*` body with
   the fixtures; the worker-to-artifact half is proven by backend pytest.
4. **Weak input** produces a full, activating result (4 questions). The documented safe outcomes are
   the zero-question result (explicit empty states, no readiness claim) and a failed session.
5. **Extract is lenient.** `extractBriefDecoderResult` checks shapes and closed sets only, not the
   4-section tuple or `maxItems: 5`, so a review change to the ANY-232 schema needs no edit here.
6. **Smoke scope.** Retry, guest-id persistence and language switching are shared-runtime behavior
   already proven elsewhere and are not repeated. Helpers are copied a third time per precedent;
   a shared e2e support package is recorded debt.

## Implementation steps

- [x] Shared hook + tests
- [x] Product definition, renderer, messages, registry, Vitest
- [x] Playwright smoke package, runner command, workflow (6 tests pass against dev-up)
- [x] Docs
- [ ] full-check, validate-docs, validate-architecture
- [ ] Rebase onto main after ANY-232 merges

## Validation

```
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py dev-up
python scripts/agent/runner.py brief-decoder-smoke
python scripts/agent/runner.py dev-down
```

## Risks

- Stacked on unmerged ANY-232; output-schema review changes force a rebase.
- Severity/priority/category translations need native-speaker review.
- The smoke's zero-question `result_viewed == 0` check uses a fixed 1.5 s grace period.
- Each smoke run makes 4 fake provider calls; the quota test does 3 real runs.
