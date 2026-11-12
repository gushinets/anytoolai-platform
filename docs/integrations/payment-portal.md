# Payment Portal integration map

Status: navigation, implementation snapshots and the ANY-711 service-authentication handoff.
Last observed: 2026-11-12; local source state, not a deployment check.

## Ownership and sources

This repository is Platform Kernel: product/scenario execution, artifacts,
technical product/metric vocabulary and runtime usage/quota enforcement.
[Payment Portal](https://github.com/gushinets/payments-portal) owns identity,
sessions, legal acceptance, public discovery and the cabinet. It also
owns commercial-to-technical mappings, paid grants/allowances, access revisions
and delivery. External Billing owns commercial billing truth and lifecycle.

Start with the peer's current [AGENTS](https://github.com/gushinets/payments-portal/blob/main/AGENTS.md)
and [architecture](https://github.com/gushinets/payments-portal/blob/main/ARCHITECTURE.md).
The target authority chain is:

1. [ADR 0005](https://github.com/gushinets/payments-portal/blob/main/docs/architecture/decisions/0005-external-billing-boundary.md).
2. [External Billing Boundary Design](https://github.com/gushinets/payments-portal/blob/main/docs/superpowers/specs/2026-09-15-external-billing-boundary-design.md).
3. [Portal-Kernel Access Contract Design](https://github.com/gushinets/payments-portal/blob/main/docs/superpowers/specs/2026-09-15-portal-kernel-access-contract-design.md).
4. [Accepted live-source amendment](https://github.com/gushinets/payments-portal/blob/main/docs/superpowers/specs/2026-10-15-live-source-commercial-admission-design-amendment.md),
   narrowly superseding source-catalog mirroring/new-sale TTL only.

The service-authentication convention below records ANY-711's concrete handoff within
these contracts. Payload semantics and MVP scope remain owned by the sources above and
[MVP scope](../product-specs/mvp-scope-source-of-truth.md),
[platform boundaries](../architecture/platform-boundaries.md),
[guest quotas](../architecture/quota-model.md) and
[frontend boundaries](../architecture/frontend-boundaries.md).
Historical Portal contracts and execution plans do not override accepted sources.

## Current local implementation

Current source baselines: Kernel `82f1b155b5d9fbc9af8e5b6bd51364d640434495`
and Portal `c41428de013e69c982386acbb9edda05e1dc9014`, plus the local PR correction
diff. The dated checkpoints below retain historical evidence, not current setup
instructions. The corrected pair covers the complete policy digest, saved grant
ownership without allowances, inactive delivery scheduling, frontend/API consumer
alignment and web-update ingress retention; focused local acceptance passed.
The [active plan](../exec-plans/active/ANY-766-implementation-plan.md) owns the
current scope and remaining gates.

- Manifest V1 is implemented in Kernel and consumed by Portal.
- Portal serves common consumer-bound identity V2 with configured callbacks,
  a persisted policy guard and documented generated security. Kernel validates
  consumer/P on every introspection and retains Core owners/replay semantics.
- Step 12 serves/consumes consumer-filtered V3 with durable consumer/P/R
  coherence, populated migration `0020` and unchanged ANY-507 buckets/replay;
  Portal Step 11 now routes configured technical sources and preserves immutable
  source/owner history; Step 13 now partitions Portal delivery by recipient.
- Kernel's durable invalidation receiver and Portal's bounded embedded sender
  are implemented. Configure matching scope/service tokens and enable
  `ANYTOOLAI_PORTAL_ACCESS_INVALIDATION_ENABLED` at Kernel before starting the updated Portal
  worker. Portal's Step 13 sender selects each snapshot recipient's origin and
  outgoing service key from `BACKEND_CONSUMERS`, with independent bounded lanes.
  Stop affected APIs/workers before migrating the Step 14 pair to Portal
  `20261111_0011` and Kernel `0021`. The historical Step 13 heads were Portal
  `20261111_0010` and Kernel `0020`. Legacy Kernel connection settings no longer
  select delivery destinations. A disabled receiver permission parks delivery with `403`;
  operator retry is required after repair. This differs from an inactive Portal
  registry recipient, whose history is retained without new scheduling. The
  [current cutover](../../infra/deployment/README.md#reviewed-images-and-independent-updates-any-766-step-17)
  also requires a higher P when installing the expanded digest, despite unchanged heads.
- Step 8 implements recoverable browser launch, owner-bound tab custody and
  paid runtime/event/handoff continuity. Step 14 implements usage/exhaustion;
  Step 15 implements independent current/historical cabinet usage with generated
  Portal DTOs. Steps 16/17 supply focused paired local acceptance and build/install
  preparation in the agreed scope. ANY-767 owns the full deferred matrix, remote
  deployment and live-service acceptance.

### Superseded access-check direction (ANY-286/287)

ANY-766 supersedes the earlier access-check direction tracked by ANY-286/287 for
this integration. The implemented contract uses consumer-bound delegation V2
and consumer-scoped AccessSnapshot V3 with independent policy/access revisions.
Portal owns authenticated identity and purchased grants/allowances; Kernel owns
execution admission and durable reserve/finalize/release through ANY-507. A
snapshot read supplies finite authority; reserving capacity and recording usage
belong to the backend's execution transaction. Use the
[current contract](../contracts/portal-kernel-paid/README.md) for implementation
and the [common backend guide](https://github.com/gushinets/payments-portal/blob/main/docs/contracts/product-backend-api/README.md)
for consumer onboarding. The earlier access-check direction is historical, not
an additional endpoint or metering path to implement.

## ANY-766 Step 9 common backend specification — 2026-11-10

Inspected local sources: Portal `119d3d86175f35006d2ef90259bb43e19a9ef82f`
and Kernel `6697b9f5c271eb1c77f507e037661fd92a048b74`, plus the Step 9
documentation/test-only diff. The
[Portal-owned common guide](https://github.com/gushinets/payments-portal/blob/main/docs/contracts/product-backend-api/README.md)
now specifies independent consumers, audience-bound V2 delegation, V3/P/R
snapshots, immutable source/owner history and recipient/usage routing. The
[paired bundle](../contracts/portal-kernel-paid/README.md) retains exact baseline
schemas/fixture payloads and independently checked target additions.

At this historical Step 9 checkpoint, runtime, migrations and generated OpenAPI
were unchanged (Kernel identity V1/snapshot V2). Step 10 subsequently implemented
common identity V2/security while retaining the then-current Kernel-only V2
snapshot. Step 12 now supersedes that wire with consumer-filtered V3/P/R. The guide records
actual owning modules, minimal replacements, populated-state forward migration
requirements and focused acceptance cases; active Kernel code is not a purge
target. Common identity is Step 10, technical-source ownership Step 11, working
auth/access with documented generated Swagger Step 12 (2026-11-13 priority),
recipient delivery Step 13, usage/cabinet Steps 14/15, assembled local acceptance
Step 16 and build/install preparation Step 17. Real external backend adoption
belongs to its owning team; remote/live acceptance remains ANY-767.

## Observed implementation

Historical snapshot (2026-10-23). Evidence baselines: Platform `79a2ada5b790f959a40b3e08451ef9ed8d97da5b`;
Portal `79dc3f4d204aec4ac9552e3d1da3481553cc8aef`.
These are inspected source snapshots, not deployment or conformance claims.
This and the dated checkpoints below retain their historical scope; the current
local summary above supersedes their statements about unimplemented work.

| Operation / request direction | Payload producer | Payload consumer / receiver | Verification status |
| --- | --- | --- | --- |
| `GET /internal/v1/capability-manifest`: Portal -> Kernel | Kernel endpoint not implemented | Portal typed HTTP client implemented against provisional schema and independent SIMULATED fixtures | Local mock/client CI PASS; real producer deferred |
| `GET /internal/v1/access-snapshots/{user_id}`: Kernel -> Portal | Portal paid-access producer not implemented | Kernel snapshot client/cache/revision floor not implemented | Target contract only |
| `POST /internal/v1/access-invalidations`: Portal -> Kernel | Portal invalidation producer/delivery not implemented | Kernel receiver endpoint not implemented | Target contract only |

Portal already publishes immutable `commercial_mapping_revisions` through a
restricted operator path and serves approved catalog terms from PostgreSQL.
Purchases, subscription reconciliation and paid-access derivation remain future
work at this snapshot. Browsing does not certify current sellability.

Evidence: [Kernel routes](https://github.com/gushinets/anytoolai-platform/blob/79a2ada5b790f959a40b3e08451ef9ed8d97da5b/apps/platform-api/src/anytoolai_platform_api/main.py),
[Portal publication](https://github.com/gushinets/payments-portal/blob/79dc3f4d204aec4ac9552e3d1da3481553cc8aef/apps/api/app/domains/catalog/publication.py),
[Portal product snapshot](https://github.com/gushinets/payments-portal/blob/79dc3f4d204aec4ac9552e3d1da3481553cc8aef/docs/PRODUCT.md)
and [local conformance handoff](https://github.com/gushinets/payments-portal/blob/79dc3f4d204aec4ac9552e3d1da3481553cc8aef/docs/contracts/kernel-capability-manifest/v1/step-8-handoff.md).
`LOCAL_SPEC_CONFORMANCE=PASS` is historical local CI evidence;
`REAL_KERNEL_CONFORMANCE=DEFERRED_NOT_IMPLEMENTED` remains explicit.

## ANY-711 implementation progress (2026-10-29)

Kernel now implements the private manifest endpoint with scoped Portal Bearer authentication,
rotation and browser refusal. Trusted API scope defaults to `anytoolai/ru` and is validated
against the loaded registry. All six ordinary products and both approved test metrics remain
disabled and are included in the complete response. Runtime routes use the same trusted scope;
existing working data is neither migrated nor relabelled. See the
[receiver configuration and rotation procedure](../../infra/deployment/README.md#portal-capability-manifest-receiver-any-711).

The peer was rechecked read-only at `2bb07d778edc5ea56011b0034ba24b0702ede81f`.
Its current settings support configured sources; the older production prohibition is a
historical observation, not current enablement authority. Historical simulated fixture evidence
above remains unchanged. The [Kernel-owned v1 contract](../contracts/kernel-capability-manifest/v1/README.md)
now publishes a generated serialization schema, canonical positive/negative fixtures and byte
checksums. Offline checks retain the Portal positive bytes and independent semantic version,
and compare resolved standalone/OpenAPI/Portal schema constraints.

Step 4 now proves real **local** TCP HTTP interoperability: the unchanged Portal typed client
at `2bb07d778edc5ea56011b0034ba24b0702ede81f` consumes the real Kernel router/middleware,
ordinary disabled inventory and a complete isolated test-enabled configuration. The producer
is `feature/ANY-711` at `7634eb09533846268a96ade004bca518c580b588` plus its uncommitted
Step 4 diff. Six products, both exact metric/owner/unit declarations, `anytoolai/ru`, independent
digest, auth/scope/rotation, safe failure/retry/recovery, restart/order stability and side-effect-free
concurrency pass. Poisoned-dotenv isolation, 92 unchanged Portal consumer regressions and manual
serve/probe/interrupt cleanup also pass. Portal source/artifacts remain unchanged.

See the [reproducible automated/manual procedure and evidence](../contracts/kernel-capability-manifest/v1/README.md#real-kernel--portal-http-conformance).
The harness starts no database, Portal stack, billing worker, webhook or LBX client and reads no
working `.env`. `CONFIGURED_SOURCE` describes the client source, not sales approval. This result
does not relabel the historical SIMULATED evidence above. Actual deployed TLS/private network
controls, production metric approval and paid-access/usage behavior remain separate gates.

## ANY-507 reservation lifecycle checkpoint

ANY-507 stage 2 (2026-11-04) adds Core-only reservation admission and owner-scoped replay for
ordinary start and immediate handoff. Typed `ExecutionOwner`/`PaidAllowance` arguments are supplied
explicitly by trusted internal callers; historical body/source-session `user_id` is not Portal
authority. No paid HTTP authentication, AccessSnapshot, usage endpoint or wire change is delivered
by this checkpoint. See the [shared contract and stage boundaries](../exec-plans/completed/ANY-507-implementation-plan.md).
Stage 3 adds one transactional success finalizer/release path for both typed paid and guest buckets,
shared by ordinary execution and rollback recovery. It returns an applied/replayed
`ConsumptionTransition` with the original reservation and an exhaustion edge for ANY-766's
same-transaction outbox integration. No outbox, paid HTTP or Portal contract is added here.
Stage 4 adds internal owner-scoped `ConsumptionReadback` plus guest HTTP fields and reservation-aware
client/events. Unknown buckets remain unobserved and reads never create allowances. Paid HTTP usage,
interservice delivery and exhaustion outbox remain ANY-766; no peer wire/authority contract changes.
The peer observation below belongs to stage 2; later stages do not refresh that observation.
Portal's committed architecture and access specification were rechecked read-only at
[`94ca83603c12d56e92110e0310553ba8e13af699`](https://github.com/gushinets/payments-portal/commit/94ca83603c12d56e92110e0310553ba8e13af699).
Its canonical snapshot specification remains V1 with calendar bounds. Proposed V2 and actual paid
integration remain ANY-766 work; this observation is not a final ANY-715/765 handoff or deployment
readiness claim. No peer source or producer/consumer artifact changed.

## ANY-766 target contract checkpoint — 2026-11-09

At Kernel `72ff15bc0b77903c87aa39f7b10186dccc556d09` and Portal
`7f985031034f45fde0203f710eb64283cd086e86`, Step 1 adds only the
[paired target schemas/fixtures](../contracts/portal-kernel-paid/README.md) and
updates the peer's two canonical designs. Snapshot V2 removes calendar interval
fields and freezes owner/allowance/product/metric/unit/quantity; manifest and
invalidation stay V1. Delegation/recovery, coherent paid admission/events and
usage/exhaustion/cabinet delivery are specified, not implemented. The historical
observations above are unchanged. Internal ANY-507 readback is not paid HTTP.

ANY-766 owns selected production vocabulary/scenario bindings under the
[dated scope clarification](https://linear.app/paveldik/issue/ANY-766); ANY-711
remains Done for manifest/TEST-ONLY delivery. Quantities, LBX associations and
sales approval remain separate. The target extends the credentials/receiver
permissions below without enabling routes: Portal → Kernel adds usage:read;
Kernel → Portal adds kernel-session:exchange, kernel-session:introspect and
allowance-exhaustion:write. Tests independently validate the retained copies
without a shared runtime dependency. Compatible consumers precede V2 connection.

Step 2 implements the four disabled production metric declarations and seven
product-owned `paid_metric_key` bindings described in the
[config model](../architecture/config-model.md). Core/SDK and loader reference
checks agree; current manifest inventory fixtures include all six metrics.
Historical two-metric TEST-ONLY fixtures retain their bytes and identity. The
Portal consumer retains independent current fixture copies. Sales, paid HTTP
identity/admission, usage delivery and purchased quantities remain separate work.

## ANY-766 Step 4 identity checkpoint — 2026-11-10

Peer Portal `4a34948eb02d034b46871d739bbf066ffc67d48a` and local Kernel
`89296ddce3c7b187881cb1730bf7fbacf3ffd302` were inspected, plus the paired
uncommitted Step 4 change. Portal implements one-use S256 codes, atomic exchange
and parent-bound introspection; Kernel implements public code exchange and the
reusable `authenticate_portal_user` dependency. It creates the existing Core
Portal-user `ExecutionOwner` directly from validated scope/UUID and introspects
on each invocation. It never falls back to a guest or matches a local user.

See [identity configuration and limits](../contracts/portal-kernel-paid/README.md#step-4-server-implementation).
At this checkpoint the reverse connection implemented exchange/introspection.
The current local summary above records the subsequent snapshot/admission/delivery
implementation. Local evidence here uses disposable Portal PostgreSQL and
intercepted Kernel HTTP; real paired HTTP remains Step 16. Browser custody/recovery
remains Step 8. The historical snapshots above remain historical evidence.

## Service authentication and scope convention (ANY-711 handoff)

This is the service-authentication convention for manifest, snapshot and
invalidation. ANY-711 supplied manifest read; ANY-766 Steps 4–7 implement the
reverse identity/snapshot connection and invalidation receiver/sender. The
[contract bundle](../contracts/portal-kernel-paid/README.md#service-requests-and-identity)
also documents the implemented identity, usage and exhaustion operations.
Steps 14/15 implement usage/exhaustion and cabinet composition; their receiver
permissions and delivery enablement remain explicit configuration gates.

### Credentials and operation permissions

- **Portal -> Kernel manifest:** Portal sends `portal_to_backend_current_secret`
  from the `platform-kernel` entry in `BACKEND_CONSUMERS` as
  `Authorization: Bearer <secret>`. Kernel validates against `ANYTOOLAI_PORTAL_SERVICE_TOKEN`
  and the optional `ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS` rotation slot. Its receiver-owned
  Portal principal has `PortalPermission.MANIFEST_READ` (`manifest:read`).
- **Portal -> Kernel invalidation:** reuse that same directional credential pair; no third
  secret is introduced. ANY-766 implements `PortalPermission.ACCESS_INVALIDATE` (`access:invalidate`)
  and explicitly grants it through Kernel's trusted receiver policy when invalidation is
  enabled. Possession of a manifest-only credential does not itself grant invalidation;
  requests cannot add permissions through headers, query parameters or body fields.
- **Kernel -> Portal AccessSnapshot:** use a different secret. The Kernel sender
  setting is `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`; Portal's platform-kernel
  entry in `BACKEND_CONSUMERS` accepts its independent
  `backend_to_portal_current_secret` and optional `backend_to_portal_previous_secret`.
  The trusted consumer principal requires explicit `access-snapshot:read`.
  Kernel-named Portal receiver settings were removed in Step 10; use the
  [current identity guide](https://github.com/gushinets/payments-portal/blob/main/docs/contracts/product-backend-api/README.md#implemented-step-10-settings-and-cutover). The two directional secrets must
  differ, and each environment and tenant/region connection uses independent secrets.

Configured technical-source reads, usage clients and recipient invalidation
delivery use the registry entry's outgoing key. The legacy `KERNEL_SERVICE_TOKEN`
does not select credentials for those clients.

All three operations use exactly one Bearer authorization header over TLS with certificate
verification. Tokens stay in server-side operator environments/secret stores and must not
appear in URLs, browser code, logs or committed configuration. User/guest, demo and Atom Lab
credentials grant no service authority. Use independently generated secrets with at least
32 random bytes and the existing manifest token syntax/validation rules.

### Receiver-owned scope and canonical identity

Kernel binds the Portal principal to trusted `ANYTOOLAI_TENANT_ID` / `ANYTOOLAI_REGION`.
Portal binds the Kernel principal to trusted `INSTANCE_TENANT_ID` / `INSTANCE_REGION`.
The RU connection is `anytoolai/ru`; both receiver policies must agree. Request values only
narrow the receiver's authority. They never select another region, change the principal
or establish authority from UI locale, browser input or unverified scenario metadata.

- Manifest requires one `tenant_id` and one `region` query parameter, exactly matching the
  authenticated Portal principal's configured scope, as implemented today.
- Invalidation carries `tenant_id`, `region` and canonical Portal `user_id` in its JSON body,
  using the accepted POST contract. Kernel checks the body scope against the authenticated
  Portal principal before touching the cache/revision floor and applies the hint only to
  that exact `(tenant_id, region, user_id)` key. Query parameters cannot override body scope.
- AccessSnapshot carries canonical Portal `user_id` in the path and `tenant_id` / `region`
  in query parameters. Kernel derives the UUID from the authenticated Portal identity flow;
  an unverified scenario user ID or Kernel-local ID cannot substitute for it. Portal first
  authorizes the service's tenant/region and resolves that UUID within the same scoped user
  store. Kernel accepts a response only when its full tuple matches the requested tuple.

Authenticated requests outside the configured scope or without the required operation
permission return `403`; ambiguous scope is refused. Unknown snapshot users within an
authorized scope retain the contract's `404`; known users with no paid access retain `200`
with the contract-defined empty state. Service authentication does not grant paid execution.

### Failures, browser refusal and rotation

Missing, malformed, duplicate, invalid or revoked Bearer credentials return `401` with
`WWW-Authenticate: Bearer`. Authenticate before evaluating request scope. All three receivers
reject requests carrying `Origin`, including preflight, with `403`, bypass public CORS and
apply `Cache-Control: no-store` to success and error responses. Invalid receiver configuration
fails startup or returns a safe unavailable response; it never enables anonymous access.
Retain the manifest's implemented `422` validation envelope and safe `5xx` behavior.

For each direction, use one bounded rotation window:

1. Generate a new independent secret. Put it in the receiver's current slot, move the old
   secret to that receiver's previous slot and restart/reload the receiver. Both slots bind
   to the same principal, scope and explicitly granted permissions.
2. Switch the corresponding sender setting: Portal -> Kernel updates
   `portal_to_backend_current_secret` in the `platform-kernel` entry of
   `BACKEND_CONSUMERS`; Kernel -> Portal updates
   `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`. Restart/recreate the API and worker
   processes that hold the affected outbound clients. Verify actual requests
   from each affected sender with the new token and refusal of wrong scopes/permissions.
3. Remove the receiver's previous slot, restart/reload and verify the old token returns `401`
   while the new token still succeeds. At most two distinct tokens are accepted; an orphaned
   or equal previous token is invalid. Overlap has no automatic expiry and must be removed.

Emergency revocation removes the compromised token from every receiver slot immediately;
do not retain it as a rotation overlap. Rotate each direction independently. The existing
[manifest receiver procedure](../../infra/deployment/README.md#portal-capability-manifest-receiver-any-711)
describes the Portal -> Kernel receiver. The
[current delegation/snapshot setup](../contracts/portal-kernel-paid/README.md#service-requests-and-identity)
describes the independent reverse connection.

## Dependencies before real integration

- **Identity:** canonical paid-access identity is Portal's authenticated UUID
  scoped by `(tenant_id, region, user_id)` and derived by delegated-token
  introspection on every protected request. A body `user_id` never establishes
  paid ownership. Guest identity/quota remains separate from paid allowances.
- **Scope:** [Kernel Settings](../../apps/platform-api/src/anytoolai_platform_api/settings.py)
  and [region config](../../configs/kernel/regions.yaml) now default to `anytoolai/ru`,
  matching the inspected [Portal Settings](https://github.com/gushinets/payments-portal/blob/2bb07d778edc5ea56011b0034ba24b0702ede81f/apps/api/app/core/settings.py).
  Deployment must explicitly configure matching trusted scopes under the convention above;
  the historical `anytoolai/default` snapshot does not describe current defaults. Do not
  rename existing data scopes or infer region from UI locale.
- **Producer compatibility:** each API owner supplies its implemented endpoint,
  producer-owned schema and positive/negative fixtures. Integration owners
  verify the actual local pair; deployed scope/TLS and commercial approval
  retain separate gates. No shared
  Portal/Kernel runtime package is required; platform-sdk serves product bundles.
- **Enablement:** the inspected Portal settings support a configured Kernel URL/token.
  Production enablement still requires deployed TLS/private-network verification and
  commercial approval after real conformance; a URL change is insufficient. Historical
  fixture pins and SIMULATED mapping history must not be relabelled as real.
- **Usage and launch:** the
  [target bundle](../contracts/portal-kernel-paid/README.md) specifies usage,
  exhaustion and authenticated browser launch. Step 8 implements browser launch;
  usage/exhaustion and cabinet usage are implemented in Steps 14/15. Focused paired
  local acceptance and the PR correction scenarios passed; broader and remote/live
  acceptance remain ANY-767 work. Kernel product handoff is not Portal login handoff;
  shared product IDs do not imply shared origins/routes or sessions.
- **Commercial meaning:** deployed product configuration, guest quota and the
  fixture's `proposal_ai.test_generations` do not approve paid metrics/quantity.
  Live source reads gate new publication/purchase; subscription trust and
  bounded Kernel AccessSnapshot caching retain separate policies. Invalidation
  fences revisions; it carries no grants or usage.

## Change and verification workflow

For changes to identity, scope, product/metric identity, paid access or cross-app
journeys, read the peer's current sources and record the observed SHA. Follow
the owning contract, update affected map sections, and fill PR **Peer impact**
with linked peer work or `None` and a reason. Keep source ownership explicit;
the implementing side supplies evidence and the consuming side verifies it.

Use `main` links for discovery and pinned links for observations. A stale SHA
means last observation, not proven incompatibility. Documentation-only commits
do not trigger mutual SHA bumps. If peer sources are unavailable, record that
limitation without claiming a fresh check. Use HTTPS for peer links and local
relative links within this repository; no developer-specific checkout paths.

Run `python scripts/agent/runner.py validate-docs` and the docs tests for this
map. Navigation checks do not prove semantic or runtime compatibility. Portal's
local checker remains its own CI gate. External source monitoring was removed
by the owner on 2026-10-19; paired paid-runtime and deployed acceptance retain
their current plan gates.
Read [ANY-727](https://linear.app/paveldik/issue/ANY-727) and companion
[ANY-728](https://linear.app/paveldik/issue/ANY-728) for this map's delivery work.


## ANY-766 Step 6 runtime checkpoint — 2026-11-10

The local paired Step 6 change consumes Portal's Step 5 snapshot V2 and reuses
Step 4's per-request principal introspection. Kernel migration `0019` adds durable
coherence. Installation, invalidation and new admission share its scoped-user row
lock; post-bucket-wait checks use PostgreSQL wall time. Accepted replay and owned
historical results remain independent of current grants/configuration.

The existing start/handoff/reservation path now receives the exact scenario-bound
allowance. Polling, next-actions, results, all handoff operations and existing
client events verify reservation/deferred ownership. Paid pre-scenario events
require no guest and retain event-id deduplication. A late handoff authority
refusal rolls back all acceptance effects and leaves consent retryable.

The invalidation receiver is available behind the explicit receiver permission
in the [server contract checkpoint](../contracts/portal-kernel-paid/README.md#step-6-server-implementation).
Portal Step 7 now supplies the sender. Browser integration, usage/exhaustion,
local connection/acceptance and build preparation remain Steps 8–12; remote
installation/live acceptance belong to ANY-767. Local PostgreSQL/ASGI
synthetic evidence does not supersede earlier historical or live-provider gates.


## ANY-766 Step 8 browser checkpoint — 2026-11-10

At Portal `f4f6fbf` and Kernel `729f0675` plus the paired Step 8 changes,
CE-kit and the existing web host implement fixed PKCE launch, canonical-owner
tab custody, frozen same-key replay, accepted-session/mode restoration and
identity-generation guards for paid events/results/handoffs without guest
fallback. See [browser configuration and limits](../contracts/portal-kernel-paid/README.md#step-8-browser-implementation).
Local component/synthetic browser evidence does not establish the real paired
HTTP/PostgreSQL acceptance required in Step 16. Historical snapshots above are
unchanged; usage/exhaustion and delivery/build gates retain their owning steps.


## ANY-766 Step 10 consumer identity checkpoint — 2026-11-11

Inspected peer: Portal `f6c5e2543a7c281bf3a0e26a0ad9af64372f651b`, plus this paired Step 10 working-tree change.
Portal now serves common backend-session code/exchange/introspection endpoints
with consumer-bound V2 identity, independent credentials/permissions, monotonic
persisted policy guard and generated named Bearer security. Kernel validates
consumer/P and keeps per-request introspection and the original Core owner/replay
partition. The localized authorization page resolves configured fixed callbacks.
Version-1 browser token envelopes require authorization while separate same-owner
pending requests retain their exact request/key. See the
[common configuration/cutover guide](https://github.com/gushinets/payments-portal/blob/main/docs/contracts/product-backend-api/README.md#implemented-step-10-settings-and-cutover).

Portal migration 20261111_0009 preserves populated delegation parent links,
hashes, TTLs and single-use state while binding historical audience to Kernel.
Step 10 needs no Kernel migration or usage reset. Snapshot remains Kernel-only
V2; another consumer cannot read that unfiltered baseline. At this Step 10
checkpoint, source routing and recipient delivery remained Steps 11/13.
The Step 11 checkpoint below supersedes source selection; V3/filtering/coherence
and recipient delivery remain Steps 12/13.
Local synthetic/API/component and disposable PostgreSQL checks are distinct from
Step 16's assembled real HTTP acceptance and ANY-767 remote/live acceptance.


## ANY-766 Step 11 Portal technical-source checkpoint — 2026-11-11

Inspected Portal base `b346f0e90c9745f942847734bc06d0d3f5b0a73d` and
Kernel `192f4cb2ebf19a697f9fb1298147d26221a0a6a0`, plus the Portal Step 11 diff.
Portal selects each configured product's manifest origin and independent
outbound credential through the existing V1 client/validator. New metered
links/terms/purchases bind technical source and sole backend owner; historical
Kernel JSON/digests and allowance identities remain unchanged. The Kernel
manifest producer, scenarios, ANY-507 execution and usage require no changes.
See the [source/history guide](https://github.com/gushinets/payments-portal/blob/main/docs/contracts/product-backend-api/README.md#implemented-step-11-technical-sources-and-history).
This is synthetic HTTP/disposable PostgreSQL evidence; the real external product
is not registered or tested. Snapshot V3, recipients and usage remain later work.


## ANY-766 Step 12 auth/access checkpoint — 2026-11-11

Peer inspected: Portal `1caa078418ffb07781467dcb4f62158f17e029a3`, plus the paired Step 12 working diff.
Portal now serves consumer-filtered V3, selecting products before provenance and
deadline/completeness checks; its cabinet/writer retain whole-user rules. Kernel
migration `0020` preserves R, usage, active reservations and replay while binding
old coherence rows to platform-kernel/P1 and evicting incompatible V2 cache
metadata. Independent durable policy/access floors fence stale response/admission;
P changes do not require a paid R transition. The Portal-owned common API guide
and generated OpenAPI/Swagger document actual identity V2/access V3 security,
schemas, examples, errors, cutover and backend enforcement duties.
Focused real PostgreSQL and local TCP auth/access evidence is separate from the
Step 16 assembled browser/execution journey. The second identity and external
LBX/manifest sources are synthetic; generic recipients/usage remain Steps 13–15.
No real third-party, live payment or deployed acceptance is claimed.


## ANY-766 Step 14 — usage and exhaustion

Kernel now serves authenticated internal and delegated-user product usage V1,
using actual ANY-507 counters and indistinguishable unknown/foreign results.
The API permission `ANYTOOLAI_PORTAL_USAGE_READ_ENABLED` defaults off. Successful
normal/recovery finalization writes one immutable exhaustion edge in the same
transaction. A separately bounded worker task delivers with live-lease ACK,
retry/parking and crash redelivery. Portal validates consumer/product, saved
source/backend owner and full tuple before durably acknowledging one immutable
hint; current hints schedule GET-only reconciliation, historical hints are inert.
Portal's V1 client and retained-owner resolver supply Step 15 cabinet
composition. Kernel `0021` and Portal `20261111_0011` extend previous heads without
resetting usage, purchases or queue history. V1 wire/fixture bytes are unchanged.
See the common backend guide's implemented Step 14 section for settings, errors,
lease/recovery and enablement. Local PostgreSQL and synthetic reverse transport
are covered. Step 16 below supplies focused paired local browser/HTTP acceptance;
the full matrix and live/deployed acceptance remain deferred to ANY-767.

## ANY-766 Step 16 — focused local acceptance

Portal's `tools/joint_paid_runtime/` composes the real APIs/workers with separate
PostgreSQL databases, TCP service authentication and ordinary Portal sessions.
Only external LBX/AI responses and the second backend are synthetic. Temporary
enabled product copies preserve disabled commercial defaults in this repository.
The main HTTP journey covers all seven selected scenarios, truthful usage,
replay/failure/recovery and retained state after recreating its own containers.

The user reduced the 2026-11-11 verification scope to the common backend API and
main journeys. The synchronized plan records actual results and the deferred full
matrix. Optional peer transport lives in `infra/compose/docker-compose.peer.yml`;
PostgreSQL remains private. Dev now retains `postgres18-data` at PostgreSQL 18's
parent mount and pins the same 18.4 image/digest as Portal. Existing anonymous dev
volumes require explicit backup/reattachment before recreating an old project;
the harness touches only fresh run-owned resources. Step 17 and ANY-767 retain
their build/install and remote/live responsibilities.
