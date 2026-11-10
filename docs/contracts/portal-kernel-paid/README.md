# ANY-766 paid integration target contracts

Status: **protocol specifications and fixtures**, formalized 2026-11-09.
Server implementation through ANY-766 Step 7 includes delegated identity,
snapshot V2, coherent paid admission/ownership/events and Portal invalidation
delivery. Step 8 implements recoverable paid browser journeys; usage/exhaustion
and cabinet integration remain pending. Paired local acceptance is Step 11; remote/live acceptance and
production rollout belong to ANY-767. All quantities and
credential-shaped strings in fixtures are synthetic. Q=1 is an isolated test
quantity, never a commercial offer or approval.

Authority: Portal's ADR 0005, the dated ANY-766 sections in the canonical
external-billing and Portal–Kernel access designs, and the synchronized
ANY-766 implementation plan. The 2026-11-09 scope clarification leaves ANY-711
Done for manifest/TEST-ONLY delivery; ANY-766 owns selected production
declarations and scenario bindings. Commercial quantities, LBX associations and
sales enablement still require their separate owner inputs.

## Inventory and ownership

`contract-index.json` records target routes, payload/schema owners, permissions
and statuses. `schemas/` contains reviewed JSON Schema 2020-12 documents.
`SHA256SUMS` covers every schema, fixture file and the index, using exact bytes.
Both repositories retain identical copies; neither imports the other's code.

Portal owns snapshot V2, invalidation V1, delegation issuance/exchange/
introspection responses and all identity request contracts, including the request
forwarded by Kernel, and the cabinet response. Kernel owns usage request
normalization/response and exhaustion V1. Manifest V1
remains in its existing ANY-711 contract directory, with unchanged pins and
TEST-ONLY history. No shared runtime package is introduced.

The bundle uses `*-v1` names to identify request contracts even when their JSON
body has no `schema_version`: code issuance, exchange and introspection requests
and the code response have exactly the fields specified below. Every versioned
document requires the exact integer schema version; bool/float versions fail.
Unknown fields fail validation. This is a new target, not a V1 snapshot adapter.

## Service requests and identity

The directional credentials remain independent:

- Portal → Kernel sends `KERNEL_SERVICE_TOKEN`; Kernel receives current/previous
  `ANYTOOLAI_PORTAL_SERVICE_TOKEN` slots. Receiver permissions are `manifest:read`,
  `access:invalidate` and `usage:read` for their respective operations.
- Kernel → Portal sends `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`; Portal receives
  current/previous `KERNEL_ACCESS_SERVICE_TOKEN` slots. Receiver permissions are
  `access-snapshot:read`, `kernel-session:exchange`, `kernel-session:introspect`
  and `allowance-exhaustion:write`.

Possession of one permission grants none of the others. Scope comes from trusted
receiver configuration. Requests only narrow that authority. Canonical Portal
UUIDs identify users; no Kernel-local mapping or body claim grants ownership.
The schemas permit other tenant/region strings for reuse; consumers compare the
entire requested scope/owner tuple before accepting any response.

Internal receivers require exactly one Bearer header, verified TLS, no browser
`Origin`, no public CORS and `Cache-Control: no-store` on success/refusal. Invalid
service auth is `401` with a Bearer challenge; authenticated permission/scope
refusal is `403`; malformed payload/unsupported schema is `422`; dependency
unavailability is `503`. Reuse the existing rotation window and safe service
error envelopes. User credentials grant no service permissions. Secret request
bodies, codes, tokens and headers must never enter logs or telemetry.

## Snapshot V2 and invalidation V1

Portal serves `GET /internal/v1/access-snapshots/{user_id}` with exactly one
`tenant_id` and `region` query parameter. `snapshot-v2` requires:

```text
schema_version=2, tenant_id, region, user_id, access_revision,
refresh_after, expires_at, grants[], allowances[]
grant: product_id, valid_until (nullable conservative UTC)
allowance: allowance_id, product_id, metric_key, unit, quantity
```

No provider calendar, `period_start`, `period_end` or `authoritative_as_of` is
exported. Snapshot membership authorizes the immutable scoped tuple
`tenant/region/user/allowance/product/metric/unit/quantity`. Calendar proof and
independently proven UTC bounds stay inside Portal. A proven future start is
not exposed early; the existing authoritative reconciler runs at that boundary.
Local time cannot manufacture a positive grant or next cycle.

