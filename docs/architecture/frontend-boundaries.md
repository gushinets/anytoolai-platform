# Frontend Boundaries

Frontends are thin delivery surfaces.

They may:

- collect input;
- create guest identity through backend APIs;
- store the opaque backend-created guest id locally;
- fetch runtime config;
- call approved scenario APIs;
- show job progress;
- fetch scenario session state;
- render artifacts;
- display backend-provided next actions;
- create backend-owned handoffs.
- open backend-owned handoff consent pages;
- capture email for quota/paywall flows;
- track client events.

They must not:

- store system prompts;
- choose provider/model;
- invent workflow steps;
- bypass quota;
- decide quota state authoritatively;
- call LLM providers directly;
- own authoritative scenario state.

## Internal Atom Lab exception

`/atom-lab` is an internal static shell hosted by `platform-api`, outside `apps/web-mirror`, CE-kit,
and product extensions. The shell contains no prompts, schemas, examples, catalog rows, provider
settings, or access code. After a user enters the separate code, JavaScript keeps it only in the
current module's memory and sends it in `X-Atom-Lab-Access-Code`; it must not use a URL, cookie,
`localStorage`, `sessionStorage`, analytics, or console logging for the code.

Only `/v1/atom-lab/*` may return registry prompts and schemas or later accept laboratory
prompt/model choices. The server remains authoritative for fixed contracts and runtime scope.
Ordinary product routes, web-mirror, shared frontend packages, and extensions do not import Atom
Lab authority and continue to follow the prohibitions above.

The public scenario/session/result/artifact/handoff surface treats a server-classified lab session
and every resource linked to it as not found. Unknown non-public runtime-scope values also fail
closed. The public scenario-start DTO forbids metadata and runtime-scope fields, so a browser cannot
turn a normal request into a laboratory request.

MVP-A2 Client Surfaces owns shared `ce-kit`, the `apps/web-mirror` multi-product host, and shared
browser journeys. Freelancer Suite owns each product's web definition/page and any optional
product-specific Chrome Extension. Product surfaces consume shared clients rather than copy
transport, storage, identity, quota, polling, result, next-action, event, or handoff code. MVP-A1 has
no frontend dependency.

Inside `apps/web-mirror`, the composition layer may import the shared product runtime and enabled
product definitions. Shared runtime must not import individual products or contain product meaning.

### `@anytoolai/shared-ui` (ANY-503)

