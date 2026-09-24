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
  `isHandoffNotActionable()` / `isHandoffAcceptanceFailed()` (reusing `isQuotaExhausted()` for the
  429 case), plus the `web-mirror` `/handoff/{handoff_token}` consent page (`HandoffConsent`) that
  renders the backend safe preview and all terminal states -- web-mirror's first real wiring to
  CE-kit. Component/browser tests cover this over Vitest + Testing Library; a real running
  dev-server route is ANY-224's job.

## Result activation and composite renderers (ANY-248)

`ProductDefinition.emitsResultViewed?(result)` is the one optional hook for a product whose
`web.result_viewed` is narrower than "any completed result". Default is true (ProposalAI and Client
Update Writer are unchanged, they activate on `copy_result`). The run still completes and renders
and `scenario_completed` still fires, carrying `resultViewed: false`; only the client-events
tracker skips `web.result_viewed`. A throwing hook counts as false. It exists because the
client-event property allowlist has no question-count property and Platform Core is not changed
for a product. Brief Decoder's `R` is a composite
object (`brief`, `issues`, `questions`, `document`) rendered by product-owned markup; only its
copy-ready `document` goes through the shared `ResultView`, using a product-side
`composeCopyText` that implements `renderer_contract.yaml`'s `canonical_field_composition`.

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
- **Selector:** one `LanguageSwitcher`, rendered by `ProductPageShell` around every registered
  product on `/products/{productId}`. A product never renders its own selector. Changing locale
  never remounts the product (no `key={locale}`), so form values, run state and the selected
  Client Update Writer mode survive.
- **Ownership:** the host owns locale resolution/persistence/provider/selector and the `host`
  namespace (generic runtime/result/error/validation copy only -- never product meaning). Each
  product owns its `product` namespace: title, field labels, validation field names, mode names,
  submit/running/failure and quota copy, supplied through `RegisteredProduct.messages`.
  `ProductDefinition` describes behavior only; it names its copy with `messageScope` and carries no
  English literals -- two optional flags, `hasDescription`/`hasStartAnother`, tell the shared
  runtime whether to look up a product's own `description` / `<messageScope>.startAnother` message,
  without the definition itself holding any text. `neutral|warm|firm` tone labels are product
  vocabulary (a product-owned wire enum's visible labels), never host's: Client Update Writer's
  shared `ToneSelect` reads them from `products/shared/toneMessages/` (one translation per locale,
  spread into its own `product` namespace so a product with a differently-meaning `tone`-shaped enum
  needs no host change); ProposalAI instead defines its own descriptive `toneOptions` labels
  ("Warm & personable" etc.) in its own messages and does not use `ToneSelect` at all -- the shared
  bundle is an opt-in convenience for products that want the same plain wording, not a contract every
  `tone`-shaped product must join.
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

1. Create `products/<name>/messages/en.ts` (English is the semantic source: `title`,
   `quotaRemaining` with `{remaining}`/`{limit}`, per-scope `submit`/`running`/`runFailed`, `fields`,
   `fieldNames`, and any product validation keys). Want a description under the title, or a
   "run again" action after a completed run? Add `description` / `<messageScope>.startAnother` here
   and set `hasDescription`/`hasStartAnother: true` on the `ProductDefinition` -- both optional, the
   shared runtime only looks them up when the flag is set.
2. Add `fr it de es ru pt` files typed `Shape<typeof en>`; use the typographic apostrophe `’` (a
   plain `'` before `{` starts ICU quoting); keep placeholders and plural categories. Reusing
   `ToneSelect`? Spread `TONE_MESSAGES[locale]` from `products/shared/toneMessages/` under a `tone`
   key in each locale file instead of retranslating `neutral|warm|firm`.
3. Export `Record<Locale, Shape<typeof en>>` from `messages/index.ts`.
4. Register the product with `messages` in `products/registry.ts`. The page shell supplies the
   provider and language selector; the completeness tests cover the new product automatically.
5. In the product, read text with `useProductT()`, render field errors with `FieldErrorMessage`, and
   set `messageScope` on each `ProductDefinition`. Never read the UI locale in `toInput`.

### Recipe: add a locale

1. Add it to `LOCALE_NAMES` in `i18n/locales.ts` (endonym).
2. TypeScript then requires an entry in `HOST_MESSAGES`, `TONE_MESSAGES` and every product's
   messages record: add `i18n/messages/<code>.ts`, `products/shared/toneMessages/<code>.ts` and
   `products/*/messages/<code>.ts`, typed `Shape<typeof en>`.
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
- `429` with `quota_exhausted` when the backend rejects a scenario start because quota is exhausted.

Recommended frontend behavior for `429 quota_exhausted`:

- keep quota state advisory in the frontend and treat the backend response as authoritative;
- disable the run action or show a clear quota-exhausted state after the response;
- do not show a progress row, job, or partial session for the rejected attempt because the backend
  creates none.

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

The canonical-artifact guard (job/workflow/schema consistency + schema re-validation) is shared with
the handoff payload builder (see `handoff-model.md`) through
`anytoolai_platform_core.artifacts.canonical.resolve_canonical_workflow_result`, so both consumers
reject the same non-canonical states identically.

## A17 public handoff contract

The backend now provides `POST /v1/handoffs`, token-based preview, accept, and decline endpoints.
The create response is the only response containing the opaque plaintext token. Frontends must
treat it as a short-lived bearer capability, avoid analytics/logging/storage beyond the consent
navigation need, and never derive or inspect its contents.

The unexpired preview response contains only display-safe product/scenario identity, status,
expiry, bounded config-mapped preview data, and nullable target session/job ids. It never contains
hidden target context, source artifact/session/job identifiers, token hashes, artifact metadata,
prompts, providers/models, or debug data. After token TTL, preview content and linked target
identifiers are redacted even when the durable handoff remains in a terminal accepted, consumed,
declined, or failed state. The backend remains authoritative for expiry and terminal status.

Accept creates and links the target session. An immediate definition may return a target job; a
deferred definition returns a retrievable `waiting_for_user/handoff_ready` target session with
`job_id: null`. Frontends must not start or fabricate a target workflow merely because the user
accepted; start policy belongs to the config contract and backend.