Quantities and counters are strict JSON integers in `0…2^53−1`. Grant product IDs
and allowance IDs are unique; each allowance has a product grant. Revision zero
has empty arrays and is read-only for a known user without a committed change.
A later empty set has positive revision. A revision freezes semantic contents;
only refresh/expiry metadata can change without a new revision/outbox commit.
Duplicate distinct allowance IDs for a product/metric are a metric-local
admission conflict, never stacked; unrelated metrics remain usable.

With Portal DB time T and local/staging budget B=5 seconds:

```text
expires_at = min(T+300s, included effective source/grant/proven UTC deadlines) - B
refresh_after = min(T+60s, expires_at)
```

With no included facts, use only T+300s. Subtract B once from each raw bound in
this minimum; already conservative wire grant bounds must not receive a second
haircut. Portal preserves separate existing LBX conservatism. A deployment must
support B; fixture math is no proof of production clock synchronization. Source
trust remains at most six hours. GET performs no state writes or peer/source
calls; overdue local reductions or no currently valid complete document return
`503`. `200` includes empty states; `404` means unknown scoped user only.

Kernel refreshes on requests. A valid cached document survives a refresh failure
only within its existing expiry, durable floor and every admission predicate.
Expired authority is never extended. Service `401/403` and unexpected `404` are
integration failures, never empty entitlements. No fleet poller or V1 translation
is added. Install compatible consumers before connecting the V2 producer.

Portal sends `invalidation-v1` to Kernel
`POST /internal/v1/access-invalidations`. Kernel atomically raises its durable
floor and evicts lower cached revisions before returning `204`; repeated/lower
revisions also return `204`. Cache eviction never deletes the floor or usage.
Sender captures N before HTTP and acknowledges only N monotonically. Pending
N+1 and newer queue generations survive that acknowledgement. Reuse the existing
Portal outbox, BillingWorkItem claims and embedded worker with a bounded lane,
User → outbox → queue lock order, HTTP outside locks, restart repair and the
privileged inspect/retry CLI. Retry transport/429/5xx with bounded backoff;
permanent auth/schema/scope failures remain parked durably with alerts.

## Delegation and browser continuation

Kernel `/portal-session/launch` creates state, S256 verifier and a validated
local product/result/handoff return target in tab `sessionStorage`. Portal's
localized `/[locale]/kernel/authorize` uses the existing Portal session and the
fixed Kernel `/portal-session/callback`; no caller-selected external callback.

- `POST /api/kernel-session-codes` uses the Portal bearer and
  `code-request-v1`: `code_challenge`, `code_challenge_method="S256"`. Its
  `code-response-v1` contains `code`, `expires_at`. Code is 32 random bytes
  encoded as unpadded base64url (43 characters), with a 60-second TTL.
- The callback receives code/state only in the fragment, immediately clears it,
  validates tab state and calls Kernel `POST /v1/portal-session/exchange` with
  `exchange-request-v1`: `code`, `code_verifier` (RFC 7636, 43–128 characters).
- Kernel calls Portal `POST /internal/v1/kernel-sessions/exchange` with that
  same request under reverse-direction service authentication. Atomic exchange
  consumes the code once and verifies PKCE. `exchange-response-v1` contains
  `schema_version=1`, `access_token`, `token_type="Bearer"`, canonical
  `tenant_id/region/user_id` and `expires_at`. No refresh token exists.
- Every protected Kernel request calls Portal
  `POST /internal/v1/kernel-sessions/introspect`. `introspection-request-v1`
  places `access_token` in the secret body; Authorization carries the service
  credential. Verify token audience, active user and parent session.
  `introspection-response-v1` contains version 1, canonical owner and UTC
  `valid_until`, with B removed. No PII or browser-selected audience is returned.

Delegated expiry is the earlier of issuance+30 minutes and parent expiry.
Invalid/expired/revoked identity returns `401`; distinguish safe codes
`kernel_delegation_expired` and `kernel_parent_authority_invalid` so ordinary
expiry permits same-owner recovery while proven parent revocation clears private
recovery state. Dependency failures preserve the descriptor for retry. Invalid code/PKCE uses
`kernel_session_code_invalid`; dependency failure is `503`, never guest fallback.
Portal stores hashes in one `kernel_session_delegations` table linked to
AuthSession with cascading deletion and User → AuthSession → delegation locks.
Internal identity reads do not commit session bookkeeping.