`packages/frontend/shared-ui` is the canonical design-system package (Bundle 3 tokens plus
`Button`/`Card`/`CopyButton`/`Input`/`Select`/`Spinner`/`TextArea`/`Toast`) for every web product
surface. Dependency direction: `shared-ui` depends only on `react`; `apps/web-mirror` (its layout,
page background/fonts, and every product's `Fields`/result/error chrome) depends on `shared-ui`.
`shared-ui` must not import `ce-kit`, `web-result-kit`, or any product-specific module -- it owns
presentation only, never product meaning or client transport/state. See
[`shared-ui/README.md`](../../packages/frontend/shared-ui/README.md) for the current presentation
contract: color pairs, typography, exterior control minimums, textarea and responsive rules. See
`docs/exec-plans/active/any-503-adopt-bundle3-design-system.md` for the token-gap and font-sourcing
decisions this package's implementation made.

After A13/A15 (ANY-8, ANY-170/ANY-171/ANY-226), `createGuestIdentity()`, `getQuota()`,
`startScenario()` (via `prepareScenarioStart()`), `getScenarioSession()`, `pollScenarioSession()`,
`nextAction()`, and `getResult()` are real CE-kit helpers backed by `PlatformApiClient`.

Required `ce-kit` capabilities:

- `createGuestIdentity()`
- `getRuntimeConfig()`
- `startScenario()`
- `getScenarioSession()`
- `nextAction()`
- `copyResultAndRecordActivation()` (clipboard write first, then exactly one `copy_result`
  next-action when the session has an active checkpoint, none otherwise -- the shared copy-button
  activation contract every product's result page uses)
- `pollScenarioSession()`
- `getResult()`
- `createHandoff()`
- `openHandoffConsent()`
- `getHandoff()`
- `acceptHandoff()`
- `declineHandoff()`
- `captureEmail()`
- `trackClientEvent()`
- `renderQuotaState()`
- `renderJobStatus()`
- `renderError()`

A15 ownership and delivery slices:

- A13 backend guest identity and quota enforcement are implemented;
- A15a / ANY-170 delivered the central `PlatformApiClient`, async storage, guest identity, runtime config,
  safe errors, cancellation, and OpenAPI drift foundation;
- A15b / ANY-171 delivered real quota HTTP calls, idempotent scenario start, bounded session polling,
  next actions, typed `429 quota_exhausted` handling, and CE integration tests;
- A15c / ANY-226 delivered `getResult()` over the Platform Core frontend-safe result API (A12b /
  ANY-217), with typed `result_artifact_not_found` / `result_artifact_unavailable` handling via
  `isResultNotFound()` / `isResultUnavailable()`;
- A18 owns shared client handoff helpers and web consent; product-specific handoff routes remain in
  Freelancer Suite.
- A18a / ANY-222 delivered `createHandoff()` and `openHandoffConsent()` as real CE-kit helpers over
  the A17 `/v1/handoffs` create endpoint, with typed `handoff_not_found` / `handoff_source_invalid` /
  `handoff_target_schema_invalid` handling via `isHandoffNotFound()` / `isHandoffSourceInvalid()` /
  `isHandoffTargetSchemaInvalid()`.
- A18b / ANY-223 delivered `getHandoff()`, `acceptHandoff()`, and `declineHandoff()` as real CE-kit
  helpers over the A17 `/v1/handoffs/{token}`, `.../accept`, and `.../decline` endpoints, with typed
  `handoff_expired` / `handoff_already_accepted` / `handoff_declined` / `handoff_failed` /
  `handoff_not_actionable` / `handoff_acceptance_failed` handling via `isHandoffExpired()` /
  `isHandoffNotActionable()` / `isHandoffAcceptanceFailed()` (using `isQuotaExhausted()` for final used exhaustion and
  `isQuotaCapacityReserved()` for temporary capacity; both are HTTP 429), plus the `web-mirror` `/handoff/{handoff_token}` consent page (`HandoffConsent`) that
  renders the backend safe preview and all terminal states -- web-mirror's first real wiring to
  CE-kit. Component/browser tests cover this over Vitest + Testing Library; a real running
  dev-server route is ANY-224's job.

## Result activation and composite renderers (ANY-248)

`ProductDefinition.emitsResultViewed?(result)` is the one optional hook for a product whose
`web.result_viewed` is narrower than "any completed result". Default is true (ProposalAI and Client
Update Writer are unchanged, they activate on `copy_result`). The run still completes and renders
and `scenario_completed` still fires (once per session, from an effect after the result phase has
committed, never while the result is merely fetched), carrying `resultViewed: false`; only the client-events
tracker skips `web.result_viewed`. A throwing hook counts as false. It exists because the
client-event property allowlist has no question-count property and Platform Core is not changed
for a product. Brief Decoder's frontend result `R` is a composite
object (`brief`, `issues`, `questions`, `document`) rendered by product-owned markup; only its
copy-ready `document` goes through the shared `ResultView`, using a product-side
`composeCopyText` that implements `renderer_contract.yaml`'s `canonical_field_composition`.
The canonical backend output additionally contains `brief_text` (the caller's original brief, kept
as handoff material); the frontend result intentionally excludes it: the product parser drops it
and it is never rendered or copied, so it must not be added to the frontend result model.

## Data-processing notice (ANY-844)

`ProductRunPage` shows a shared data-processing notice before submit in all seven host locales.
`NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL` is an optional build-time absolute HTTP(S) URL for its
privacy-policy link (new tab); missing or invalid values hide the link, not the notice. Public
deployments must supply the approved URL and rebuild after changes. `prod-up` validates it before
profile generation or Docker calls; development, fake smoke and maintenance keep it optional.
Browser-local draft text may be lost on reload or navigation; the shared notice does not promise
recovery, since only products opting into draft persistence attempt it.

## Cross-product handoff in the web host (ANY-244)

The shared runtime, not a product, owns the web side of a handoff:

- `ProductDefinition.handoff` (`handoffDefinitionId`, `targetProductId`) makes `ProductRunPage`
  render a button beside "New task" (label from `<messageScope>.continueToTarget`). A click calls
  `createHandoff` for the shown result and opens `/handoff/{token}` in the same tab. The button is
  hidden unless the target is in `NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS` (unset = all).
- `HandoffConsent` sends the user to `/products/{targetProductId}?session={id}` right after a
  successful Accept; later preview GETs redact the ids after TTL, while an owner-checked accept
  replay can still return the existing target linkage.
- `/products/{id}?session=` reaches the product as `attachSessionId`; `ProductRunPage` polls that
  already-queued session and renders its result without a new start or reservation; its backend
  success consumes the existing reservation. "Try again" re-polls that session, and an unknown session id (404) ends in the run-failed state. The
  route reads `?session=` from its `searchParams` prop (not `useSearchParams`, whose Suspense
  boundary would turn the unknown-product 404 into a 200), removes it from the address bar so a
  bookmark or shared link does not carry it, and keeps it in the tab's `sessionStorage` so a reload
  still shows the result the accept already queued. `useAttachSession` is the one owner of that
  state (`AttachProps`: `attachSessionId`, `onAttachBegin`, `onAttachEnd`, threaded route -> shell ->
  product -> `ProductRunPage`; no analytics event is involved). The page reports two facts: it started
  polling the session, and the person moved on from it ("New task" on the attached result, own work
  whose result replaced it on screen, a mode switch, or its terminal failure). The owner forgets the
  persisted id only for an end that follows a begin, so a failed boot, or typing in another mode,
  forgets nothing, and a run that failed to start leaves the attached result restorable. After consent the linked scenario session is an ordinary runtime handle:
  the platform's session/result GETs take no guest id and the session has no expiry of its own, so
  the id is an opaque public handle, not proof of ownership, and not the short-lived handoff bearer
  token (which does have a TTL and redaction contract). If a bounded lifetime is ever wanted for it,
  that is a backend lifecycle contract, not a frontend assumption. The attached result must come
  from this product's scenario: its backend-owned `schemaRef` and `schemaVersion` are checked
  against the selected scenario's output schema from runtime config (a declared version must match;
  a ref keeps its name across a version bump) before the product parser sees it.
- Products opting in through `ProductDefinition.draft` keep form values and their last accepted
  scenario session in the tab's `sessionStorage`
  (`anytoolai.product_draft.<productId>.<messageScope>`). Reload resumes polling without a new start.
  "New task" clears both; terminal failure clears only the matching saved run and keeps the draft.
  A failed attachment preserves a different saved own run. User text stays in
  tab storage, never events, URLs or logs. ProposalAI and all three Client Update Writer modes opt in;
  handoff attachment takes precedence. The last selected draft scenario is stored separately under
  `anytoolai.product_draft_scenario.<productId>`. Multi-mode pages resolve it against their current
  opt-in definitions before mounting a form, so reload opens the correct mode without briefly
  polling another mode's saved run. Explicit mode selection, field edits and accepted own starts
  remember that scenario; merely viewing an attached result does not replace it. New task clears
  the current mode's fields/run and retains the mode selection; other modes keep separate drafts.
- Once an own start and its scenario selection are confirmed saved, the per-product attachment
  entry records a preferred own-run reference (draft key and session id). The route lets draft
  recovery resume that run immediately, including while an old attached result is still displayed.
  Rejected/ambiguous starts retain the previous attachment; failed persistence delays its
  retirement until the new result commits. Only the replaced attachment reference is retired;
  other pending attachments remain fallbacks. A late
  background Accept cannot replace the preferred own run, while an explicit attachment open can.
  Clearing or losing the referenced saved run releases its priority over remaining attachments.
- A spent (accepted/consumed) token that still names the target session shows an explicit "Open result" on the
  consent page, for the case where the Accept response was lost and the person reloaded instead of retrying
  (a retry that gets "already accepted" redirects on its own). It never redirects automatically on load.
- The redirect happens only when `products/attachTargets.ts` lists the accepted target scenario
  (a registered, enabled product page that can attach it); otherwise the consent page keeps showing
  the terminal status. The consent route injects that check, so it does not bundle every product.
- `web.result_viewed` for an attached or draft-restored session is sent with the session alone, without a guest: the backend
  derives guest and chain from the session and rejects a different explicit guest, which is what the
  current one is after a reload without a usable `localStorage` (a fresh in-memory guest). The tab keeps, per
  session, the event id, the web session id it was sent under, and whether the backend accepted it:
  accepted means never again; anything else (a lost response, a timeout) is retried on the next report with
  the SAME `event_id` and the SAME web session id, so a first attempt that the backend did commit is deduped
  there (`trackClientEvent` requires the same id on every retry of one logical event) instead of adding a
  second row. The web session id matters: the backend compares the whole event for a reused id, and a reload
  without a usable `localStorage` mints a new web session id, which would otherwise be rejected as
  `client_event_id_conflict`; such a conflict is itself treated as "already recorded".
- The redirect after Accept (and the "Open result" action, and what is remembered) needs an `accepted` or
  `consumed` preview that names a non-empty target session the host can open; any other status with a
  session id (for example `failed`) stays on the consent page's terminal status. One remembered session
  per product per tab, and the newest accepted one wins by the handoff's own order (its `expiresAt`, which grows with creation time, compared as a time to the microsecond, since the backend clock has microseconds, and not as a string: `...:00.5Z` is later than `...:00Z`), not by which response arrives last: an older Accept that settles late cannot replace the newer session the person is already on. A session the person opens themselves (the Accept they just clicked, or "Open result" on a spent token) is chosen outright: it is what the tab restores from then on, even when an older one, while the newest accepted session stays remembered as its fallback (and its order as the guard against late Accepts): when the opened one ends, that newer accepted session is what the next visit restores, and a newer Accept that settles late meanwhile only becomes that fallback, never the restored one. An Accept whose answer was lost or unreadable (transport failure, timeout, a non-preview 2xx) is resolved by one authoritative preview read, on the page (open the queued session, or let the person retry) and after leaving it (remember the queued session only).
- A product with a `handoff` must define `<messageScope>.continueToTarget` in its messages. A
  multi-mode product (each mode its own `ProductDefinition`) supplies only its mode list to the shared
  `products/shared/MultiModeProduct.tsx`, which owns the selector, the clean remount per mode, the
  one-shot handoff attach, and the rule that the mode switch (and the form) stay locked while the page
  is "locked" (`onLockedChange`): a run in flight (including an ambiguous failure that may still be
  running server-side), a handoff being created or navigated to, or an attached session that is still
  booting. A failed boot of an attached session releases the lock and leaves the persisted session
  untouched (an `onAttachEnd` that was never preceded by `onAttachBegin` does nothing), so a reload
  still retries it.
- The source-side handoff button creates the handoff (state "creating", form and mode switch locked),
  then starts the same-tab navigation ("navigating"). Both show a visible "Opening the next step…" status
  and lock the page until it unloads; a bfcache return resets it. There is deliberately no timer: how
  long a navigation takes is a guess, and unlocking on a guess lets a new run start under a
  navigation that is still going to leave for the previous result. A cancelled navigation (Esc, Stop)
  fires no event, so the "navigating" status carries an explicit "Stay on this page" action. It calls
  `window.stop()` before unlocking: otherwise a merely slow navigation could still commit after the
  person started a new run here and abandon that run's result. `window.stop()` also aborts every other
  in-flight request of the document, and the one that must survive is a copy activation POST (it
  outlives the "Copied" feedback), so the action is disabled while one is in flight.
- An Accept whose response arrives after the person left the consent page still happened server-side and
  reserved capacity: the target session id is kept for that product's next visit
  (`rememberAttachSession`), and nothing navigates. An error such as "already accepted" that
  arrives after the person left proves the Accept went through, so one read of the authoritative preview
  names the session it queued and that is kept too; nothing else continues. Left before any answer
  arrived, the id is simply unknown.
- The copy text of a product whose renderer contract fixes its wording (Acceptance Builder) is the
  contract's English text, not UI-locale copy.

## Web i18n (ANY-519)

`apps/web-mirror` localizes product-page UI. The mechanism is host-owned; the words are
product-owned. Code: `apps/web-mirror/src/i18n/` (library `use-intl`, imported only from there).

- **Supported locales:** `en fr it de es ru pt` (BCP 47 base tags; generic `pt`, no `pt-BR`/`pt-PT`).
  Display names are endonyms and are never translated.
- **Resolution order:** persisted explicit choice, then `navigator.languages` (first supported base
  language; `de-AT`/`pt-BR`/`fr-CA` map to `de`/`pt`/`fr`), then `en`. Resolved client-side before
  first paint; server and first client render use `en`. There are no locale-prefixed routes and no
  server-side `Accept-Language` resolution.
- **Fallback:** English underneath every locale (deep merge in `LocaleProvider`), so a missing key
  shows English rather than a key path. Non-English message files are typed
  `Shape<typeof en>`, so a missing or extra key fails typecheck; `test/i18n.test.ts` additionally
  checks key parity, ICU placeholders and syntax for the host and every registered product.
- **Persistence:** localStorage key `anytoolai.ui_locale`, written only on an explicit choice (an
  auto-resolved locale is not persisted, so a changed browser language keeps being respected).
  Read synchronously, unlike ce-kit's async storage adapter, to avoid a flash of English. The
  document `<html lang>` follows the effective locale.
- **Selector:** one `LanguageSwitcher`, rendered by `ProductPageShell` beside the localized product
  title for every registered product on `/products/{productId}`. `ProductRunPage` omits its own
  title and selector when mounted in that shell. A product never renders its own selector. Changing locale
  never remounts the product (no `key={locale}`), so form values, run state and the selected
  Client Update Writer mode survive.
- **Ownership:** the host owns locale resolution/persistence/provider/selector and the `host`
  namespace (generic runtime/result/error/validation copy only -- never product meaning). Each
  product owns its `product` namespace: title, field labels, validation field names, mode names,
  submit/running/failure and quota copy, supplied through `RegisteredProduct.messages`.
  `ProductDefinition` describes behavior only; it names its copy with `messageScope` and carries no
  English literals -- one optional flag, `hasDescription`, tells the shared runtime whether to look
  up a product's own `description` message, without the definition itself holding any text. `neutral|warm|firm` tone labels are product
  vocabulary (a product-owned wire enum's visible labels), never host's: Client Update Writer's
  native tone radios read the plain labels from its own `tone` messages; ProposalAI defines
  descriptive `toneOptions` labels ("Warm & personable" etc.) in its own messages. Each product
  owns its wording even when the wire enum is the same.
- **One-screen workspace (ANY-528, ANY-530):** `ProductRunPage` renders every product as an input
  card beside a result card (stacked below 860px; `ProductPageShell` always uses the wide shell).
  The runtime keeps the form and the latest successful result together, with the result tied to the
  input snapshot that produced it. Editing marks the displayed result as based on previous data; a
  regeneration keeps the old result visible until the new one arrives; waiting and errors appear in
  the result card; "Copy" and "New task" share one action group; "New task" clears both cards,
  refreshes quota and focuses the first `textarea`/`input`. There is no result-only mode and no
  per-product layout switch. Host messages own the copy every product shares
  (`workspace.inputTitle|previousDetails|backToInputs|newTask|handoffFailed|handoffOpening|handoffStay`); the product owns the noun-specific
  copy under its `messageScope` (`resultTitle|placeholder|regenerate`, one set per Client Update
  Writer mode). The shared runtime still owns start, retry, quota, and copy behavior.
- **Waiting progress (ANY-842):** the shared runtime shows elapsed time and a localized stage hint
  throughout submission and polling, including regeneration over a previous result. Hints change at
  30 and 60 seconds, based on observed 4.5–42-second product runs; these are expectations, not
  deadlines. Products provide only their `<scope>.running` status and must not add their own timers.
  The accessible timer has live announcements off and sits outside the status region. Accepted own
  runs retain their client start timestamp where draft recovery is enabled; legacy drafts and
  attached handoff sessions time from local observation. Ambiguous/accepted retries retain the
  timestamp; a proved capacity rejection resets timing on retry while preserving the request key;
  leaving the pending state removes the timer. Polling policy remains owned by ANY-777.
- **First-run example (ANY-847):** ProposalAI, Brief Decoder and each Client Update Writer mode
  render shared `products/shared/ExampleDisclosure.tsx` first in their `Fields`: a collapsed
  `<details>` showing inputs and a sample result. Static text never prefills the form or changes
  typed input or tab drafts. Host messages own `example.toggle|inputs|output|note`; products own
  `<scope>.example.intro|inputs.<field>|output` in all seven locales. Sample inputs pass their
  product validators in tests. Prepaid Request keeps Amount short and puts context in Billing notes.
- **Validation:** shared validators return structured `FieldError` data (`required`,
  `outer_whitespace`, `max_length`, `product`), never prose; `FieldErrorMessage` renders it in the
  current locale. Backend schema validation stays authoritative.
- **UI locale is not the generated-content language.** ProposalAI's web form has no output-language
  input at all (ANY-521/PR #140 removed it; output language derives from `task_text`, with an
  explicit `language` override remaining backend/schema-only for non-web callers). Client Update
  Writer likewise exposes no `constraints.language` UI. Neither product's `toInput` ever reads the
  UI locale, so independence holds by construction; any future output-language input must keep that
  same rule -- changing UI locale must never change it, and vice versa.
- **Wire values stay untranslated.** Closed-set values (`neutral|warm|firm`, mode ids, enums,
  statuses) are sent to the backend as-is; only visible labels are translated. Prompts, schemas and
  backend product config never depend on UI locale.
- **`@anytoolai/shared-ui` and `@anytoolai/ce-kit` stay localization-agnostic:** they take text via
  props/children and never import the host i18n layer. (`shared-ui`'s `CopyButton` still has English
  literals; web-mirror does not use it, and adopting it means passing labels.)
- **Shared runtime errors** keep a closed reason, not finished text (`Phase.retryable-error.reason`),
  so an error already on screen re-localizes on a locale switch.

### Recipe: translations for a new web product

1. Create `products/<name>/messages/en.json` (English is the semantic source: `title`,
   `quotaRemaining` with `{remaining}`/`{limit}`, per-scope `submit`/`running`/`runFailed`, `fields`,
   `fieldNames`, and any product validation keys). Every scope also needs `resultTitle` (the
   result card heading, a noun for what the run produces), `placeholder` (shown before the first
   result) and `regenerate` (the submit label once a result is shown). Want a description under the
   title? Add `description` here and set `hasDescription: true` on the `ProductDefinition` -- the
   shared runtime only looks it up when the flag is set. A first-run example goes under
   `<scope>.example` (`intro`, `inputs.<field>`, `output`) and is rendered by the product’s `Fields`
   through `ExampleDisclosure`.
2. Add `fr it de es ru pt` JSON files with the same structure; use the typographic apostrophe `’` (a
   plain `'` before `{` starts ICU quoting); keep placeholders and plural categories. Keep
   product-owned vocabulary such as tone labels in the product's locale files. Reuse host keys
   for shared runtime conditions; handoff uses `errors.quotaCapacityReserved` for occupied capacity.
3. Export `Record<Locale, Shape<typeof en>>` from `messages/index.ts`.
4. Register the product with `messages` in `products/registry.ts`; every locale must include a
   nonempty `title` for the page shell. The shell supplies the provider and language selector;
   the completeness tests cover the new product automatically.
5. In the product, read text with `useProductT()`, render field errors with `FieldErrorMessage`, and
   set `messageScope` on each `ProductDefinition`. Never read the UI locale in `toInput`. The
   product's `Result` must be embedded (`ResultView embedded`, no `Card` of its own; use `h3` for
   headings inside it) and pass `secondaryAction` through to sit beside "Copy"; the first
   `textarea`/`input` of its `Fields` is what "New task" focuses.

### Recipe: add a locale

1. Add it to `LOCALE_NAMES` in `i18n/locales.ts` (endonym).
2. TypeScript then requires an entry in every locale record: add `i18n/messages/<code>.json`,
   `app/homeMessages/<code>.json`, `components/handoffMessages/<code>.json` and
   `products/*/messages/<code>.json` and register each in its typed bundle index.
   TypeScript checks required keys and value types; i18n tests compare exact structure and inspect
   raw JSON for strict syntax and duplicate keys.
3. Run `pnpm --filter @anytoolai/web-mirror test`; the parity, placeholder and ICU-syntax checks
   fail on any gap. No product runtime change is needed.

## A12/A13 public scenario runtime contract

The A12/A13 public runtime surface is:

- `POST /v1/identity/guest`
- `GET /v1/products/{product_id}/quota?guest_id={guest_id}`
- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start`
- `GET /v1/scenario-sessions/{id}`
- `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}`
- `GET /v1/results/{result_artifact_id}` (A12b / ANY-217)

`startScenario()` request body:

```json
{
  "frontend_id": "kernel_demo_ce",
  "input": {
    "source_text": "deadline budget deliverables"
  },
  "guest_id": "guest_optional",
  "user_id": "user_optional",
  "source_frontend_instance_id": "instance_optional"
}
```

For products with `quota_policy_ref`, `guest_id` is required and must be an opaque id created by
`POST /v1/identity/guest`.
When a product's quota policy uses `dimension: scenario`, quota state checks also provide
`scenario_id`; product-wide policies do not require it.

`startScenario()` returns a stable queue-and-return payload:

```json
{
  "scenario_session_id": "scenario_session_123",
  "job_id": "job_123",
  "status": "started",
  "allowed_next_actions": [],
  "result_artifact_id": null
}
```

`getScenarioSession()` returns the frontend-safe polling snapshot:

```json
{
  "scenario_session_id": "scenario_session_123",
  "job_id": "job_123",
  "status": "completed",
  "current_checkpoint_id": "result_ready",
  "allowed_next_actions": ["copy_result", "create_handoff"],
  "result_artifact_id": "artifact_123"
}
```

`nextAction()` request body:

```json
{
  "checkpoint_id": "result_ready"
}
```

The frontend must poll `getScenarioSession()` for runtime progress in A12. `job_id` is returned for
correlation and future expansion, but job polling is not the primary public runtime contract for
this slice.

Safe API behavior:

- `404` for unknown scenario, unknown session, or unknown guest identity;
- `409` for stale checkpoints, non-actionable checkpoints, or disallowed next actions;
- `422` for invalid frontend selection, non-object scenario input, or missing guest identity;
- `429` with `quota_exhausted` when used quota reached the configured limit;
- `429` with `quota_capacity_reserved` when remaining quota is temporarily occupied by reservations.

A start error describes one HTTP attempt. If an earlier send of that prepared key timed out, lost
its response or returned an unreadable acceptance, a later rejection cannot prove the earlier send
will not commit. Preserve the key, field/Submit/mode locks and same-key recovery across automatic
and manual retries, including enveloped 4xx, quota exhaustion and unknown-guest responses. Do not
enter a paywall or replace guest identity while that execution is unresolved. Once a session is
known, retry polls it instead of sending another start.
An explicit `idempotency_key_conflict` proves that the immutable request does not own that key's
execution; discard that handle and allow a fresh key rather than keeping an unrecoverable lock.

When the key has no unresolved sends, definite 4xx rejections unlock the form and allow a fresh key.
Repeated definite rejections alone do not create uncertainty. For `429 quota_exhausted` in that case:

- keep quota state advisory in the frontend and treat the backend response as authoritative;
- disable the run action or show a clear quota-exhausted state after the response;
- do not show a progress row, job, or partial session for the rejected attempt because the backend
  creates none.

For `quota_capacity_reserved`, show temporary occupancy and retry the same prepared start/key
(or handoff token/guest). Do not open an exhausted/paywall state or manufacture a new execution.
The rejected attempt leaves no session/job/reservation; quota refresh is read-only.
With no unresolved sends, fields, ordinary Submit, mode selection and shell busy indication unlock.
Retain the key for an unchanged retry; safe edits create a new key. Uncertainty belongs to that key,
not subsequent logical submissions. Ambiguous polling and accepted or attached executions retain
their reattachment locks.

Frontend-safe responses must not expose prompts, provider policies, provider/model names, retry
budgets, PydanticAI run ids, LiteLLM response ids, or raw unsafe exception text.

Web product pages and optional product Chrome Extensions complete through shared client contracts
and the frontend-safe result API. Product pages use `/products/{product_id}` in `apps/web-mirror`;
shared result and consent routes remain backend-state consumers. None of these surfaces is a
prerequisite for MVP-A1.

## A12b public result artifact contract

`GET /v1/results/{result_artifact_id}` returns only the normalized canonical workflow result for a
`result_artifact_id` already surfaced by `startScenario()` / `getScenarioSession()`:

```json
{
  "result_artifact_id": "artifact_123",
  "scenario_session_id": "scenario_session_123",
  "job_id": "job_123",
  "workflow_id": "kernel_demo.single_action_extract_v1",
  "workflow_version": 1,
  "schema_ref": "kernel_demo.extract_output_v1",
  "schema_version": 1,
  "created_at": "2026-01-01T00:00:00Z",
  "output": { "...": "workflow output schema-shaped payload" }
}
```

The endpoint is scoped to tenant/region and only ever serves an artifact that is: `stored`, of the
canonical `structured_output` type (never `structured_output_debug_raw` or any raw/debug artifact),
tagged `artifact_role: workflow_result`, linked as `result_artifact_id` on a `succeeded` job whose
tenant/region/product/frontend match the artifact's, and re-validated against its workflow's
output schema/version at read time. `output` is never returned raw from storage without this
re-validation pass.

Raw/debug artifacts (`structured_output_debug_raw` type, or any artifact not tagged
`artifact_role: workflow_result`) are rejected outright by the canonical-artifact guard above and
never reach response serialization.

Separately, because the endpoint returns the full normalized output *object* (unlike handoffs,
which only ever expose an explicit per-field allowlist mapping), and shipped workflow output
schemas may still declare `additionalProperties: true`, `ResultService` additionally rejects any
normalized output containing a *key* that exactly matches (after normalizing `-`/`_`/case to a
common form) a small, results-specific denylist, at any nesting depth. The list covers both the
actual bare internal field names used for provider/prompt lineage elsewhere in the platform
(`prompt`, `prompt_ref`, `provider`, `model`, `model_ref`, `provider_policy_ref`,
`provider_call_id`, `gateway_backend`, `gateway_model`, `pydantic_run_id`,
`litellm_response_id` — `model_ref` mirrors `config.loader.FORBIDDEN_RAW_LLM_FIELDS`, the
config-authoring-time guard against the same raw-LLM field names; the rest of that list
(`temperature`, `top_p`, `seed`, `stop`, `stream`, `tools`, ...) is deliberately not mirrored
here, since those are generic words with real domain-field collision risk) and additional
compound/lineage-shaped names not currently used verbatim elsewhere but plausible leak shapes
(`system_prompt`, `raw_prompt`, `prompt_template`, `raw_provider`, `provider_output`,
`provider_model`, `provider_name`, `provider_policy`, `model_name`, `model_id`, `model_version`,
`litellm`, `litellm_debug_info`, `trace_id`, `parent_trace_id`). Key normalization strips `-`/`_`
separators and casefolds, from both the incoming key and the marker, then compares the results for
equality — it deliberately does **not** try to re-insert word boundaries into camelCase/acronym
spellings (an earlier revision did, and needed a growing pile of regex rules that still missed
fully-uppercase spellings like `TRACEID`/`GATEWAYMODEL`, which have no lowercase letter to anchor
a boundary on, and multi-acronym PascalCase like `LiteLlmDebugInfo`, which splits into more words
than its marker has). Comparing separator-stripped canonical forms sidesteps that ambiguity
entirely while still being a whole-string equality check, so `provider-model`, `providerModel`,
`GATEWAYMODEL`, and `LiteLlmDebugInfo` all resolve to the same canonical form as their marker.
Matching is against the whole normalized key, not a
substring: an earlier
revision matched markers as substrings, which both left the bare internal names above undetected
(they were deliberately excluded from a substring-based list to avoid colliding with fields like
`car_model`/`insurance_provider`) and, separately, rejected unrelated legitimate compound fields
that happened to contain a marker substring (e.g. `vehicle_model_id`, `car_model_version`,
`insurance_provider_name`, `business_trace_id`). Whole-key matching fixes both. This list is
deliberately its own, narrower policy rather than a reuse of `common.logging.SENSITIVE_KEY_PARTS`
(the log-redaction denylist): a false positive there just redacts a logged value, while a false
positive here would make an entire valid, already-succeeded result silently disappear as a 404, so
broad single-word markers like `email`/`token`/`handoff`/`secret` are intentionally not used. This
is a defense-in-depth backstop against those specific key names while workflow output schemas are
not yet uniformly closed — it is not a general guarantee against every possible form of
provider/prompt/debug content (an unlisted key name, or a value rather than a key, is not
inspected). It also cuts both ways: because `prompt`/`provider`/`model` are blocked as bare exact
keys (not just compound markers), a future workflow whose *legitimate* schema-declared output
happens to use one of those exact names (e.g. a prompt-generation product returning a field
literally called `prompt`) would incorrectly 404 rather than leak. This is an accepted trade-off
of a key-name denylist over a schema; a workflow needing a legitimate field with one of these
exact names must pick a differently-named field. Closing the relevant workflow output schemas, or
introducing a dedicated public output schema per workflow, remains open follow-up work.

Safe API behavior — both cases return `404`, and neither ever includes artifact/job internals,
prompts, or provider/model identifiers in the response body:

- `result_artifact_not_found`: the id is unknown, or belongs to a different tenant/region;
- `result_artifact_unavailable`: the artifact exists in the caller's tenant/region but is not an
  available canonical result (a raw/debug artifact, an artifact from an unfinished/non-succeeded
  job, an artifact with schema/version drift, or content that fails re-validation against its
  declared output schema).

`getScenarioSession()` only ever surfaces a non-null `result_artifact_id` once the job has
succeeded, so this endpoint is not meant to be polled for an in-progress job. The two codes
intentionally differ so a caller holding a previously-valid id (e.g. from before a config redeploy
changed the workflow's output schema/version) can tell "this id is wrong or out of scope" apart
from "this id was valid but the artifact is no longer an available canonical result." This does
distinguish "exists in my own tenant/region" from "unknown," i.e. it is not a strict
no-existence-oracle guarantee across all callers who can reach an id in-scope — it only guarantees
that a caller cannot learn anything about artifacts outside their own tenant/region.

The canonical-artifact layer (job/workflow/schema consistency and schema re-validation) is shared
with the handoff payload builder through `artifacts.canonical.resolve_canonical_workflow_result`.
Result API and metered publication additionally share `results.validation`'s recursive forbidden-key
check. Consumption therefore requires the full Result API availability boundary, not just the
canonical artifact predicate or an artifact row. See [quota model](quota-model.md).

## A17 public handoff contract

The backend now provides `POST /v1/handoffs`, token-based preview, accept, and decline endpoints.
The create response is the only response containing the opaque plaintext token. Frontends must
treat it as a short-lived bearer capability, avoid analytics/logging/storage beyond the consent
navigation need, and never derive or inspect its contents.

The unexpired preview response contains only display-safe product/scenario identity, status,
expiry, bounded config-mapped preview data, and nullable target session/job ids. It never contains
hidden target context, source artifact/session/job identifiers, token hashes, artifact metadata,
prompts, providers/models, or debug data. After token TTL, preview GET returns `status=expired`,
empty preview content and null target identifiers while preserving durable terminal state.
An accept replay by the original owner is checked before TTL denial and returns its existing safe
target linkage, including after expiry; it creates no execution or new reserve. New acceptance and
decline still enforce TTL. The backend owns both rules; clients must not infer them from local time.

Accept creates and links the target session. An immediate definition may return a target job; a
deferred definition returns a retrievable `waiting_for_user/handoff_ready` target session with
`job_id: null`. Frontends must not start or fabricate a target workflow merely because the user
accepted; start policy belongs to the config contract and backend.

## Reservation-aware quota clients (ANY-507 stage 4)

CE-kit preserves guest quota fields and maps `successful_used_count`, `legacy_used_count`,
`reserved_count`, `available_count`, `read_at` to `successfulUsedCount`, `legacyUsedCount`,
`reservedCount`, `availableCount`, `readAt`. `remainingCount` includes reserved capacity;
`availableCount` excludes it, and `exhausted` depends on remaining, not available. The parser rejects
missing/invalid counters, inconsistent arithmetic and invalid aware timestamps. Shared web refreshes
after acceptance and terminal success/release. `quota_capacity_reserved`
is retryable with the same prepared key or handoff token/guest, without exhausted/paywall UI.
`quota_exhausted` remains final used exhaustion. Advisory reads and result-fetch retries create no
logical execution; an active/completed result is never replaced by a quota refresh.

## Structured fit results (ANY-247)

Task Finder uses the shared `ProductRunPage` with two product-owned fields and a typed result.
Its parser orders comparison deltas and criterion scores by criterion id (skills, experience,
scope, constraints), rejecting missing, duplicate or unknown ids. Array position is not a backend
contract. Score and verdict are independent indicators; the renderer shows both without reconciling
them and keeps comparison statuses separate from criterion scores. The numeric score has a native
meter as a decorative supplement; text carries the accessible meaning.

`ResultView hideText` supplies shared copy states without duplicating the structured display.
If copying fails, it reveals the copy text so the existing Select text fallback remains usable.
The default still displays text. Task Finder's copy composition is fixed English under every UI
locale, as required by its renderer contract. Empty strengths/gaps say “Not specified.” Echoed
inputs and comparison confidence never enter the frontend result model, display, copy or events.
The product has no handoff definition; Task Finder to ProposalAI remains an optional later journey.
