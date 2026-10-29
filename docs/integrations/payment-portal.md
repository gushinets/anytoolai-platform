# Payment Portal integration map

Status: navigation and implementation snapshot; normative contracts are delegated below.
Last observed: 2026-10-23.

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

This map introduces no wire semantics or new MVP scope. Local scope remains
[MVP scope](../product-specs/mvp-scope-source-of-truth.md),
[platform boundaries](../architecture/platform-boundaries.md),
[guest quotas](../architecture/quota-model.md) and
[frontend boundaries](../architecture/frontend-boundaries.md).
Historical Portal contracts and execution plans do not override accepted sources.

## Observed implementation

Evidence baselines: Platform `79a2ada5b790f959a40b3e08451ef9ed8d97da5b`;
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
Its current settings support configured sources; the older production prohibition below is a
historical observation, not current enablement authority. Historical simulated fixture evidence
above remains unchanged. The [Kernel-owned v1 contract](../contracts/kernel-capability-manifest/v1/README.md)
now publishes a generated serialization schema, canonical positive/negative fixtures and byte
checksums. Offline checks retain the Portal positive bytes and independent semantic version,
and compare resolved standalone/OpenAPI/Portal schema constraints. Actual TCP HTTP interoperability
with the unchanged Portal client remains Step 4; artifact checks do not establish that result.

## Dependencies before real integration

- **Identity:** canonical paid-access identity is Portal's authenticated UUID
  scoped by `(tenant_id, region, user_id)`. Current scenario `user_id` is
  client-supplied and unverified ([TD-013](../tech-debt-tracker.md)); it is not a
  Portal principal. Guest identity/quota remains separate from paid allowances.
- **Scope:** [Kernel Settings](https://github.com/gushinets/anytoolai-platform/blob/79a2ada5b790f959a40b3e08451ef9ed8d97da5b/apps/platform-api/src/anytoolai_platform_api/settings.py)
  and [region config](../../configs/kernel/regions.yaml) use `anytoolai/default`.
  [Portal Settings](https://github.com/gushinets/payments-portal/blob/79dc3f4d204aec4ac9552e3d1da3481553cc8aef/apps/api/app/core/settings.py)
  permits `anytoolai/ru`. Scope alignment needs explicit producer deployment
  work; do not rename existing data scopes or infer region from UI locale.
- **Producer delivery:** Kernel API owners must supply implemented endpoint,
  producer-owned schema/positive and negative fixtures, paid metric/unit/release
  approvals and authenticated tenant/region deployment. Portal integration
  owners reconcile and test their consumer against that producer. No shared
  Portal/Kernel runtime package is required; platform-sdk serves product bundles.
- **Enablement:** Portal currently rejects configured provisional Kernel
  URL/token in production, even over HTTPS. Production enablement is separate
  reviewed work after real conformance; a URL change is insufficient. Historical
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