Keep the delegated token/owner in tab sessionStorage and the original bearer
only at Portal. Before a new paid send, durably store a versioned CE-kit prepared
start descriptor with original key, frozen request and canonical owner. Storage
failure refuses the new send but permits existing result reads. On an accepted
response, replace the pending descriptor with the session reference and delete
frozen input. If that post-acceptance storage update fails, preserve the accepted
response; any retained pending descriptor remains owner-bound and replays the
original request/key until replacement succeeds or private state is cleared.
This failure never permits a new logical start. Uncertainty/reload/ordinary
expiry reuses the same key/request after same-owner reauthorization. Owner change,
logout or parent revocation clears token, pending input and private display;
ignore old-generation responses. Rebuild the API client on generation change,
preserve it across ordinary remounts and restore product/result/handoff return
targets without creating a new start or guest.

## Paid admission, ownership and client events

One PostgreSQL coherence row per scoped user serializes floor/cache installation,
invalidation and new admission. Authenticate → owner/hash replay → HTTP refresh
outside SQL → lock coherence → repeat replay → resolve scenario-owned metric and
exact allowance → ANY-507 in caller's Session → after bucket/reservation waits,
resample DB wall time and recheck identity expiry, floor/revision, snapshot expiry
and grant → atomic commit, or rollback all acceptance writes. Allowance/revision
never enters replay meaning. Frozen tuple conflicts never reset history.

Protect starts, all handoff operations, polling, next-actions, result/artifact
reads and client events. Use reservation ownership or server-written deferred
handoff ownership, never historical body `user_id`. Valid identity can read owned
accepted results after grants expire. In-flight checked requests may finish;
accepted jobs finalize against the original bucket after revocation/rollover.
Late handoff authority/dependency refusal escapes the acceptance transaction,
rolls back target/reservation linkage and leaves retryable consent unfailed.

Extend existing ClientEventService with trusted paid owner and scenario ownership;
derive user_id, permit pre-scenario product events, retain guest validation and
event-id deduplication. Events remain observational: no access, finalization or
debit authority.

## Usage, exhaustion and cabinet

Kernel `GET /internal/v1/usage/{user_id}` takes tenant/region and repeated
`allowance_id` parameters: 1–100 distinct canonical UUIDs. Repeating an ID,
malformed IDs, extra/ambiguous scope or excessive counts returns `422`.
`usage-query-v1` describes the normalized path/query input (`allowance_ids` is
an array in the test representation, never a GET JSON body).

`usage-response-v1` returns version 1, canonical owner and `items` in exact request
order, one per requested ID. Observed items contain the complete allowance tuple,
status, successful_used, reserved, remaining, available and UTC read_at.
Unobserved items contain only allowance_id/status. Unknown and foreign buckets
are indistinguishable. Rows come from a single existing repository/readback row
snapshot; errors are `503`, never manufactured zeros. Reads create no rows;
snapshot ingestion establishes zero-use buckets via existing `ensure_usage`.

```text
remaining = max(quantity - successful_used, 0)
available = max(quantity - successful_used - reserved, 0)
```

Paid successful_used+reserved cannot exceed Q. Busy reserve has available=0 but
remaining>0; final exhaustion means successful_used reaches Q. Public
`GET /v1/products/{product_id}/paid-usage?allowance_id=...` uses the same response,
introspected owner and product restriction. Historical reads need no current
sales flag. Consumers check scope/owner, exact IDs/order and observed tuples;
shape alone cannot prove those contextual predicates.

Kernel emits `exhaustion-v1` only on `became_exhausted`: version 1,
event_type=allowance_exhausted, canonical owner and allowance tuple, UTC occurred_at.
Persist an immutable leased outbox event in the SAME successful finalization
transaction, including rollback recovery. Identity is scoped user + allowance ID
+ event type. The existing worker sends outside SQL, acknowledges only its live
claim and independently bounds delivery. Retry transport/429/5xx; park permanent
faults with diagnostics.

