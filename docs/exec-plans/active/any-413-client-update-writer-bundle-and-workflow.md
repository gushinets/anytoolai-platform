# Execution Plan: ANY-413 Client Update Writer Bundle And Workflow

## Status

- State: active
- Owner: agent
- Created: 2026-09-08
- Last updated: 2026-09-08
- Review date: 2026-09-08
- Next action: verification (quick-check/full-check/validate-*) and code review; move to
  `completed/` once merged.
- Blocker: none

## Goal

Define the `client_update_writer` Freelancer Suite product bundle (Update, PrepaidRequest,
ReplyDraft modes) as a real product config directory loaded through
`FreelancerSuiteBundle.config_roots()`, using only A07 `text.compose_reply` (all modes) and A06
`text.compose_persuasive_text` (PrepaidRequest only) — no Platform Core changes, no product Python
code.

## Scope

### In scope

- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/client_update_writer/`:
  product/scenario/workflow/action-config/prompt/schema config for all three modes.
- `FreelancerSuiteBundle.config_roots()` wiring.
- Deterministic fake-provider fixtures for each action config.
- Tests: quick-check-covered config-load + schema-validation evidence in
  `apps/platform-api/tests`; deeper per-mode + no-forbidden-import coverage in
  `packages/backend/product-platforms/freelancer-suite/tests`.
- README roadmap update.

### Out of scope

`apps/web-mirror` page/renderer, Chrome Extension delivery, automated sending, custom backend
endpoints, ProposalAI (ANY-227) or any other Freelancer-suite product, Platform Core/atom-contract
changes (A07/A06 already implemented and hardened), handoff wiring (no downstream target named in
this ticket).

## Relevant docs

- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
- `docs/architecture/action-model.md`
- `docs/product-specs/add-product-recipe.md`
- `packages/backend/product-platforms/freelancer-suite/README.md`

## Contracts touched

- API: none (existing generic `/v1/products/{product}/scenarios/{scenario}/start` runtime only).
- DB: none.
- Config: new product config tree under `freelancer-suite`; `FreelancerSuiteBundle.config_roots()`.
- Events: `client.next_action_clicked` via the generic `copy_result` next-action (no new event
  types introduced).
- Frontend: `frontends.yaml` registers one `web_mirror` entry (metadata only, required by the
  scenario runtime to accept a scenario start at all — see design decision 5) but no CE/web page
  code ships; no CE/web delivery is in this ticket's scope.

## Design decisions

1. **Three separate scenario/workflow pairs**, not one workflow parameterized by a `mode` input
   field — matches every existing precedent (`kernel_demo`'s per-atom scenarios) and keeps each
   mode's input schema strict/non-permissive per mode instead of a single loosely-typed
   `mode`-branching schema.
2. **A06 (`text.compose_persuasive_text`) is used only by PrepaidRequest** — asking for payment is
   the one mode that plausibly needs persuasive framing; Update and ReplyDraft are single-step
   `text.compose_reply` workflows. PrepaidRequest mirrors `kernel_demo.composite_shape_and_write_v1`:
   `compose_persuasive_text` output `.text` feeds `compose_reply`'s `situation`.
3. **Workflow-level input schemas are product-owned and decoupled from the atom's own input
   schema** — mirrors `kernel_demo.single_action_compose_reply_v1`'s pattern
   (`generic_text_input_v1`, not `compose_reply_input_v1`, as the workflow input). Each mode's
   input schema exposes only the fields a caller actually supplies (freeform notes/message +
   `tone` + optional `constraints`); mode-specific `intent`/`objective` framing is a workflow
   `literal:` value, and mode-specific voice lives in the product-owned prompt text, not in the
   input schema.
4. **Output schema is `kernel.schemas.compose_reply_output_v1` for all three modes**, reused
   directly (not redefined) — the atom's own `{text, call_to_action}` shape *is* the copy-ready
   client message. The renderer contract this ticket's scope requires is pinned as a concrete
   product-owned artifact, `renderer_contract.yaml` (mirroring ProposalAI's own file and
   regression test): `text` is the canonical copy-ready field; when `call_to_action` is present it
   is appended after `text` separated by one blank line, otherwise the payload is `text` alone.
   `apps/web-mirror` (ANY-412/414, out of scope here) is the renderer *implementation* this
   contract is built against, not part of this ticket.
5. **`frontends.yaml` declares one `web_mirror` (type: web) entry, not an empty list.**
   `ConfigLoader._load_frontends` requires the file to exist, but the harder constraint is
   runtime, not load-time: `ScenarioRuntimeService.start_session`'s `_require_enabled_frontend`
   rejects starting *any* scenario unless the product has at least one enabled frontend_id — an
   empty list would make this product permanently unstartable through the real runtime, which
   would contradict the ticket's own "bundle loads ... without Platform Core changes" and
   deterministic-test acceptance criteria. Registering `web_mirror` here is metadata only (frontend
   id + type), not a page implementation — `apps/web-mirror` still ships no product page for this
   ticket, matching the non-goals.
6. **No `quotas.yaml`/`handoffs.yaml`** — the ticket names no quota policy or handoff target, and
   both are optional to the loader when `product.yaml` sets no `quota_policy_ref`.
7. **No `analytics.yaml` file** — it is optional to the loader (`_load_analytics` returns `{}`
   when the file is absent) and no product-specific event IDs are named beyond the generic
   `client.next_action_clicked` recorded via `allowed_next_actions: [copy_result]`.

## Implementation steps

- [x] Exec plan (this file).
- [x] Product config tree (product.yaml, scenarios.yaml, workflows.yaml, action_configs.yaml,
      prompts.yaml + prompts/*.md, schemas.yaml + schemas/*.json, frontends.yaml).
- [x] `FreelancerSuiteBundle.config_roots()` wiring + README roadmap update.
- [x] Fake-provider fixtures per action config.
- [x] Tests: `apps/platform-api/tests` (quick-check) + `freelancer-suite/tests` (full-check).
- [x] Verification: `validate-configs`, `validate-architecture`, `quick-check`, `full-check`.

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check` (1226 passed)
- [x] `python scripts/agent/runner.py full-check` (backend + frontend lint/typecheck/test/build)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-08 | 3 modes = 3 scenario/workflow pairs, not 1 parameterized workflow | Matches kernel_demo precedent; keeps per-mode schemas strict |
| 2026-09-08 | A06 only in PrepaidRequest | Only mode with an inherently persuasive ask (payment) |
| 2026-09-08 | Reuse `kernel.schemas.compose_reply_output_v1` as output for all 3 modes | Already the exact copy-ready-message shape; avoids a redundant product schema |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-08 | Exec plan written; config/loader contract fully re-derived from `packages/backend/platform-core/src/anytoolai_platform_core/config/loader.py` | Write product config tree |
| 2026-09-08 | Product config tree, bundle wiring, fixtures, and both test suites written; `quick-check` (1226 passed) and `full-check` (backend + frontend) green | Code review |
| 2026-09-08 | Code review round 1: fixed the real bug (prepaid_request's persuasive-text step dropped `constraints.language/max_length/output_format`), added real-worker happy-path coverage for all 3 modes (was update-only), fixed 4 stale "`config_roots()` returns `[]`" docstrings/comments, fixed a substring-matching gap in the no-forbidden-import test. 3 findings accepted as-is: the `constraints` JSON Schema block duplicated across the 3 mode-input schemas (no `$ref`/include precedent in this repo), `CLAUDE.md` vs `AGENTS.md` drift (tracked separately under ANY-341), and a theoretical untyped-`default=dict` edge case in a test helper (not reproduced). `quick-check` re-green at 1228 passed. | Await round 2 or merge |
| 2026-09-08 | Code review round 2: fixed a real critical bug — `prepaid_request_v1`'s billing amount/due date never reached the client message at all (prompt design gap: step 1 was told not to state them, step 2 never got a channel to add them back). Fixed at the **prompt level** by having the persuasive-text step state them (it's the only step with access to `billing_context`) and the reply step preserve them verbatim — this is a live-provider-path fix; the deterministic e2e test still runs against fixed fake-provider fixtures per action_config_id, so it cannot itself prove a real model follows the new prompt wording (round 3 caught that the round-2 fixture text hadn't been updated to match — fixed in round 3). Also: added `client_update_writer` to the endpoint-forbidden-terms architecture test, tightened a membership-check to an exact per-step assertion in the quick-check test, made the no-forbidden-import test's token matching word-boundary-safe, fixed a wrong-class doc reference, replaced a hand-rolled schema normalizer with platform-core's existing `normalize_schema_mapping`, and removed a literal-id duplication between two test dicts. `quick-check` re-green at 1228 passed. | Await round 3 or merge |
| 2026-09-08 | Code review round 3 (wide scope: whole main→working-tree diff, touched both ANY-32 and ANY-413): fixed a real cross-composition-root bug unrelated to ANY-413's own diff but caught while auditing bundle composition — `apps/platform-worker/composition.py` and `scripts/agent/validate_configs.py` never passed `reserved=RESERVED_BUNDLE_IDS` to `check_ids_are_unique()`, unlike `bootstrap.py`, so a bundle_id colliding with a reserved kernel label would fail API startup but pass worker startup and the required `validate-configs` CI gate silently. Fixed both plus added a parity test closing that coverage gap. Also fixed: the round-2 persuasive-text fixture didn't actually match its own updated prompt (still lacked the amount/due date it now requires stating), this exec-plan's self-contradictory "Frontend: none" line, a missing `re.IGNORECASE` in the forbidden-token regex, and a dead `output_mapping` entry in `workflows.yaml`. Left ~11 debt/efficiency findings out of scope as pre-existing ANY-32/tooling issues unrelated to this ticket's own diff (e.g. `DEFAULT_PRODUCT_BUNDLES`/`RESERVED_BUNDLE_IDS` literal duplication across the three composition roots, architecture-validator AST-parse duplication, `quick_check.py`/`runner.py` fingerprint-list duplication). `quick-check` re-green at 1229 passed, `full-check` green. | Await round 4 or merge |

## Open questions

None blocking. All pre-implementation design risks (mode→workflow shape, which mode needs A06,
the renderer contract, frontend registration, quota/handoff config) resolved into the concrete
choices recorded under "Design decisions" above.

## Follow-up debt

- No handoff target is wired for any mode; a future ticket may add `create_handoff` once a
  downstream product (e.g. Send-Ready) exists.
