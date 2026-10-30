# Payment Portal integration map

Status: navigation, implementation snapshots and the ANY-711 service-authentication handoff.
Last observed: 2026-10-30.

## Ownership and sources

This repository is Platform Kernel: product/scenario execution, artifacts,
technical product/metric vocabulary and runtime usage/quota enforcement.
[Payment Portal](https://github.com/gushinets/payments-portal) owns identity,
sessions, legal acceptance, public discovery and the cabinet. Its target also
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

## Observed implementation

Historical snapshot (2026-10-23). Evidence baselines: Platform `79a2ada5b790f959a40b3e08451ef9ed8d97da5b`;
Portal `79dc3f4d204aec4ac9552e3d1da3481553cc8aef`.
These are inspected source snapshots, not deployment or conformance claims.

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

## Service authentication and scope convention (ANY-711 handoff)

This is the normative service-authentication handoff for all three operations. ANY-711
implements only manifest read. ANY-766 must implement the snapshot/invalidation rules below;
the future settings and permissions named here are not enabled or accepted by current code.
Peer settings and the accepted access-contract design were rechecked read-only at Portal
`2bb07d778edc5ea56011b0034ba24b0702ede81f` on 2026-10-30. This documentation change requires
no Portal source/artifact change or mutual SHA bump.

### Credentials and operation permissions

- **Portal -> Kernel manifest:** Portal sends its existing server-side `KERNEL_SERVICE_TOKEN`
  as `Authorization: Bearer <secret>`. Kernel validates against `ANYTOOLAI_PORTAL_SERVICE_TOKEN`
  and the optional `ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS` rotation slot. Its receiver-owned
  Portal principal has `PortalPermission.MANIFEST_READ` (`manifest:read`).
- **Portal -> Kernel invalidation:** reuse that same directional credential pair; no third
  secret is introduced. ANY-766 adds `PortalPermission.ACCESS_INVALIDATE` (`access:invalidate`)
  and explicitly grants it through Kernel's trusted receiver policy when invalidation is
  enabled. Possession of a manifest-only credential does not itself grant invalidation;
  requests cannot add permissions through headers, query parameters or body fields.
- **Kernel -> Portal AccessSnapshot:** use a different secret. The future Kernel sender
  setting is `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`; Portal's receiver settings are
  `KERNEL_ACCESS_SERVICE_TOKEN` and optional `KERNEL_ACCESS_SERVICE_TOKEN_PREVIOUS`.
  Portal binds this credential to a Kernel service principal with `access-snapshot:read`.
  These names are reserved for ANY-766 implementation. The two directional secrets must
  differ, and each environment and tenant/region connection uses independent secrets.

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
2. Switch the corresponding sender setting (`KERNEL_SERVICE_TOKEN` at Portal, or future
   `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN` at Kernel). Verify authorized requests with the new
   token and refusal of wrong scopes/permissions.
3. Remove the receiver's previous slot, restart/reload and verify the old token returns `401`
   while the new token still succeeds. At most two distinct tokens are accepted; an orphaned
   or equal previous token is invalid. Overlap has no automatic expiry and must be removed.

Emergency revocation removes the compromised token from every receiver slot immediately;
do not retain it as a rotation overlap. Rotate each direction independently. The existing
[manifest receiver procedure](../../infra/deployment/README.md#portal-capability-manifest-receiver-any-711)
implements the Portal -> Kernel half; reverse-direction support remains ANY-766 work.

## Dependencies before real integration

- **Identity:** canonical paid-access identity is Portal's authenticated UUID
  scoped by `(tenant_id, region, user_id)`. Current scenario `user_id` is
  client-supplied and unverified ([TD-013](../tech-debt-tracker.md)); it is not a
  Portal principal. Guest identity/quota remains separate from paid allowances.
- **Scope:** [Kernel Settings](../../apps/platform-api/src/anytoolai_platform_api/settings.py)
  and [region config](../../configs/kernel/regions.yaml) now default to `anytoolai/ru`,
  matching the inspected [Portal Settings](https://github.com/gushinets/payments-portal/blob/2bb07d778edc5ea56011b0034ba24b0702ede81f/apps/api/app/core/settings.py).
  Deployment must explicitly configure matching trusted scopes under the convention above;
  the historical `anytoolai/default` snapshot does not describe current defaults. Do not
  rename existing data scopes or infer region from UI locale.
- **Producer delivery:** Kernel API owners must supply implemented endpoint,
  producer-owned schema/positive and negative fixtures, paid metric/unit/release
  approvals and authenticated tenant/region deployment. Portal integration
  owners reconcile and test their consumer against that producer. No shared
  Portal/Kernel runtime package is required; platform-sdk serves product bundles.
- **Enablement:** the inspected Portal settings support a configured Kernel URL/token.
  Production enablement still requires deployed TLS/private-network verification and
  commercial approval after real conformance; a URL change is insufficient. Historical
  fixture pins and SIMULATED mapping history must not be relabelled as real.
- **Usage and launch:** the three operations above do not define the cabinet's
  actual usage/remaining API. Its contract and authenticated cross-app launch
  are separate future work. Kernel product handoff is not Portal login handoff;
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
by the owner on 2026-10-19; real producer conformance is a later enablement gate.
Read [ANY-727](https://linear.app/paveldik/issue/ANY-727) and companion
[ANY-728](https://linear.app/paveldik/issue/ANY-728) for this map's delivery work.