Portal `POST /internal/v1/allowance-exhaustions` compares the complete immutable
issued tuple, inserts one `allowance_exhaustion` work item with immutable payload
and unique coalescing key, then returns `204` after durable commit. Identical
duplicate/historical deliveries also return `204`; completed duplicate hints
never revive. Unknown/mismatched tuples return `409`, malformed input `422`.
Current hints may request existing GET-only reconciliation. Old-cycle hints
complete without altering the new cycle. No financial action, grant revocation,
subscription termination, quota refill or Portal counter is authorized.

Portal `GET /api/paid-usage` requires the existing active verified-email billing
session. Derive scope/user and current production IDs locally, falling back to
the latest issued allowance per product when none is current. Use independent
bounded Kernel HTTP resources outside DB transactions; preserve `/api/paid-access`
reserved DB/thread/cancellation capacity. Validate remote tuples, then reread
local access revision; change returns `503 paid_usage_state_changed`.
`cabinet-usage-v1` records local terms, current/historical classification and
observed/unobserved/unavailable variants. Unknown/unavailable items omit counters;
tuple mismatch makes that item unavailable with safe diagnostics; dependency
outage is `503`. No-store applies to success/refusal. The future runtime API must
generate named Pydantic/OpenAPI/TypeScript DTOs through Portal's existing tooling;
this target schema creates no frontend type authority or generated API change.

## Verification boundaries

`fixtures/valid.json` and `invalid.json` cover every schema, unsupported versions,
strict integer limits, calendar-field refusal, UTC/shape errors and all usage
variants. `contextual-invalid.json` keeps valid shapes with wrong owner/IDs/order.
`protocol-vectors.json` specifies clock arithmetic, exact-N ACK and full-tuple
exhaustion duplicate/historical/mismatch outcomes. These are offline contract
examples, not database durability, security, browser or two-service proofs.

Portal tests use an independent test-only Pydantic oracle and compare its resolved
shape, including timestamp patterns, with the reviewed schemas. Every timestamp
checks the raw UTC RFC3339 string before datetime conversion; epoch strings are
not alternate wire encodings. The REV-1 regression fixtures cover all timestamp
positions, including nullable grant deadlines and nested usage/cabinet read times.
Kernel uses JSON Schema with strict integer
types and independent semantic checks; it also verifies compatibility with
ANY-507 PaidAllowance/readback. Each repository checks byte inventory/hashes.
Neither validator is used by runtime code. Run the focused commands in Step 1
of the plan and compare both bundle directories before handoff. Offline fixture
checks validate the protocol only. Runtime durability/concurrency checks belong
to their implementation steps; assembled local HTTP/browser acceptance is
Step 11, and remote/live acceptance belongs to ANY-767.

## Step 4 server implementation

The schemas/fixtures above remain the normative protocol bundle. ANY-766 Step 4
implements only the identity server slice: Portal code issuance, internal
exchange/introspection, Kernel public exchange and the reusable Kernel identity
dependency. Step 5 adds snapshot V2 serving, Step 6 attaches identity to paid
runtime ownership/admission, and Step 7 delivers invalidations. Browser
launch/callback/storage is implemented in Step 8 below; usage/exhaustion remains Step 9.
The original Portal bearer is not sent to Portal's internal service
endpoints or forwarded by Kernel.

Portal settings (server environment only):

- `KERNEL_ACCESS_SERVICE_TOKEN`, optional `KERNEL_ACCESS_SERVICE_TOKEN_PREVIOUS`:
  independent reverse-direction secrets, with the existing 32–256 Bearer-safe
  character syntax. Orphaned/equal previous slots and equality with the opposite
  direction's `KERNEL_SERVICE_TOKEN` fail validation.
- `KERNEL_ACCESS_PERMISSIONS`: explicit comma-separated receiver grants from
  `kernel-session:exchange,kernel-session:introspect,access-snapshot:read`.
  The default is empty; configuring a token alone grants none of them.
  The target exhaustion receiver remains unimplemented.
- Existing `PAID_ACCESS_CLOCK_SKEW_SECONDS` is required by introspection; the
  selected local/staging value is 5. Missing clock configuration returns `503`.
  Supporting that clock budget in a deployed environment remains an operator gate.

