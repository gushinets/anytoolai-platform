# Execution Plan: B11. Product Events And Evaluation Fixtures (ANY-17)

## Status

- State: active
- Owner: agent
- Linear: [ANY-17](https://linear.app/paveldik/issue/ANY-17/b11-product-events-and-evaluation-fixtures)
- Created: 2026-09-09
- Last updated: 2026-09-09
- Review date: 2026-09-09
- Next action: run full validation, then move this plan to `docs/exec-plans/completed/`.
- Blocker: none

## Goal

Ship the real `POST /v1/client-events` ingestion contract, the real `trackClientEvent()` ce-kit
helper, and the `web.*` v1 event allowlist so ProposalAI (and every later web product) can emit
truthful, privacy-safe client analytics before its own product bundle exists. Prove that the
existing `client.next_action_clicked(copy_result)` mechanism already satisfies the ProposalAI
copy-activation contract.

## Scope

### In scope

- `configs/kernel/platform_events.yaml`: add a `web` group with the 8 v1 web events.
- `docs/architecture/event-taxonomy.md` + generated `docs/generated/event-catalog.md`: document the
  new group via the existing generator (no new generator).
- `POST /v1/client-events`: allowlisted event type, idempotent client-supplied `event_id`,
  server-derived `tenant_id`/`region`, product/frontend validation, optional guest/scenario-session
  correlation, scalar property allowlist (`mode`, `field_count`, `gap_category`), required
  `web_session_id`.
- Extend `EventEmitter.emit()` with an optional client-supplied `event_id` (idempotent replay path
  already exists in `EventLogRepository`; this reuses it instead of adding a parallel write path).
- Real `trackClientEvent()` in `ce-kit`, plus a `web_session_id` local helper with the 30-minute
  inactivity rotation rule. Update `ce-kit`'s generated OpenAPI client and drift assertions.
- Tests: API allowlist/privacy/idempotency/correlation, client-helper success + non-blocking
  failure, taxonomy/catalog checks, and a scenario-runtime test proving exactly one
  `client.next_action_clicked(copy_result)` per `scenario_session_id`.
- Update `packages/frontend/ce-kit/README.md` to drop `trackClientEvent` from the "not yet exported"
  list.

### Out of scope (per the approved design spec and ANY-410's completed alignment)

- ProposalAI itself (config, prompts, schema, page) — owned by ANY-227 per
  `packages/backend/product-platforms/freelancer-suite/README.md`.
- A machine-readable metric/trust-class registry. The design spec is explicit: "V1 does not add a
  metric registry, confidence score, database column, or analytics schema." The metric contract
  (`definition`/`producer`/`trust_class`/`blind_spots`) already exists as the approved Markdown table
  in `docs/superpowers/specs/2026-09-03-web-first-product-framework-design.md`; ANY-17's "generated
  catalog coverage" step is about the existing *event* catalog generator, not a new metric one.
- `onboarding.started`/`onboarding.completed` — listed in the design spec's full taxonomy but not in
  this ticket's "V1 web event allowlist" of 8 events; left for whichever ticket owns onboarding.
- A `client.result_copied` producer or its future dedup migration — stays reserved and unused.
- Any database migration (`event_log.properties` already holds `web_session_id`; no schema change).
- Product-level `analytics.yaml` consumption (`config/loader.py`'s `_load_analytics` stub) — no
  product needs it yet.

## Relevant docs

- `docs/architecture/event-taxonomy.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/frontend-boundaries.md`
- `docs/superpowers/specs/2026-09-03-web-first-product-framework-design.md`
- `docs/exec-plans/completed/web-first-product-plan-alignment.md`
- `packages/frontend/ce-kit/README.md`

## Contracts touched

- API: new `POST /v1/client-events` (`apps/platform-api`).
- DB: none (reuses `event_log`, client-supplied `event_id` as primary key via the existing
  idempotent-insert path).
- Config: `configs/kernel/platform_events.yaml` gains a `web` group.
- Events: adds the 8 `web.*` event types. No existing event type or dimension changes.
- Frontend: `ce-kit` gains `trackClientEvent()` and a `web_session_id` helper; generated
  `platformApi.ts` regenerated.

## Implementation steps

- [x] Step 1: Execution plan (this file).
- [x] Step 2: Add the `web` group (8 events) to `configs/kernel/platform_events.yaml`; update
  `docs/architecture/event-taxonomy.md`'s group listing and runtime-ownership section; add taxonomy
  tests for the new group and regenerate `docs/generated/event-catalog.md`.
- [x] Step 3: Extend `EventEmitter.emit()` with an optional client-supplied `event_id` (validated
  non-empty, bounded length) that routes through the existing `allow_existing_event_id=True`
  idempotent-insert path. Unit tests in platform-core.
- [x] Step 4: Implement the client-events domain module (allowlist check against the new `web`
  group, product/frontend validation, optional guest/scenario-session correlation, scalar property
  allowlist, `web_session_id` requirement) plus its `PlatformError` subclasses.
- [x] Step 5: Add `ClientEventRequest`/`ClientEventResponse` schemas and the
  `POST /v1/client-events` router wired into `main.py`, following the `identity_quota.py` /
  `scenario_runtime.py` router pattern.
- [x] Step 6: Backend tests: allowlist rejection, unknown event name, invalid product/frontend
  combination, property allowlist rejection (unknown key, non-scalar value), missing/oversized
  `web_session_id`, idempotent duplicate `event_id` delivery, guest/scenario-session correlation
  (valid + not-found), server-derived `tenant_id`/`region` regardless of client input.
- [x] Step 7: Prove the ProposalAI activation contract is already satisfied: add/confirm a
  scenario-runtime test that exactly one `client.next_action_clicked` with
  `next_action_id=copy_result` is recorded per `scenario_session_id` after a next-action call.
- [x] Step 8: `ce-kit`: regenerate `platformApi.ts` from the new endpoint's OpenAPI schema; add
  `trackClientEvent()` (reusing `generateIdempotencyKey()` for `event_id`) and a
  `getOrCreateWebSessionId()` helper (30-minute inactivity rotation) with drift assertions; export
  both from `index.ts`; update `README.md`.
- [x] Step 9: Frontend tests: `trackClientEvent` success + non-blocking failure, web-session mint /
  reuse / rotate-after-30-minutes.
- [x] Step 10: Run `quick-check`, `frontend-check`, `validate-docs`, `generate-docs --check`,
  `validate-configs`, `validate-architecture`; fix regressions.
- [x] Step 11: Update this plan's decision/progress logs with evidence and move it to
  `docs/exec-plans/completed/` once merged-ready.

## Validation

- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py frontend-check`
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-09 | No new metric registry; keep the metric contract as the existing Markdown table. | The approved design spec explicitly rules this out for v1; ANY-17's "generated catalog" step extends the existing event catalog, not a new one. |
| 2026-09-09 | Extend `EventEmitter.emit()` with an optional `event_id` rather than a parallel write path. | Reuses the idempotent-insert path `EventLogRepository` already has for replay events instead of duplicating sanitization/validation logic. |
| 2026-09-09 | Property allowlist limited to `mode`, `field_count`, `gap_category`. | These are the only examples the design spec names; more keys are added only when a product needs them. |
| 2026-09-09 | Skip `onboarding.*` events. | Not in ANY-17's "V1 web event allowlist" of 8 events, unlike the design spec's full taxonomy. |
| 2026-09-09 | Skip ProposalAI product code and any `client.result_copied` producer/dedup. | Explicitly out of scope per ANY-227 and the design spec's reserved-event rule. |
| 2026-09-09 | No new "ProposalAI activation" test added. | `test_record_next_action_emits_event_and_validates_checkpoint` (platform-core) and its API-level counterpart already prove exactly one `client.next_action_clicked(next_action_id=copy_result)` per call, generically (kernel_demo stands in for any product using the same mechanism, including ProposalAI once it exists). |
| 2026-09-09 | Renamed `getOrCreateWebSessionId`'s parameter to `backingStorage`, not `storage`. | WXT's global auto-import does a regex scan for a bare `storage` identifier in any ce-kit source file bundled into the Chrome-extension build and rewrites it to `import { storage } from "wxt/utils/storage"`, breaking the build (`extensions/kernel-demo-ce build` failed with an unresolved import) -- same gotcha already documented on `createLocalStorageAdapter()`. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-09 | Surveyed existing event/scenario/ce-kit infrastructure, read the approved design spec and ANY-410's completed alignment plan, and wrote this execution plan. | Add the `web` taxonomy group and extend `EventEmitter`. |
| 2026-09-09 | Implemented the `web` taxonomy group, `EventEmitter.emit(event_id=...)`, `ClientEventService`, `POST /v1/client-events`, and their backend tests (unit + API, run against a real throwaway PostgreSQL container: `test_event_log.py` 24/24, `test_client_events_api.py` 12/12, full `postgresql-check` suite green). | Implement the `ce-kit` client helper. |
| 2026-09-09 | Implemented `trackClientEvent()` and `getOrCreateWebSessionId()` in `ce-kit`, regenerated `platformApi.ts`, updated `index.ts`/`README.md`, and added their tests (14 new, 303/303 ce-kit tests green). Found and fixed a WXT bundler break (bare `storage` identifier) during `frontend-check`. | Run full validation and hand off for review. |
| 2026-09-09 | `quick-check`, `frontend-check` (lint/typecheck/test/build across all 7 frontend workspaces including the Chrome extension), `validate-docs`, `generate-docs --check`, `validate-configs`, and `validate-architecture` all pass. Changes are uncommitted, pending user review/commit approval. | User review; commit when approved. |
| 2026-09-09 | Verified the 12 findings from a code review pass logged above by direct code reading. Fixed 7 real issues: (1) client-supplied `event_id` colliding with different content now raises `client_event_id_conflict` (409) instead of silently returning stale data; (2) a valid `scenario_session_id` paired with a valid-but-unrelated `guest_id` now 404s instead of correlating to the wrong owner; (3) `properties` are now validated per-key expected type (`field_count` must be `int`, not any scalar, and a `bool` no longer passes as `field_count`); (4) `getOrCreateWebSessionId()` now single-flights concurrent calls per `(storage, storageKey)` instead of racing to two different ids; (5) a backward system-clock jump now rotates the session instead of reading as trivially-still-active forever; (6) `ClientEventRequest.event_type` is now the generated `WebClientEventType` `StrEnum`, not `str`, per `docs/agent/coding-conventions.md`; (7) `ce-kit`'s `WebClientEventType` is now derived from the generated OpenAPI schema instead of being a 4th independent hand-copied list. Left 3 as-is: (8) the CLAUDE.md/AGENTS.md "five vs six products" drift is a pre-existing untracked file unrelated to this ticket; (9)/(10) the two small validation duplications match this codebase's established per-router/defense-in-depth convention (see `errors.py`'s own comment on the same tradeoff). Added regression tests for all 7 fixes; full `postgresql-check` and `frontend-check` stay green (41/41 new+updated API tests, 306/306 ce-kit tests). | Committed as `bfdeae5`. |
| 2026-09-10 | Verified the 11 findings from a second code review pass (findings caused by round 1's own fixes). Fixed 3 critical + 2 significant + 1 minor issues: (1) the round-1 conflict check compared post-sanitization stored properties against pre-sanitization input, so a `mode`/`gap_category` value over 1024 chars falsely 409'd on its own first, successful write -- now compares against `sanitize_event_properties(event_properties)`; (2) the round-1 owner check only fired when the request supplied `guest_id`, so omitting it entirely bypassed ownership verification for a guest-owned session -- now checks the session's own `guest_id`, unconditionally; (3) `EventEmitter`'s `EventValidationError` (a `ValueError`, not `PlatformError`) wasn't caught by the router's `except PlatformError`, so a taxonomy drift would 500 instead of 422 -- `ClientEventService.record()` now catches it and re-raises as `ClientEventTypeNotAllowedError`; (4) `event_id` was validated with `.strip()` but stored/looked-up unstripped, so `"abc"` and `" abc "` didn't dedupe -- `EventEmitter.emit()` now normalizes before use; (5) `getOrCreateWebSessionId()`'s single-flight WeakMap guard only coalesces calls sharing the same storage instance -- documented as a caller contract (matches `PlatformApiClient`'s own single-flight scoping) rather than built further; (6) the bool-exclusion in `_validate_properties` ran unconditionally, which would wrongly reject a hypothetical future bool-typed property -- scoped to int-typed keys only. Also updated `docs/tech-debt-tracker.md` TD-004, which still listed client-event ingestion as a deferred slice. Left as-is: the manual 7-field conflict comparison (a hash-based redesign like scenario sessions' would need a persisted-hash column, i.e. a migration, for no added correctness now that #1 is fixed), the `WebClientEventType` duplication concern (already resolved in round 1 -- verified still true), the `inFlightCalls`/`inFlightGuestIdentity` conceptual-duplication observation (no shared abstraction actually exists to reuse across a class-bound guard and a bare-function one), and `storage.set()` running every call (confirmed intentional, repeat of round 1's finding). Added regression tests for all 6 fixes; `postgresql-check` (44/44 client-event tests) and `frontend-check` stay green. | None -- ready for user review/commit. |
| 2026-09-10 | Verified the 10 findings from a third code review pass (findings caused by round 2's own fixes) plus one out-of-band note. Fixed 5 real issues + 1 doc convention: (1) the round-2 owner check (`session.guest_id is not None and session.guest_id != guest_id`) still let an anonymous session (`guest_id=None`) be silently claimed by any real `guest_id` -- simplified to a plain `session.guest_id != guest_id` equality, which closes every asymmetric case (omitted guest_id, anonymous session, mismatched guest) at once; (2) a client-controlled property key was echoed unsanitized and unbounded into the 422 error message -- `ClientEventPropertyInvalidError` now truncates it to 64 chars, and property string values are now capped at 128 chars (which also makes round 2's "sanitizer truncation causes a false conflict" failure mode structurally unreachable for properties, not just handled); (3) `ClientEventResponse.event_type` was still plain `str` (only the request field was fixed in round 1) -- now `WebClientEventType` too, with `ce-kit`'s `parseClientEventResponse` narrowing to the same type; (4) `event_id` length was validated before trimming, so whitespace padding could make an otherwise-valid id read as oversized -- reordered to trim-then-validate in both `ClientEventService.record()` and `EventEmitter.emit()`; (5) `web_session_id` was trimmed for validation but stored untrimmed -- now the trimmed value is what's used throughout. Also replaced two literal `` /code-review `` -style backtick strings in this plan's own progress-log prose (written by me, not a reintroduction) with plain "code review", per the standing repo convention. Left as-is: tenant/region not part of the conflict comparison or the repository lookup scope (MVP-A is single-tenant platform-wide, not specific to this endpoint); the manual 7-field comparison vs. a hash-based redesign (still needs a migration); a shared `backingStorage`-naming eslint rule (real but disproportionate infra work for a 3-occurrence convention, better as its own ticket); `sanitize_event_properties()` running twice per request (negligible on a ≤4-key dict). `docs/tech-debt-tracker.md` TD-004's "shared-client support" phrase was intentionally folded into the "client-event ingestion (ANY-17: ..., trackClientEvent())" credit, not silently dropped -- already explicit as written. A repo-wide grep found the same `` /code-review `` -string issue in three unrelated, already-merged tickets' exec plans; left untouched as out of scope for this ticket (flagged to the user instead of a drive-by edit). Added regression tests for all 5 code fixes; `postgresql-check` (51/51 client-event tests) and `frontend-check` stay green. | None -- ready for user review/commit. |
| 2026-09-10 | Verified the 9 findings from a fourth code review pass (findings caused by round 3's own fixes, plus two pre-existing gaps a live check of SQLAlchemy's exception hierarchy confirmed). Fixed 5 real issues: (1) `user_id` was the one free-text field with no length check -- `event_log.user_id` is `String(128)`, and an oversized value reached the INSERT unchecked, raising `sa.exc.DataError` (confirmed not a subclass of the `sa.exc.IntegrityError` `EventLogRepository.create()` catches), surfacing as a raw 500; added the same trim-then-validate treatment as `event_id`/`web_session_id`; (2) `field_count` had no upper (or lower) bound -- capped to `[0, 10_000]`, a sane ceiling for a form-field count; (3) `ce-kit`'s `toWireProperties()` didn't guard `fieldCount` against `NaN`/`Infinity`, which `JSON.stringify` silently turns into `null` on the wire, producing a confusing generic rejection instead of a clear client-side problem -- now dropped (like an unset property) rather than sent; (4) the router's `_status_code_for_platform_error` returned raw ints instead of `http.HTTPStatus`, per `docs/agent/coding-conventions.md`'s explicit rule for new files (this router is one); (5) the 7-field conflict comparison duplicated identifiers `context` already carries -- now reads them off `context` via `getattr` over a named `_CONTEXT_CORRELATION_FIELDS` tuple, and the bool-exclusion branch in `_validate_properties` folded into a single `_is_allowed_property_value()` helper (a genuine simplification, not just a rename). Left as-is: tenant/region still not compared (repeat of round 3's accepted single-tenant scope decision); the manual correlation comparison vs. a hash-based redesign (still needs a migration); `docs/tech-debt-tracker.md` TD-004 (repeat, already explicit); `sanitize_event_properties()` running twice (repeat, negligible); the nested `WeakMap<AsyncStorage, Map<key, Promise>>` in `webSession.ts` -- disagreed with "collapse to a single-level WeakMap": `storageKey` is a real, already-shipped public parameter mirroring the established `refreshGuestIdentity`/`DEFAULT_GUEST_STORAGE_KEY` pattern, and collapsing the map would silently miscoalesce two different storageKeys sharing one storage instance, reintroducing a real bug rather than removing dead code -- kept, with reasoning recorded here rather than in the code. Added regression tests for all 5 fixes; `postgresql-check` (56/56 client-event tests) and `frontend-check` stay green. | None -- ready for user review/commit. |
| 2026-09-10 | Verified the 11 findings from a fifth code review pass (a third continuation of the same owner-check chain, plus new findings). Fixed 6 real issues, refactored one duplication flagged as its own finding: (1) the owner check compared `session.guest_id` but never `session.user_id` -- a session with `guest_id=None, user_id="real_user"` could be claimed by simply omitting `guest_id` (`None == None`) and supplying any unchecked `user_id`; now compares both; (2) `guest_id`/`scenario_session_id` weren't trimmed before lookup, unlike every other free-text field, so a real guest's id with incidental whitespace 404'd, and (worse) would have permanently broken the round-4 owner-check equality once whitespace was involved; (3) empty `guest_id`/`scenario_session_id` were looked up as if provided (falling through to a 404) rather than rejected with a dedicated 422, inconsistent with `user_id`'s own `ClientEventUserIdInvalidError` -- added matching `ClientEventGuestIdInvalidError`/`ClientEventScenarioSessionIdInvalidError`; (2)+(3) together closed by extracting one `_trim_or_raise()` helper and using it for all five free-text fields (`event_id`, `web_session_id`, `user_id`, `guest_id`, `scenario_session_id`), which also directly addressed the review's own "same 3-line pattern copied 3 times" finding; (4) `ce-kit`'s `fieldCount` guard used `Number.isFinite`, which admits non-integers like `2.5` -- the backend's `field_count` is a Python `int`, so a finite non-integer still failed `isinstance` and rejected the whole event; switched to `Number.isInteger` (which also subsumes the NaN/Infinity case); (5) `ClientEventService.record()`'s `event_type` parameter was typed `str`, widening back from the `WebClientEventType` the router already holds -- now typed to match, free since the enum is already defined in the same file. Left as-is: `EventLogRepository.create(allow_existing_id=True)` trusting any existing row without a content check is accurately described as "the client-event path's safety rests entirely on `ClientEventService`'s own bolt-on comparison" -- that's the deliberate design (the repository/emitter stay generic; a client-supplied id's content-conflict semantics are this endpoint's own concern), not a gap; the `except EventValidationError` catch-all mapping to one error code (repeat of round 4's accepted defensive-fallback reasoning); the frontend-enabled-for-product duplicate check vs. `ScenarioSessionService` (repeat of round 1's accepted convention); `emitter.py`'s own separate strip-and-validate copy for `event_id` (a different module/abstraction level -- a generic shared primitive shouldn't import a `client_events`-specific helper); cross-tab/cross-execution-context coalescing for `getOrCreateWebSessionId()` (the existing single-flight guard is explicitly scoped to one JS execution context, matching `PlatformApiClient`'s own precedent -- cross-tab coordination would need a different primitive, e.g. a Web Lock, disproportionate for a device-local, approximate-by-design session concept); property validation running after the two DB round-trips for `guest_id`/`scenario_session_id` (negligible reordering gain). Added regression tests for all 6 fixes (2 new scenario-session fixtures: anonymous-but-user-owned, and the trim/empty cases); `postgresql-check` (62/62 client-event tests) and `frontend-check` stay green. | None -- ready for user review/commit. |
| 2026-09-10 | Addressed a human PR review (4 blocking findings, PR #113) verified against current code. Fixed all 4: (1) `event_id`/`web_session_id` were only trim+length checked, so arbitrary 128-char content could be stored under `web_session_id` (breaking the content-free analytics guarantee) and a client `event_id` could occupy the backend's own reserved `event_replay_...` namespace -- both are now required to be canonical-lowercase UUID strings (the exact shape ce-kit's `generateIdempotencyKey()`/`getOrCreateWebSessionId()` already produce), which structurally rules out both; (2) identity/correlation was only validated against the request's own copies, not derived from server-owned state -- `record()` now treats a resolved `scenario_session_id`'s own `guest_id`/`user_id`/`scenario_chain_id` as authoritative once found (an explicit, contradicting client-supplied `guest_id`/`user_id` is still rejected, but omitting one no longer loses correct attribution -- this also supersedes round 2's now-obsolete assumption that omitting `guest_id` must always be rejected outright), and a standalone `user_id` with no `scenario_session_id` to verify it against is rejected outright (`client_event_user_id_requires_scenario_session`), since MVP-A has no authenticated-user lookup at all to check it against; (3) `mode`/`gap_category` accepted arbitrary text up to the length cap, so prompt/result fragments could be smuggled in under an allowlisted key -- now validated against a lowercase slug shape (`^[a-z][a-z0-9_]{0,63}$`), a content-shape guard that doesn't require platform-core to know any product's actual category vocabulary (which would violate the platform-core/product-platforms boundary -- validate-architecture's `ATAI002` check caught one draft comment that named a product, confirming the boundary is real and enforced); (4) `ce-kit`'s `trackClientEvent()` minted a new `event_id` on every call with no way for a caller to reuse one across its own retries, making the backend's idempotency guarantee unreachable from the one place that needs it -- added an optional `eventId` request field, and exported `generateIdempotencyKey()` (previously internal-only) so a caller can mint one to reuse. One existing round-2 regression test's expectation flipped from reject-on-omitted-guest_id to accept-and-correctly-attribute, matching the corrected design; all other existing owner-check tests still pass unchanged. Added regression tests for all 4 fixes plus the UUID-shape/categorical-value/session-derivation behavior generally; `postgresql-check` (69/69 client-event tests) and `frontend-check` stay green. | None -- ready for user review/commit. |
| 2026-09-10 | Addressed a second human PR review round (PR #113): the prior round's slug-shape check for `mode`/`gap_category` was sharpened to a real per-product closed vocabulary, since a value like `please_rewrite_this_proposal_before_friday` is a valid slug and still arbitrary content re-encoded under an allowlisted key. Implemented the reviewer's suggested mechanism: `config/loader.py`'s `_load_analytics()` now parses and validates a `client_event_properties: {mode: [...], gap_category: [...]}` block in each product's `analytics.yaml` (a mapping of property name to a list of non-empty strings; malformed shapes raise `InvalidConfigShapeError` at config-load time, matching every other config validation in this loader), and `ClientEventService._validate_properties()` checks membership in `product.analytics["client_event_properties"]` instead of a generic shape/regex. A product that declares nothing for a key cannot use that key at all -- the default is an empty closed set, never "anything goes" -- which keeps the platform-core/product-platforms boundary intact without inventing any product's real vocabulary. Declared `kernel_demo`'s own smoke-test vocabulary (`mode: [one_run, two_run]`, `gap_category: [budget, timeline, scope]`) since it's the generic proof product every test in this file already exercises; deliberately did *not* invent one for `proposal_ai` (ANY-227's real product, merged into this branch since round 1) since it has no mode/gap-selection concept implemented yet (single scenario, no such input fields) -- inventing values now would be speculative, not a real product contract, so `proposal_ai` correctly rejects `mode`/`gap_category` entirely today, which is itself covered by a new test. Found and fixed a real bug while wiring this up: `ConfigRegistry` freezes loaded YAML lists into tuples, so the initial membership check (`isinstance(allowed_values, list)`) rejected every value including ones on the declared list -- caught immediately by the full postgres test run (4 failures), fixed to accept `(list, tuple)`. Added loader-level tests (`test_config_loader.py`): vocabulary loads correctly, non-mapping `client_event_properties` rejected, non-list property value rejected. Rewrote the now-obsolete length-boundary property tests as vocabulary-membership tests. `postgresql-check` (70/70 client-event tests), the new loader tests, and `frontend-check` all green. | None -- ready for user review/commit. |

## Open questions

None — the approved design spec and ANY-410 already resolved the metric-contract and event-taxonomy
ambiguities; this plan implements the code they describe.

## Follow-up debt

- ProposalAI vertical-slice implementation (ANY-227) will be the first real consumer of
  `trackClientEvent()` from an actual product page.
- A machine-readable metric registry, if a future ticket demonstrates code needs to consume
  `trust_class`/`producer`/`blind_spots` programmatically instead of as documentation.