Kernel settings (server environment only):

- `ANYTOOLAI_PORTAL_BASE_URL`: Portal origin, required together with
  `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`. HTTPS is mandatory except loopback
  HTTP in `dev`/`test`; credentials, paths, query and fragment are rejected.
- `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`: matches a Portal receiver slot and
  differs from both opposite-direction receiver slots. Rotation switches this
  sender only after Portal accepts current and previous slots; remove the
  previous Portal slot after verifying the new sender. At most two receiver
  credentials are accepted, with no automatic overlap expiry.

The stored audience is the fixed `platform-kernel`, never a caller parameter.
Code/token hashes are linked to the existing session with cascading deletion.
Security writes lock User → AuthSession → delegation and recheck authority after
waiting. Introspection is one joined read without bookkeeping or commit. Logout,
password reset, inactive users and parent expiry/deletion invalidate delegation.
Unknown/deleted credentials use `kernel_parent_authority_invalid`; proven token
expiry uses `kernel_delegation_expired`. Invalid/used code, verifier or audience
at exchange uses `kernel_session_code_invalid`. Internal receivers reject Origin
before CORS and use exactly one authenticated service Bearer, explicit operation
permission and trusted scope. Payload validation refuses unknown fields and
returns a redacted `422`. All identity responses/refusals use no-store.

Kernel validates independent version/scope/UUID/UTC/deadline contracts and
returns the existing Core Portal-user owner. Each protected dependency invocation
performs introspection; it has no identity cache or guest fallback. The adapter
uses verified TLS, a two-second socket timeout, a 16 KiB response limit and no
redirects, environment proxy or automatic exchange retry. Its TTL sanity bound
allows the selected five-second interservice clock budget without extending a
returned deadline. Transport, malformed-response and service-auth failures are
safe `503`; only allowlisted identity `401` codes are relayed. A response that
expires in transit is refused as ordinary delegation expiry.

Local tests use SQLite, disposable PostgreSQL and intercepted Kernel HTTP.
They do not prove real paired HTTP, browser recovery, sales or deployment.


## Step 6 server implementation

Kernel consumes snapshot V2 with strict version, UTC, integer and contextual
scope checks. Requests use the existing reverse-direction credential, verified
TLS, a two-second timeout, a 256 KiB response bound and no redirects/environment
proxies. Valid finite cached authority may survive refresh failure; it cannot
cross its original expiry or durable revision floor.

Migration `0019` and Core's coherence repository serialize installation,
invalidation and new admission. The API reuses ANY-507 reservations, replay and
original-bucket finalization. Reservation/deferred ownership protects every paid
runtime surface; the existing client-event service supports trusted paid owners
without granting access or charging usage.

`POST /internal/v1/access-invalidations` is implemented. Its receiver-owned
`access:invalidate` permission requires explicit trusted
`ANYTOOLAI_PORTAL_ACCESS_INVALIDATION_ENABLED=true`; default is false, retaining
manifest-only authority. Current/previous Portal service tokens share this
configured permission and trusted scope. The receiver returns `204` only after
floor/eviction commit, including repeated/lower revisions. Portal Step 7 now
delivers invalidations through its embedded worker. The sender starts with the
existing manifest URL/token when that worker is enabled, so configure this
receiver permission first. The usage API and exhaustion delivery remain Step 9.

Focused evidence uses real disposable PostgreSQL and in-process ASGI with
synthetic Portal responses. It does not establish real paired HTTP, browser,
clock/TLS deployment, live LBX, sales enablement or staging acceptance.


## Step 8 browser implementation

The localized Portal authorization page reuses the existing account/session UI
and generated `KernelCodeRequest`/`KernelCodeResponse` adapter. A confirmed
cabinet grant exposes the existing Kernel product through its launch route.
Configure Portal `NEXT_PUBLIC_KERNEL_WEB_BASE_URL` with the Kernel **web** base
URL (including its optional base path), separately from server-only
`KERNEL_BASE_URL` and service credentials. Configure Kernel web
`NEXT_PUBLIC_PORTAL_AUTHORIZE_URL` with a supported localized Portal route, e.g.
`https://portal.example/ru/kernel/authorize`. Both are frontend build inputs;
HTTPS is required except for loopback development. Kernel's existing
`ANYTOOLAI_WEB_BASE_PATH` remains the source of its web base path. No endpoint,
service permission, migration, product placement or sales gate changes here.

Kernel's launch/callback pages use secure-context Web Crypto S256, unpredictable
state and tab `sessionStorage`. Only registered product pages, their
`?session=<id>&scenario=<scenario_id>&paid=1` result continuations and handoff pages
are allowed. Paid result/handoff links carry the non-secret `paid=1` marker so
a fresh tab requires authorization before mounting a product or creating any guest.
Reauthorization keeps handoff continuations in tab storage instead
of placing their capability token in a query. Portal always selects the
configured fixed callback; code/state arrive in its fragment, which Kernel
clears before any asynchronous operation. A lost one-use exchange starts a new
authorization while preserving the original operation, rather than guessing an
exchange outcome or creating a guest.

CE-kit extends `prepareScenarioStart` with a version-1 canonical-owner-bound
recovery descriptor. Before any new paid send, the original key and frozen
request must be written and read back successfully. An accepted response replaces
that input with its session/scenario reference; a lost response replays the
original key/body. If storage becomes unavailable **after** acceptance, the
already accepted result still opens; any retained pending descriptor replays its
original key on reload. This is the recovery path for that browser-storage
failure, not a second execution. Existing explicit result reads remain usable
when new-start storage is refused.

The shared web runtime restores every selected scenario/mode, attaches accepted
sessions, uses the existing paid client-event transport and reuses backend-owned
handoff consent. Paid mode creates no guest and makes no guest quota read.
The browser client survives ordinary remounts and is replaced on identity
changes; obsolete generations cannot send, persist, display or navigate from a
late response. Ordinary delegation expiry preserves owner-bound recovery.
Different owner, explicit tab sign-out or observed parent-authority revocation
clears token, pending inputs, attach/event marks and displayed private state.
Portal logout revokes the parent on the server; Kernel observes that revocation
on its next protected request. Tab sign-out clears this Kernel tab and does not
log out the Portal parent. Paid mode remains explicit during reauthorization.

History restoration and focus reconcile the cached document with the current
tab identity; paid-client generation checks repeat that comparison before sends,
persistence and response use. Authorization launch and code exchange also reconcile
custody, including after the exchange await and before installing its session.
Callback pages reconcile on history restoration and focus. The tab's version-1
mode record includes a fresh `custodyId` for each authorization transition and
session installation. Comparing this persisted epoch detects an intervening login
and logout even when owner/token fields return to their original values. PKCE
context is bound to the launch epoch; obsolete callbacks are refused before
exchange as well as after its await. A suspended PKCE computation cannot replace
a newer authorization record or redirect its older launch. Legacy custody or
PKCE records without an epoch require reauthorization, preserving owner-bound
paid recovery. Custody/session writes must read back successfully; failed writes
cannot authorize a new client. A different stored epoch/token/owner invalidates
the old client without deleting a newer document's recovery.
Result-link session/scenario parameters are consumed together and remain paired
for the current visit.
On reload, pending or accepted paid recovery supersedes an older remembered
handoff attachment; an explicitly opened result retains precedence for that visit.
Selecting a result through a deep link or handoff consent preserves an existing
pending descriptor, including its original key and frozen request. Ending or failing
that selected result does not clear another operation. A new form submission cannot
replace the saved pending operation; the retry action reloads the page to resume it.
CE-kit rereads the current descriptor immediately before every pending write/send,
including retries from a restored document. A different unresolved key or changed
frozen request is refused locally. Acceptance replaces only its matching pending
key; a late accepted response cannot replace a newer pending. Prepared handles
forget only their own pending key or known accepted session. An attached result
can clear only its own accepted reference. A definitive rejection with no earlier
uncertain send releases its persisted descriptor; the in-memory handle still reuses
the same key for unchanged retries, while edits or another mode can use a new key. Superseding the old attachment preserves any newer handoff fallback.

Step 8 evidence is local component/transport testing and synthetic browser UI
coverage, distinct from the real two-service HTTP/PostgreSQL/browser acceptance
required by Step 11. Usage/exhaustion and cabinet counters remain Steps 9–10;
remote/live-service acceptance remains ANY-767.
