# ANY-766 — Portal–Kernel Paid Execution Integration

Status: **STEPS 1–7 COMPLETE within local verification; Steps 8–12 pending; delivery ends at PR readiness**

Date: **2026-11-09**

Issue: [ANY-766](https://linear.app/paveldik/issue/ANY-766)

- State: active
- Owner: mixed — Portal and Kernel execution owners
- Last updated: 2026-11-10
- Review date: 2026-11-10
- Next action: Step 8 recoverable paid browser journeys, only when separately requested.
- Blocker: none for Step 8 implementation. Missing remote-server, live-provider and registry inputs do not block local integration or PR readiness; later operational actions retain the gates in Section 3.8.

Portal's `docs/exec-plans/active/ANY-766-implementation-plan.md` is authoritative;
Kernel keeps a byte-for-byte copy at the same repository-relative path.
The active repositories are the two clones under
`/home/wstanley/www/work_unirec/runtime-research`.

This is an execution plan, not a verification journal. Keep the goal, decisions,
step instructions, required checks and a concise current status here. Record
necessary decision changes with their reason and affected steps; keep detailed
run histories, commands, output and commit bookkeeping in execution reports or
PR/issue evidence rather than appending them to this plan. The first committed
plan remains available through Git: Portal `cde9a66`, Kernel `0ff8dfca`.

## 1. Goal & Final Expected Outcome

An authenticated Portal user with confirmed paid test access can launch the selected Kernel products through actual local browser and HTTP boundaries. Kernel verifies the existing Portal identity through scoped session delegation, obtains current access authority, resolves the scenario’s declared metric and passes the exact purchased allowance into ANY-507.

Acceptance commits the session/job and reservation atomically. One valid, durably saved, user-accessible final result consumes one unit. Terminal failure without that result releases the reservation. Replays return the original execution and bucket without another reservation or debit. The cabinet shows Kernel’s actual usage, reservations, remaining quantity and available capacity.

The user approved these production identities and shared counters:

- ProposalAI: `proposal_ai.generate_v1` → `proposal_ai.generations`, unit `generation`.
- Client Update Writer: `update_v1`, `prepaid_request_v1`, `reply_draft_v1` → `client_update_writer.messages`, unit `message`.
- Brief Decoder: `brief_decoder.decode_v1` → `brief_decoder.analyses`, unit `analysis`.
- Acceptance Builder: `draft_v1`, `check_v1` → `acceptance_builder.results`, unit `result`.

Counters are independent between products. Each successful scenario result consumes one unit. Internal workflow steps, provider calls and retries consume no additional units.

Existing test metrics and history retain their identities and TEST-ONLY meaning. Commercial quantities, exact LBX associations and sales enablement require separate owner approval.

**Delivery boundary — user decision, 2026-11-10:** ANY-766 ends with implemented
integration verified locally, minimal image-build/installation preparation and PRs
ready for review. Local acceptance uses real Portal and Kernel applications,
separate PostgreSQL databases and actual browser/TCP HTTP; external LBX and AI
provider responses may be deterministic test substitutes, labelled as such.

PR review and corrections precede registry publication and remote deployment.
Actual staging deployment, real external-service configuration, the complete
registration/payment/product journey, remaining natural-renewal acceptance and
production rollout belong to ANY-767, **stage 11 of parent ANY-504**. No remote
server, public domain, live purchase or registry credential is required to close
this plan's local development scope. Internal Step 11 below is the local
integration check; it is distinct from parent ANY-504 stage 11.
This delivery boundary supersedes earlier staging-completion wording for this
plan; the paid-access contracts and product behavior remain unchanged.

## 2. Current State & Reusable Implementation

Development bases: Portal ANY-766 is based on ANY-765
`b2ef280048ac634a60c18e820fbf702beddba19c`; Kernel is based on
`72ff15bc0b77903c87aa39f7b10186dccc556d09` and includes ANY-507/814.
Current migration heads after Step 7 are Portal `20261110_0008` and Kernel `0019`.

Development may continue above the verified ANY-765 base while its PR is reviewed.
After it merges, transfer only ANY-766 changes onto accepted main under a
separately authorized base refresh, preserving intervening corrections. Recheck
affected behavior and extend the actual migration heads without rewriting them.

### Consumed ANY-765 handoff and preservation requirements

Read the [current Step 10 producer handoff](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/docs/engineering/billing-background-operations.md#step-10-handoff--any-765) and [completed review/evidence record](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/docs/exec-plans/completed/ANY-765-implementation-plan-refactor.md). “Step 10” in that handoff means the whole program ticket ANY-766, not only this plan's internal Step 10 cabinet work.

- Preserve the inherited trust-observation provenance, paused automatic UNKNOWN recovery, explicit GET-only recovery, informational `block_to_close_days`, metric admission before new financial sends, isolated paid reads and cancellation ownership.
- Keep selected-meaning `confirmation_digest()` separate from full-source/audit identity (`source_digest`, full `kernel_manifest_version`, technical `digest`). Another product or global source-version change cannot invalidate unchanged selected consent. Historical v2 full-audit-digest acceptances remain readable and replay the exact saved buyer digest; v1 receives no invented technical quantity. Steps 3/11 must preserve these regressions.
- Primary selection uses complete relevant product inventory and original owner/version/fence proof. Financial CREATE admission and `restore-original`/`bind-original` retain customer-wide completeness. Steps 5/11 must preserve independence from unrelated incomplete products without weakening financial admission.
- Preserve the sole whole-user paid writer, atomic revision/causal observation/outbox/deadline commit, finite source trust, immutable same-cycle allowance identity and calendar precision. Calendar evidence stays Portal-internal; Step 5 implements snapshot V2 and Step 7 implements exact-N delivery/ACK.
- Current `/api/paid-access` requires an active verified-email session, derives scope/user server-side, is local and read-only after identity bookkeeping, and retains its reserved DB/thread budget and cancellation ownership. Step 10's separate usage API must preserve those authorization and availability guarantees.
- Reader compatibility is stricter than the unchanged migration head: pre-fix Step 9 binaries cannot read newly accepted selected-digest purchases. Step 12 installation preparation and the Section 7 handoff must record this format-compatibility floor for subsequent ANY-767 deployment/recovery; same migration head does not authorize rolling back to an older reader.
- At preparation, the refreshed handoff and Portal integration map still assigned production vocabulary to ANY-711. The [2026-11-09 ANY-766 scope clarification](https://linear.app/paveldik/issue/ANY-766) explicitly assigns selected production declarations/bindings to ANY-766 and leaves ANY-711 Done for its delivered manifest/TEST-ONLY baseline. **Step 1 now aligns both statements** without reopening ANY-711 or adding a dependency on new work there. Commercial quantity/LBX/sales approval remains separate.

### Reuse and actual gaps

- ANY-711 supplies real manifest delivery, independent consumer validation, fixture ownership and directional service authentication.
- ANY-765 supplies immutable accepted evidence, primary selection, calendar classification, stable allowance identities, semantic revisions, deadlines and atomic invalidation outbox updates.
- Steps 3/5 now implement immutable configured-source technical terms and production allowance derivation. Ordinary commercial enablement and live positive proof retain their separate gates.
- ANY-507 supplies paid owner partitioning, replay, reserve/finalize/release, recovery and readback. It already uses the required immutable allowance tuple.
- Kernel Step 6 attaches the Step 4 principal adapter to coherent paid admission and reservation/deferred ownership protection. Its existing `ClientEventService` now supports trusted paid owners, including events before a scenario exists; guest validation and deduplication remain intact.
- Kernel Step 6 implements the durable coherence/invalidation receiver. Portal Step 7 implements bounded durable invalidation transport with exact-N ACK, parking/CLI retry and restart repair. Kernel exhaustion delivery remains later work.
- Existing independent Compose projects, runners, migration services and Kernel profile activation are reusable. Add only the image/build and installation preparation needed for the selected Portal/Kernel pair; server installation follows PR review in ANY-767.

### Current completion and verification limits

- Steps 1–7 are complete within their contract/configuration and local test scope:
  production metric bindings and purchased terms, session delegation, Portal V2
  snapshots, Kernel coherent admission, ownership, invalidation receiver and paid
  client events and durable Portal invalidation delivery.
- Browser launch/recovery, usage/exhaustion delivery, cabinet integration, local
  joint verification and build preparation remain Steps 8–12.
- Real paired local paid HTTP/browser acceptance is not yet established and must
  pass in Step 11. Live-LBX and remote staging acceptance remain future ANY-767
  work; synthetic/ASGI evidence does not establish those external outcomes.
- The broader Kernel activation-marker test remains environment-limited:
  `test_activation_marker_is_readable_by_non_root_api_user` needs supported
  noninteractive execution as the target user. Do not treat the interrupted
  broader `quick-check` as a full PASS.
- The Step 6 invalidation receiver's permission is disabled by default through
  `ANYTOOLAI_PORTAL_ACCESS_INVALIDATION_ENABLED`; configure it explicitly when
  connecting the Portal sender. Sales enablement retains its separate gate.

## 3. Decisions, Contracts, Ownership & Dependencies

### 3.1 Authority and boundaries

Follow both repositories’ applicable AGENTS, architecture, conventions and delivery instructions. Portal billing authority remains ADR 0005 → accepted external-billing/access designs → the narrow live-source amendment and precise accepted dated decisions.

Preserve:

- RU contour isolation, Bundle 3 and generated Portal API contracts.
- Kernel product meaning in product configuration, with generic mechanisms in Core.
- Existing guest behavior and historical data.
- Customer legal-source restrictions.
- Separate application databases, migrations and deployment ownership.

Do not introduce quota templates, an admin API, catalog mirrors, a second metering path, a Portal usage ledger, direct-provider abstractions, a Resolver implementation or product UI relocation.

**Execution clarification — 2026-11-09:** the 2026-11-03 decisions in [ANY-766](https://linear.app/paveldik/issue/ANY-766) and [ANY-768](https://linear.app/paveldik/issue/ANY-768) establish the accepted strategy. The user clarified that Mikhail's response is the strategy decision and does not introduce another discussion or separately recorded protocol approval before implementation. The concrete protocol and storage details below are the selected implementation of that strategy; they are not presented as exact wire formats historically approved by Mikhail. Step 1 formalizes them in both canonical designs, schemas and fixtures and verifies producer/consumer consistency. Technical review is part of that work, not an external prerequisite. Escalate a concrete departure from the accepted strategy or a genuinely unresolved material contradiction, with evidence; do not stop to request an approval record for Sections 3.3–3.6.

### 3.2 Production declarations and immutable purchased terms

Add optional scenario-owned `paid_metric_key` to Kernel configuration and Core/SDK representations. The existing loader validates that the referenced metric belongs to the scenario’s product. Portal validates the purchased unit against that metric.

Declare the four approved production metrics and all seven bindings. Keep ordinary product/metric commercial flags disabled until sales approval. Existing test declarations remain unchanged.

Extend the existing protected mapping CLI with:

```text
--metric-key
--unit
--allowance-quantity
```

Existing `--quantity` retains its LBX commercial meaning.

Publish `product-link-v3` in the existing mapping table. Its immutable identity includes one fixed-per-cycle technical offer, the existing LBX selection and source provenance. Retain current live-source validation, operator identity, publication CAS and history.

New production acceptance uses:

- `purchased-technical-terms:v2`, with configured-source provenance.
- `accepted-purchase:v3`, binding the technical offer, mapping revision/digest, account/selection, commercial fingerprint and manifest evidence.

Quantities are strict integers from zero through `2^53−1`; booleans, floats and lossy values are rejected.

Read previous document versions without rewriting them. Preserve the selected-meaning confirmation digest separately from complete source/audit digests: unrelated product or global-version changes do not require fresh consent for unchanged selected terms. Historical v2 full-audit-digest and selected-digest acceptances both remain readable, with exact saved-digest replay. V1 purchases receive no invented quantity. SIMULATED purchases remain simulated. Existing subscriptions retain their accepted quantity through later cycles, even after a new mapping quantity is published.

Extend the existing provenance policy and customer response types together. Production cannot materialize allowances from SIMULATED evidence. Historical subscriptions without proven technical terms may retain independently supported access, but cannot acquire an invented metered allowance.

Tests use temporary product configurations with explicitly enabled capabilities and isolated synthetic quantities. They do not enable ordinary sales or promote simulated history.

### 3.3 B10: selected AccessSnapshot V2 contract

Keep:

```text
GET /internal/v1/access-snapshots/{user_id}?tenant_id=anytoolai&region=ru
```

The target snapshot producer will serve only `schema_version: 2`; Step 1 records this contract in the canonical designs and fixtures:

```text
schema_version
tenant_id
region
user_id
access_revision
refresh_after
expires_at
grants[]
allowances[]
```

Each grant contains `product_id` and nullable conservative UTC `valid_until`.

Each allowance contains:

```text
allowance_id
product_id
metric_key
unit
quantity
```

The immutable binding is:

```text
tenant / region / user / allowance_id / product / metric / unit / quantity
```

LBX calendar evidence stays in Portal. Do not export guessed UTC cycle boundaries. Membership in the committed snapshot authorizes the bucket; allowance identity and history survive removal from that snapshot.

Portal retains independently proven timestamp bounds internally. A future allowance is not exposed before its proven start; schedule authoritative reconciliation at that boundary. Local time never manufactures positive authority or a new cycle.

Use a five-second Portal–Kernel clock budget `B` for local/staging. The deployed environment must support that budget; it is not evidence of an already verified production clock guarantee:

```text
expires_at =
  min(Portal database time + 300 seconds,
      every included effective source/grant/proven UTC deadline) − B

refresh_after = min(Portal database time + 60 seconds, expires_at)
```

With no included facts, only the 300-second bound applies. Existing LBX clock conservatism remains separate. Return `503` when no complete, currently valid document can be served.

Retain:

- Source trust no longer than six hours.
- Implicit empty revision zero for a known user without a committed transition, without writing state.
- Positive committed revision for subsequent empty states.
- Semantic immutability at the same revision; refresh timestamps may change.
- Read-only GET, without LBX/Kernel calls.
- Overdue-boundary refusal until the existing writer commits the reduction.
- Bounded old-cycle use within existing trust; refill requires proven new-cycle evidence.

Kernel follows the existing request-driven refresh rules. A still-valid accepted document may be used during refresh failure only when it satisfies the durable floor and every admission predicate. Expired authority is never extended locally. Service `401/403` and unexpected `404` remain integration failures, not empty entitlement results.

Keep manifest and invalidation at version 1. Install compatible consumers before enabling the V2 snapshot connection. No V1 translation fabricates period semantics.

Update both canonical designs, producer schemas, positive/negative fixtures and independently validated consumer copies. Portal owns snapshot/invalidation/identity fixtures; Kernel owns manifest/usage/exhaustion fixtures.

### 3.4 Portal-session delegation and browser recovery

Use the user-selected one-use code with S256 PKCE and a narrow Kernel token.

Browser routes:

- Kernel `/portal-session/launch`.
- Kernel `/portal-session/callback`.
- Portal localized `/[locale]/kernel/authorize`, using existing locale routing.

The Kernel launch page stores an unpredictable state, verifier and validated local return target in tab `sessionStorage`. Allowed targets are registered product pages, result pages and handoff pages. Portal accepts no caller-selected external callback.

Portal authenticates the existing session and issues a random 32-byte code, valid for 60 seconds. The fixed Kernel callback receives code/state in the fragment, clears it immediately, verifies state and exchanges through the Kernel backend.

Interfaces:

- Portal `POST /api/kernel-session-codes` accepts `code_challenge` and `code_challenge_method: "S256"` under the existing Portal bearer. It returns the code and expiry with no-store headers.
- Kernel `POST /v1/portal-session/exchange` accepts `code` and `code_verifier`.
- Portal `POST /internal/v1/kernel-sessions/exchange` accepts the code/verifier under reverse-direction service authentication.
- Portal `POST /internal/v1/kernel-sessions/introspect` accepts the delegated token in a secret body field; its Authorization header carries the service credential.

Exchange returns a version-1 response containing the delegated `access_token`, `token_type: "Bearer"`, canonical scope/user and expiry. The token expires at the earlier of 30 minutes and parent-session expiry. There is no refresh token.

Introspection validates the token, audience, parent session and active user on every protected Kernel request. It returns canonical scope/user and conservative `valid_until`, with the Portal–Kernel clock budget removed. It returns no PII.

Use:

- `401` for invalid, revoked or expired delegation.
- Distinct safe error codes for delegated-token expiry and invalid/revoked parent authority.
- `403` for authenticated service scope/permission refusal.
- `503` for dependency unavailability.

Portal stores hashes only in one `kernel_session_delegations` table, linked to the existing AuthSession with cascading deletion. Code exchange is atomic and single-use. Use lock order User → AuthSession → delegation for the security writes. Do not add commits to internal identity reads.

Browser custody and recovery are fixed as follows:

- Store the delegated token and canonical owner in tab `sessionStorage`; never in URL queries, localStorage, telemetry or product inputs.
- Keep the original Portal bearer exclusively at Portal.
- Extend CE-kit’s existing prepared-start mechanism with a versioned recovery descriptor containing its original key and frozen request. Do not create another execution API.
- Persist that descriptor before sending a new paid start. Bind it to canonical scope/user. If persistence fails, refuse the new paid send with a recoverable local error; existing result reads remain available.
- After acceptance, replace the pending descriptor with the accepted session reference and remove the frozen input.
- After an uncertain response, reload or token expiry, retry the same frozen request/key after reauthorization by the same owner.
- A different owner, explicit logout or parent revocation clears token, pending inputs and displayed private state. Late responses from the previous identity generation are ignored.
- Reauthorization must restore product/result/handoff continuation. It must never silently create a guest or a new logical start.

Rebuild the shared API client on identity-generation changes. Preserve its lifetime across ordinary product remounts.

Every protected request introspects identity. An already authenticated in-flight request may complete under its checked authority; new execution rechecks principal expiry after admission waits.

### 3.5 Coherence, admission, ownership and client events

Preserve independent directional credentials:

- Portal → Kernel: `KERNEL_SERVICE_TOKEN`, received as current/previous `ANYTOOLAI_PORTAL_SERVICE_TOKEN`.
- Kernel → Portal: `ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN`, received as current/previous `KERNEL_ACCESS_SERVICE_TOKEN`.

Add receiver-owned permissions for each new operation. Internal endpoints require exactly one Bearer header, trusted scope, TLS verification, no browser Origin, no-store responses and safe errors.

Kernel stores the revision floor and cached snapshot in one PostgreSQL coherence row per scoped user. Snapshot installation, invalidation and new-execution admission use that same row lock. Eviction removes the document, never the floor.

New-execution sequence:

1. Authenticate the canonical owner.
2. Attempt owner/hash-matched accepted replay.
3. Perform required HTTP refresh outside the business transaction.
4. Lock coherence and repeat replay lookup.
5. Resolve the server-declared scenario metric and exact eligible allowance.
6. Invoke ANY-507 using the caller-owned Session.
7. After bucket/reservation waits, resample database wall time and recheck principal expiry, floor/revision, snapshot expiry and grant authority.
8. Commit all acceptance writes together, or roll them back.

Preserve ANY-507’s request hash, owner partition and deliberate exclusion of allowance/revision from replay meaning. A frozen-tuple conflict cannot reset history and denies only dependent metering.

Protect paid start, handoff create/preview/accept/decline, polling, next-actions, result/artifact reads and client-event ingestion. Use existing reservation ownership or server-written deferred-handoff ownership metadata. Historical body `user_id` is never authenticated ownership.

Owned accepted results remain readable with valid identity after grant expiry. Accepted jobs finalize against their original bucket after revocation or rollover.

For handoff admission, make the late paid-authority refusal escape the acceptance transaction. The current HTTP handler’s deferred PlatformError path must not commit target linkage/reservation changes or mark a retryable authority/dependency refusal as a terminal failed handoff. Preserve existing expiry, decline and terminal execution semantics.

Extend the existing `ClientEventService`:

- Accept the trusted paid owner from HTTP composition.
- Verify any supplied scenario belongs to that owner using existing execution ownership.
- Derive paid `user_id`; do not trust a body claim.
- Permit authenticated product events before a scenario exists.
- Preserve existing guest validation and event-id deduplication.
- Keep events observational: they never authorize access, finalize results or charge usage.

### 3.6 Invalidation, usage and exhaustion delivery

**Portal invalidations**

Reuse the existing outbox, BillingWorkItem claims and embedded worker. Add one independently bounded delivery lane so LBX work cannot starve delivery or local deadlines.

Capture revision N before HTTP. On `204`, acknowledge only N, monotonically. Preserve pending N+1 and newer work generations. Use User → outbox → queue lock order, with HTTP outside locks.

Retry transport/429/5xx with bounded backoff. Park permanent auth/schema/scope failures durably, alert and expose inspect/retry through the existing privileged CLI. Restart repairs missing scheduling from unresolved outbox rows.

**Kernel usage API**

```text
GET /internal/v1/usage/{user_id}
  ?tenant_id=anytoolai
  &region=ru
  &allowance_id=...
```

Accept 1–100 distinct allowance IDs. Reject malformed, repeated or excessive inputs with `422`.

Version-1 response contains canonical scope/user and one result per requested allowance ID, in request order:

- `observed`: allowance ID, product, metric, unit, quantity, successful_used, reserved, remaining, available and read_at.
- `unobserved`: allowance ID and status only; no invented tuple or counters.

Unknown and foreign buckets are indistinguishable as `unobserved`. Storage failures return `503`, never zero. Counters come from one row snapshot through existing repository/readback methods.

```text
remaining = max(quantity − successful_used, 0)
available = max(quantity − successful_used − reserved, 0)
```

Add authenticated public:

```text
GET /v1/products/{product_id}/paid-usage?allowance_id=...
```

It derives the owner from introspection, restricts rows to that product and uses the same response semantics. Historical reads do not require current sales enablement.

Usage reads create no rows. Valid snapshot ingestion establishes zero-use buckets through existing `ensure_usage`; later reads report actual zero only for an established bucket.

**Exhaustion**

Kernel owns version-1 event fixtures for:

```text
schema_version: 1
event_type: allowance_exhausted
tenant_id
region
user_id
allowance_id
product_id
metric_key
unit
quantity
occurred_at
```

Write the immutable event into an outbox in the same transaction as successful finalization when `became_exhausted` is true. Cover normal and rollback-recovery finalization. Unique identity is scoped user + allowance ID + event type.

The existing worker runs a bounded delivery task independently of workflow duration. Claim rows with a lease, send outside SQL and acknowledge only the live claim. Retry transport/429/5xx; park permanent errors with diagnostics. Receiver:

```text
POST /internal/v1/allowance-exhaustions
```

Portal verifies the full tuple against its immutable issued allowance. It inserts one durable `allowance_exhaustion` work item with an immutable payload and unique coalescing key. Duplicate insertion is a no-op; ordinary coalescing must not revive completed duplicate hints.

Return `204` only after durable commit, including valid duplicate or historical delivery. Unknown/mismatching bindings return `409`; malformed payloads return `422`.

The local worker may request existing GET-only reconciliation for a current allowance. Old-cycle hints complete without affecting the new cycle. Exhaustion never terminates a subscription, revokes a grant, replenishes capacity or triggers a financial command. Portal stores no usage counters.

**Portal cabinet API**

Add separate authenticated `GET /api/paid-usage`. Reuse the existing active verified-email billing-session guard and server-derived tenant/region/user; generic identity-session authentication alone does not enforce verified email. Success and refusal responses are no-store. Kernel usage calls use their own bounded HTTP resources and cannot occupy the existing local `/api/paid-access` reserved DB/thread budget.

Derive requested IDs locally: current production allowances, or the most recent issued allowance per product when no current allowance exists. Mark historical items explicitly.

Read Kernel outside Portal transactions, validate scope/owner and observed tuples, then re-read the local access revision. A changed revision returns retryable `503 paid_usage_state_changed`; do not present a mixed result.

The generated Portal DTO includes local allowance identity/terms and `current | historical` classification. Observed items include actual counters/read time; unobserved items omit counters. A mismatching item becomes unavailable with diagnostics. A dependency outage returns `503`; `/api/paid-access` remains independently usable.

### 3.7 Minimal build and installation preparation

Ownership:

- Portal team: Portal code, embedded worker, migrations, image builds and app-owned Compose/runner changes.
- Kernel team: Kernel code, API/worker builds, migrations, profile activation and app-owned Compose/runner changes.
- Infrastructure owner assigned for ANY-767: server/operator, domains/TLS, registry access, secrets, shared ingress/network and backups.

Reuse existing Dockerfiles, independent Compose projects, repository-owned runners,
private databases and retained volumes. Optional image overrides belong to each
app: Portal `deploy/compose.images.yml`, Kernel
`infra/compose/docker-compose.images.yml`. Component-selectable build/publish
workflows belong in each repository's `.github/workflows/publish-images.yml`.
Implementing these files does not execute publication or deployment.

Prepare independent frontend/backend builds for GitHub Actions and subsequent
GHCR publication. Portal API/migration use the same backend image. Kernel API and
worker use their existing Dockerfiles and one matching backend source revision.
Frontend-only changes must not require rebuilding or restarting an unchanged
compatible backend. Preserve the existing environment-specific frontend
origins/base paths as explicit build inputs; use local test origins for rehearsal.

Keep version selection simple: pin the chosen image references/digests in app-owned
Compose environment inputs and record their source revisions, migration heads,
peer wire versions and frontend build inputs in the existing runbooks. Application
builds run before server installation. Control scripts may use a checkout at the
matching reviewed revision; application-specific migration/profile commands run
inside the selected images.

Do not build a general release manager, portable installer bundle, new web API
compatibility-ID catalogue or shared version-selection schema. A universal
`selection.json` and copied runner/helper release bundles are not required.
Support the concrete locally verified pair and document its compatibility limits;
do not infer compatibility from equal Git SHAs. Record the Portal purchased-document
reader floor: an unchanged migration head does not make older pre-selected-digest
readers compatible with new purchase history. Installation instructions must reject
or exclude unsupported reader/image combinations without rewriting history.

Provide the smallest repository-owned build/install commands and parameterized
configuration needed by this pair, reusing existing runners. Backend updates
preserve deployment locks, quiesce/drain, migration-before-start, readiness and
activation. Migration failure keeps admission closed; recovery follows the existing
backup procedure. Frontend-only update uses the existing Compose service with
`--no-deps`, preserving backend, migrations, active profile and volumes.

For Kernel, generate the candidate profile inside the selected API image, bind an
explicit operator-owned host directory and derive host mount paths from it. Do not
reuse container paths as host paths. Preserve profile fingerprints, API/worker
source checks and the existing activation marker; retain the previous profile
until successful activation. Do not add another activation mechanism.

Step 12 verifies the chosen image/configuration locally using disposable resources
and records reproducible installation commands. Remote-host configuration,
actual registry publication, deployment and the post-review installed-version
acceptance belong to ANY-767. Missing remote inputs do not block Step 12.

### 3.8 Commercial and operational gates

Contract formalization and consistency checks belong to Step 1. The accepted
strategy needs no additional preliminary protocol approval.

- **Development base:** use Section 2's bases and preservation rules. Further Git integration requires separate authorization.
- **Local acceptance:** use isolated test users, known test quantities and temporary enabled product profiles. Real interservice HTTP/authentication, PostgreSQL and browser checks are mandatory; replacing LBX/AI provider responses is permitted when clearly labelled. Do not enable ordinary sales or promote simulated history.
- **Sales/live proof:** approved quantities, exact LBX associations and an authorized supported paid test purchase are prerequisites for their later live actions, not for the local completion of ANY-766.
- **Review before rollout:** prepare PRs for review, resolve review changes and rerun affected checks before publication/deployment. This plan's endpoint is local development and PR readiness; external PR review follows it.
- **Registry/staging — ANY-767:** after PR review/corrections, the infrastructure owner supplies the server/operator, domains/TLS, registry access, secrets, data roots, backups, SMTP, approved AI/LBX configuration and deployment authorization. Missing inputs defer those actions without blocking this plan.
- **Production — ANY-767:** rollout follows the full billing-journey and environment acceptance.

Record local readiness separately from later live/staging/production acceptance.
Unexecuted external checks remain NOT_RUN; they do not become a failed local
criterion or a synthetic live PASS.

## 4. Local Functional DoD & Acceptance Coverage

- Known-user empty revision zero is read-only; refusal creates no job, reservation or debit.
- All seven selected scenarios use the approved metric; shared product counters behave consistently.
- Actual local Portal–Kernel HTTP/browser execution from committed test purchase/access state produces one accessible result and one debit; cabinet and Kernel readback agree. Do not substitute either app, their authentication or databases with endpoint mocks.
- Failure/cancellation without a successful result releases capacity.
- Same-key replay returns original execution/bucket across reauthorization, reload, grant changes and rollover.
- Last-unit races accept only affordable work; reserved capacity is distinct from final exhaustion.
- Concurrent invalidation/install/admission cannot regress the floor or commit expired authority.
- Same-cycle block/recovery preserves allowance ID, quantity and usage; only proven new-cycle evidence creates a bucket.
- Outage/restart preserves finite authority, reservations, usage and pending delivery.
- Foreign identity/scope/audience/resource access fails without disclosure.
- Paid client events work without a guest, retain deduplication and cannot impersonate another owner.
- N acknowledgement cannot clear N+1; exhaustion acknowledgement follows durable hint commit.
- New quantities affect new purchases only; legacy and SIMULATED evidence remain compatible.
- Browser expiry/relaunch preserves the original logical start and rejects stale-account responses.
- The selected local image/configuration rehearsal preserves databases, usage and active profiles, including a frontend-only update; unsupported reader/image combinations are refused or excluded by the installation contract.

Steps 2–10 implement the product integration. Step 11 is the assembled local
HTTP/PostgreSQL/browser proof; Step 12 prepares and locally verifies minimal build
and installation support. The PR readiness checklist closes this plan. Remote
staging acceptance is not part of its DoD and follows review in ANY-767.

## 5. Sequential Implementation Steps

### Common execution protocol

Shared execution rules for both repositories:

1. Follow the current user request, applicable root and subtree `AGENTS.md`, repository authorities and delivery instructions. Communicate with the user in Russian; keep engineering artifacts in English.
2. Implement only the numbered step requested by the user. A request to execute Step 1 authorizes its document/schema/fixture/test work without another preliminary contract approval. Preparation or plan maintenance alone does not execute Step 1 or authorize application changes.
3. Reuse existing mechanisms, composition points, tooling and contracts; do not create a parallel mechanism when the existing one can meet the requested step.
4. Run the step's focused checks and applicable non-fixing checks, fix failures introduced by the step, and record actual commands and evidence. Broader suites belong to the assembled result or a separately requested verification.
5. Report **PASS / FAIL / NOT_RUN / BLOCKED** for each relevant check or acceptance item. PASS requires actual passing evidence; FAIL records an executed failure; NOT_RUN records an unexecuted check and reason; BLOCKED identifies the missing prerequisite or decision. Synthetic evidence never counts as live acceptance.
6. Apply Section 3.8 and other applicable commercial/operational conditions only to the actions they govern. Do not perform unapproved live LBX, financial, publication, staging or production operations.
7. Do not stage, commit, push, merge, rebase or switch branches during subsequent execution. Do not reset, stash, discard or overwrite existing work. Initial branch creation and the 2026-11-09 predecessor-base refreshes were preparation-only authorizations; they do not authorize later Git operations. Proposed commit messages below grant no authorization.
8. Escalate only a concrete departure from the accepted strategy or a genuinely unresolved material decision, with evidence. Do not request another approval of the already selected strategy or an approval record for Sections 3.3–3.6. Continue independent authorized work when a commercial/operational condition blocks another action; record its precise scope without guessing or bypassing it.
9. Portal remains the authoritative plan. Update only concise status, necessary decisions or step instructions here; keep detailed execution evidence outside the plan. Synchronize the entire file byte-for-byte to Kernel after each plan change and verify equality before handoff.
10. Keep affected as-built documentation and runbooks current within their owning steps. Step 11 supplies the combined local acceptance; the final PR checklist adds no implementation stage or repeated full test campaign.

Repository roots:

- Portal: `/home/wstanley/www/work_unirec/runtime-research/payments-portal`.
- Kernel: `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform`.

Commands below run from the indicated root. New test targets are planned additions and must be created by their step.

Use Portal’s root `.venv` and Kernel’s `.quick-check-venv`. Bootstrap through existing setup commands if needed; do not install into system Python. Portal root npm aliases need a command-scoped PATH:

```bash
PATH="$PWD/.venv/bin:$PATH" npm run check:fast
```

Portal PostgreSQL cases require its isolated test server/configuration. Kernel cases require `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` pointing to a maintenance database for disposable test databases. Do not print credentials. Skipped database cases are NOT_RUN, never PASS.

All prompts below require the complete authoritative plan and this common protocol, including Russian communication with the user. Consult Section 2 for completed steps. If the plan file is absent or ambiguous, report the exact problem instead of reconstructing it from a historical external file.

After each code step, run its focused checks and applicable non-fixing lint/type/architecture checks. Fix failures introduced by the step. Broad suites run on the assembled result.

### Step 1 — Formalize and validate Portal–Kernel contracts

**Goal / Expected behavior:** future chats receive the synchronized plan and matching canonical specifications, schemas and fixtures that both producers and consumers validate against the selected contracts.

**Repositories / Read before implementation:** both root instructions, Portal docs instructions, ADR 0005, both canonical designs, the current ANY-765 producer handoff and completed evidence linked in Section 2, the 2026-11-09 ticket scope clarification, and the [Kernel handoff](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/docs/handoffs/ANY-507-execution-metering.md).

**Implement / reuse:** plan saving and base/migration recording are complete as a preparation-only checkpoint. Verify that saved record, then formalize the selected contracts in Sections 3.3–3.6 in both canonical designs. Add producer schemas, positive/negative fixtures, independently validated consumer copies and focused contract tests using the existing ANY-507/711 mechanisms and tooling. Review consistency across documents, producers and consumers as part of this step; do not wait for another approval record. Align the two stale ANY-711 production-vocabulary ownership statements in the consumed handoff/integration map with the dated ANY-766 scope clarification; preserve delivered ANY-711 ownership and separate commercial approval. Preserve historical evidence and distinguish target contracts from implemented runtime behavior.

**Invariants:** no Git integration, predecessor rewrite, financial action or runtime claim from fixtures.

**Verification — Portal:**

```bash
PATH="$PWD/.venv/bin:$PATH" npm run docs:check
./.venv/bin/python -m pytest -q apps/api/tests/test_any766_contracts.py
./.venv/bin/python scripts/check_kernel_manifest_contract.py --local
```

**Verification — Kernel:**

```bash
./.quick-check-venv/bin/python scripts/agent/runner.py validate-docs
./.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check
./.quick-check-venv/bin/python -m pytest -q apps/platform-api/tests/test_paid_contract_fixtures.py
```

**Expected completion:** both canonical designs and producer/consumer fixtures agree with Sections 3.3–3.6; both repositories pass their focused contract checks, including unknown usage, duplicate exhaustion and unsupported versions. Technical review is complete as part of Step 1; this does not claim runtime implementation or live acceptance.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 1. Communicate in Russian. Preparation is complete. Follow both repositories’ instructions and the common protocol. Formalize Sections 3.3–3.6 in the canonical designs, schemas, fixtures and focused contract tests using existing ANY-507/711 tooling; verify consistency as part of this work. No additional preliminary contract approval is required. Synchronize the Kernel plan copy, run the specified checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Preserve Git state and commercial/operational gates. Escalate only a concrete strategy departure or unresolved material contradiction with evidence.

**Proposed commit:** `ANY-766 - Define Portal Kernel paid contracts`

### Step 2 — Declare production metrics and scenario bindings

**Goal / Expected behavior:** all seven scenarios resolve their approved metric through product-owned configuration.

**Repository / Read before implementation:** Kernel; [loader](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/backend/platform-core/src/anytoolai_platform_core/config/loader.py), product declarations and Core/SDK scenario contracts.

**Implement / reuse:** add `paid_metric_key`, four declarations and bindings; extend existing loader/reference checks and SDK compatibility. Update current manifest inventory fixtures while preserving historical/test identities.

**Invariants:** sales remain disabled; no Task Finder web surface or Client Update Writer guest-policy change.

**Verification:**

```bash
./.quick-check-venv/bin/python -m pytest -q packages/backend/platform-core/tests/unit/test_config_loader.py apps/platform-api/tests/test_paid_metric_bindings.py apps/platform-api/tests/test_capability_manifest_contract.py
./.quick-check-venv/bin/python scripts/agent/runner.py validate-configs
./.quick-check-venv/bin/python scripts/agent/runner.py validate-architecture
./.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance --portal-root /home/wstanley/www/work_unirec/runtime-research/payments-portal --portal-python /home/wstanley/www/work_unirec/runtime-research/payments-portal/.venv/bin/python
```

**Expected completion:** valid bindings resolve deterministically; missing, foreign and incompatible bindings fail.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 2. Follow applicable repository instructions and its common execution protocol. Reuse Kernel configuration validation and preserve guest policies, TEST-ONLY history and disabled sales. Update required consumer fixtures. Run the step’s focused checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Declare production metrics and scenario bindings`

### Step 3 — Publish and accept purchased quantities

**Goal / Expected behavior:** an operator publishes exact terms and a buyer sees and immutably accepts them.

**Repository / Read before implementation:** Portal; [CLI](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/cli/commercial_mappings.py), [product links](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/catalog/product_link.py), [technical terms](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/purchases/technical_terms.py).

**Implement / reuse:** add the versioned documents and CLI arguments. Validate actual enabled capability/unit and selected LBX offer. Include selected technical meaning in publication/confirmation digests and final CAS, while retaining complete source/audit identity separately. Preserve `confirmation_digest()` semantics and exact historical v2 full-digest replay. Show quantity/unit before consent. Preserve original-operation recovery before new-sale I/O.

**Invariants:** no template/catalog/admin API, no historical rewrite and no reassignment of LBX commercial quantity.

**Verification:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_any765_purchase_terms.py apps/api/tests/test_commercial_mapping_postgres.py apps/api/tests/test_any766_purchase_terms_postgres.py
npm --workspace @anytoolai/web run test:components -- tests/components/any766-purchase-terms.test.tsx
PATH="$PWD/.venv/bin:$PATH" npm run generate
PATH="$PWD/.venv/bin:$PATH" npm run generate:check
```

Cover Q changes, immutable renewal quantity, CAS/replay, unsupported metric/unit, zero, overflow, bool/float rejection and older versions. Regress unchanged selected consent across unrelated product/global-source/manifest-version changes, changed selected terms requiring reacceptance, and exact saved full-digest v2 replay.

**Expected completion:** new acceptance contains the exact published technical offer; old subscriptions keep theirs.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 3. Follow Portal root/API/web instructions and the common protocol. Reuse the protected CLI, source clients, immutable acceptance and transaction guards. Preserve historical and SIMULATED documents. Run the specified focused checks and generation, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not publish real associations, enable sales or operate live LBX/production without authorization. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Publish immutable production allowance terms`

### Step 4 — Implement scoped session delegation

**Goal / Expected behavior:** Kernel verifies the existing Portal identity without receiving its original bearer.

**Repositories / Read before implementation:** both; [Portal authentication](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/identity/services/auth.py), identity models and [Kernel service authentication](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/apps/platform-api/src/anytoolai_platform_api/manifest_auth.py).

**Implement / reuse:** add the delegation migration, code issuance, exchange, introspection and Kernel adapter. Reuse session validation while separating internal reads from public last-seen commits. Implement the TTL, PKCE, hashing, audience, parent-session and lock-order rules specified in Section 3.4.

**Invariants:** no second user directory, identity matching, refresh tokens or broad SSO platform.

**Verification — Portal:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_api_identity_session.py apps/api/tests/test_kernel_session_delegation_postgres.py
```

**Verification — Kernel:**

```bash
./.quick-check-venv/bin/python -m pytest -q apps/platform-api/tests/test_portal_session_api.py
```

Cover single-use races, wrong verifier/audience/scope, expiry, logout/reset/deactivation, parent deletion, dependency outage and secret-log canaries.

**Expected completion:** a genuine principal is available; invalid identity never becomes guest authority.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 4. Follow both repositories’ authoritative instructions and common protocol. Reuse Portal sessions and directional authentication; implement the specified delegation and parent-session checks without another identity authority. Run focused security/PostgreSQL checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Delegate Portal sessions to Kernel`

### Step 5 — Derive production allowances and serve snapshots

**Goal / Expected behavior:** accepted production terms produce complete, finite V2 authority.

**Repository / Read before implementation:** Portal; [paid writer](https://github.com/gushinets/payments-portal/blob/b2ef280048ac634a60c18e820fbf702beddba19c/apps/api/app/domains/billing/paid_access.py), [allowance issuance](https://github.com/gushinets/payments-portal/blob/b2ef280048ac634a60c18e820fbf702beddba19c/apps/api/app/domains/billing/paid_allowances.py), [paid read](https://github.com/gushinets/payments-portal/blob/b2ef280048ac634a60c18e820fbf702beddba19c/apps/api/app/domains/billing/paid_read.py).

**Implement / reuse:** replace simulation-only derivation switches with explicit provenance policy. Reuse primary/cycle classification, issuance, deadline scheduling and the sole paid commit. Preserve complete relevant product proof for primary decisions and customer-wide proof for financial CREATE/original-resolution admission; unrelated incomplete products must not block a proven primary. Add a scoped committed-state read and authenticated V2 producer with bounded serving capacity. Update customer DTO provenance and generated contracts.

**Invariants:** no source I/O or state writes in snapshot GET; no guessed calendar conversion or repricing existing subscriptions.

**Verification:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_access_snapshot_postgres.py apps/api/tests/test_paid_access_recovery_postgres.py apps/api/tests/test_paid_access_capacity_postgres.py apps/api/tests/test_paid_access_terms_postgres.py apps/api/tests/test_paid_access_primary_scope_postgres.py
PATH="$PWD/.venv/bin:$PATH" npm run generate
PATH="$PWD/.venv/bin:$PATH" npm run generate:check
```

Cover revision zero/N, no-op, rollback, source/UTC deadlines, future starts, simulation isolation, renewal retention and unrelated-product survival. Retain the scoped-primary/operator regressions and stricter financial admission when another product remains incomplete. Include `apps/api/tests/test_paid_access_review_regressions_postgres.py`: preserve finite source-end history and one skew adjustment, distinct overdue-reduction/restoration revisions, stable same-cycle allowance IDs, rollback of both phases and product-local inventory failures. Retain the explicit calendar-month offset controls in `apps/api/tests/test_paid_access_policy.py`.

**Expected completion:** service reads expose the committed production set with stable IDs and bounded authority.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 5. Follow authoritative billing instructions and the common protocol. Extend existing paid derivation, issuance, deadlines and bounded reads; preserve historical terms and same-cycle IDs. Run focused API/PostgreSQL/capacity checks and generation, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live financial or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Serve production paid access snapshots`

### Step 6 — Enforce paid admission, ownership and events

**Goal / Expected behavior:** paid actions use current authority and observational events work under trusted identity.

**Repository / Read before implementation:** Kernel; [scenario runtime](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/backend/platform-core/src/anytoolai_platform_core/scenarios/service.py), [handoff service](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/backend/platform-core/src/anytoolai_platform_core/handoffs/service.py), [client events](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/backend/platform-core/src/anytoolai_platform_core/events/client_events.py).

**Implement / reuse:** add coherence migration, snapshot client and invalidation receiver. Apply the replay/refresh/lock/reserve/final-check sequence. Protect every paid surface, including deferred handoffs and client events. Preserve accepted replay before mutable configuration checks. Correct handoff rollback boundaries for late authority refusal.

**Invariants:** no second metering/finalization path, HTTP under locks, guest fallback, floor deletion or body-identity adoption.

**Verification:**

```bash
./.quick-check-venv/bin/python -m pytest -q apps/platform-api/tests/test_paid_access_admission_postgresql.py apps/platform-api/tests/test_paid_client_events.py apps/platform-api/tests/test_client_events_api.py apps/platform-api/tests/test_handoffs_api.py
```

Use PostgreSQL barriers for stale N after N+1, install races, restart/eviction, last unit, expiry after waits and full handoff rollback. Test paid events without guests, foreign ownership and guest/event-dedup regressions.

**Expected completion:** stale authority cannot commit new work; accepted ownership and paid event correlation remain valid.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 6. Follow Kernel instructions and the common protocol. Reuse ANY-507/814 admission, replay and ownership; extend existing client events. Implement durable coherence, post-wait checks and handoff rollback without another meter. Run focused API/PostgreSQL races, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Enforce coherent paid execution and ownership`

### Step 7 — Deliver Portal invalidations durably

**Goal / Expected behavior:** pending revisions reach Kernel without lost acknowledgements or deadline starvation.

**Repository / Read before implementation:** Portal; [worker](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/jobs/billing.py), [work lifecycle](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/billing/work.py), [outbox](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/models/billing_access.py).

**Implement / reuse:** schedule coalesced delivery with the paid commit. Extend recurring-work indexes, claims, bounded resources and repair scan. Implement exact-N acknowledgement, retries, permanent parking and existing-CLI inspection/retry.

**Invariants:** no new scheduler or mandatory worker container; LBX configuration is unnecessary for delivery.

**Verification:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_access_invalidation_delivery_postgres.py apps/api/tests/test_billing_worker_postgres.py
```

Cover crashes around send/apply/ack, N/N+1, lease/generation loss, outage, permanent failure and deadline progress under saturation. Preserve the predecessor's two causal revisions on overdue refresh and final outbox coalescing; the early reduction must not schedule queue work, and acknowledgement must advance only through the revision actually sent.

**Expected completion:** restart repairs delivery and preserves monotonic acknowledgement.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 7. Follow Portal instructions and the common protocol. Reuse outbox, claims, generations and embedded worker; implement bounded delivery and exact sent-revision acknowledgement. Run focused delivery/concurrency/capacity checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Deliver durable access invalidations`

### Step 8 — Connect browser launch and recoverable paid journeys

**Goal / Expected behavior:** Portal users reach Kernel products and continue the original operation across reload or reauthorization.

**Repositories / Read before implementation:** both; [prepared starts](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/frontend/ce-kit/src/scenarios/prepareScenarioStart.ts), [Kernel client](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/apps/web-mirror/src/lib/apiClient.ts), shared product runtime and Portal billing launch surfaces.

**Implement / reuse:** add the fixed launch/authorization/callback flow, tab token custody, owner-bound recovery descriptor and identity-generation guards. Extend existing prepared starts, attach-session handling, event tracking and handoff consent. Never create a guest in paid mode.

**Invariants:** no credential in query/logs, new product UI or duplicate start after uncertainty.

**Verification — Portal:**

```bash
npm --workspace @anytoolai/web run test:components -- tests/components/any766-kernel-launch.test.tsx
npm run lint:web
npm run typecheck:web
```

**Verification — Kernel:**

```bash
pnpm --filter @anytoolai/ce-kit exec vitest run test/identity/portalSession.test.ts test/scenarios/paidStartRecovery.test.ts test/events/trackClientEvent.test.ts
pnpm --filter @anytoolai/web-mirror exec vitest run test/paidProductJourney.test.tsx test/HandoffConsent.test.tsx
```

Cover all scenario modes, reload, lost start/exchange responses, expiry, different owner, invalid state, storage refusal, result deep links and late responses. Actual desktop/mobile integration follows in Step 11.

**Expected completion:** reauthorization preserves original request/key or accepted session; account changes expose no previous-user data.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 8. Follow both frontend instruction sets and the common protocol. Reuse shared transport, prepared starts, attach sessions, events and handoff consent. Implement the specified tab custody and same-owner recovery without guest fallback. Run focused checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Connect recoverable paid browser journeys`

### Step 9 — Expose usage and deliver exhaustion

**Goal / Expected behavior:** actual counters are readable and committed exhaustion is recoverably delivered.

**Repositories / Read before implementation:** both; [Kernel readback](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/backend/platform-core/src/anytoolai_platform_core/quotas/readback.py), [workflow runner](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/packages/backend/platform-core/src/anytoolai_platform_core/workflows/runner.py), worker lifecycle and Portal issued-allowance/work queries.

**Implement / reuse:** implement Section 3.6 routes and fixtures. Add the transactional exhaustion outbox at both success orchestration paths. Run bounded leased delivery in the existing worker. Add immutable deduplicated Portal hints and corresponding work-index migration.

**Invariants:** no second debit, Portal counters, financial command or zero manufactured by reads.

**Verification — Kernel:**

```bash
./.quick-check-venv/bin/python -m pytest -q apps/platform-api/tests/test_paid_usage_exhaustion_postgresql.py apps/platform-api/tests/test_execution_finalization_postgresql.py apps/platform-api/tests/test_execution_readback_postgresql.py
```

**Verification — Portal:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_allowance_exhaustion_receiver_postgres.py
```

Cover result/debit/outbox rollback, duplicate finalization/delivery, crash before acknowledgement, unknown/foreign usage, tuple conflict, old-cycle delivery and busy versus exhausted.

**Expected completion:** actual usage and one durable exhaustion edge survive rollback/restart without repeated effects.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 9. Follow both repositories’ instructions and the common protocol. Implement the exact usage/exhaustion contracts using ANY-507 readback/finalization and existing workers/work storage. Preserve durable-commit acknowledgement and immutable deduplication. Run focused PostgreSQL/contract/recovery checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Expose usage and deliver exhaustion`

### Step 10 — Display actual usage in the cabinet

**Goal / Expected behavior:** the existing cabinet shows truthful current/historical usage independently of access reads.

**Repository / Read before implementation:** Portal; [paid panel](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/web/src/features/billing/PaidProductAccess.tsx), [refresh hook](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/web/src/features/billing/use-paid-access.ts), bounded read composition.

**Implement / reuse:** add `/api/paid-usage` with its own bounded Kernel HTTP resources. Reuse the existing verified-email billing-session guard, derive scope/user on the server and use no-store success/refusal responses. Perform remote I/O outside SQL, validate tuples and recheck local revision. Preserve the independent local `/api/paid-access` pool/thread/cancellation ownership while Kernel usage is slow or unavailable. Reuse generated DTOs, session-operation guards and visibility refresh.

Show successful used, reserved, remaining, available and read time. Distinguish current/historical, unobserved/unavailable and temporary busy/final exhaustion. Do not invent reset dates.

**Verification:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_paid_usage_postgres.py
npm --workspace @anytoolai/web run test:components -- tests/components/any766-paid-usage.test.tsx tests/components/any765-paid-access.test.tsx
PATH="$PWD/.venv/bin:$PATH" npm run generate
PATH="$PWD/.venv/bin:$PATH" npm run generate:check
```

Cover revision changes, partial tuple failure, outages, blocked history, new cycles and late account responses. Reject inactive/unverified/foreign identity, verify no-store responses, and prove local paid-read availability under usage timeout, cancellation and capacity pressure.

**Expected completion:** cabinet values match authenticated Kernel readback while local access remains usable during usage outage.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 10. Follow Portal API/web instructions and the common protocol. Reuse generated contracts, bounded resources, session guards and Bundle 3. Implement separate truthful usage reads and presentation. Run focused checks and generation, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Display actual Kernel usage in the cabinet`

### Step 11 — Verify the assembled integration locally

**Goal / Expected behavior:** both real applications work together locally through browser and HTTP with separate PostgreSQL state. Confirm that a test user with committed paid access can execute the selected products and see correct results/usage. This is the current plan's combined integration acceptance, not parent ANY-504 stage 11.

**Repositories / Read before implementation:** both Compose/runners and [metering cutover](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/infra/deployment/execution-metering-cutover.md).

**Implement / reuse:** add optional peer-network/config inputs and the Kernel development PostgreSQL named-volume correction. Pin the selected PostgreSQL 18 patch/digest without changing database major versions or abandoning retained volumes.

Add a bounded Portal-owned joint harness under `tools/joint_paid_runtime/`.
Reuse existing process/composition/test seams; launch real APIs/workers with
separate disposable PostgreSQL databases and TCP HTTP. Start from confirmed
persisted test purchase/access facts through existing application/domain paths.
Use real Portal identity/session and service authentication, temporary enabled
product profiles, isolated purchased quantities and deterministic provider/LBX
substitutes. Never replace Portal–Kernel transport or trusted identity with test
principal overrides in the joint acceptance. No remote server is needed.

**Verification — Portal:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_any766_joint_http_postgres.py
npm run test:e2e -- any766-kernel-launch.spec.ts any766-paid-execution.spec.ts
```

The new browser cases use the harness-provided Portal/Kernel origins and run existing desktop/mobile projects.

Verify all service directions, session launch, seven scenarios, paid events, replay, exhaustion, revocation, last-unit competition, same-cycle recovery, new cycle and process restart. Regress selected-digest/historical replay and product-scoped primary decisions while an unrelated product is incomplete; financial admission must retain its customer-wide requirements. Recreate containers and compare retained identities, purchases, floors and usage. Collect accessibility evidence for changed Portal surfaces.

**Invariants:** no shared database, global cleanup, real financial mutation or new orchestration framework.

**Expected completion:** actual local browser/HTTP/PostgreSQL evidence proves the integration and its failure/recovery behavior on pinned sources. Provider/LBX substitutes remain labelled; live payment, remote staging and production acceptance are deferred to ANY-767.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 11, the assembled local integration acceptance. Follow both runtime instruction sets and the common protocol. Reuse existing runners and independent Compose projects; add the bounded joint harness and required storage/network corrections. Exercise real Portal/Kernel APIs, sessions, service authentication, PostgreSQL and browser journeys from committed test purchase/access state; only external LBX/AI responses may be substituted. Run the stated checks, fix introduced failures and report evidence by source. No remote host or live purchase is needed. Do not stage, commit, push, merge, rebase, switch branches, publish or deploy. Preserve unrelated volumes. Escalate only an unresolved material decision.

**Proposed commit:** `ANY-766 - Prove durable joint Portal Kernel execution`

### Step 12 — Prepare minimal builds and installation instructions

**Goal / Expected behavior:** the Portal and Kernel changes needed to build and
later install the selected versions are locally verified and ready for PR review.
A remote server and registry credentials are not prerequisites.

**Repositories / Read before implementation:** both existing Dockerfiles, production
Compose files, CI, runners and runbooks; Section 3.7; Kernel profile activation and
metering cutover safeguards.

**Implement / reuse:** follow Section 3.7. Add component-selectable build/publish
workflow definitions and the minimal app-owned image overrides/runner support.
Keep frontend/backend independent, pin selected image versions in ordinary Compose
inputs and document source/migration/wire/build-origin compatibility in existing
runbooks. Preserve the Portal purchased-document reader floor and Kernel profile
path/fingerprint/activation rules. Control scripts may use matching reviewed
checkouts; no portable installer bundle, universal selection schema or new release
manager is required. Document parameterized future installation/update commands.

**Verification — Portal:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_image_deploy.py
```

**Verification — Kernel:**

```bash
./.quick-check-venv/bin/python -m pytest -q tests/test_image_deploy.py tests/test_runner.py
```

Use local configurations/images and disposable resources to verify the selected
pair, build-time origins, migration failure handling, Kernel profile generation
and activation, backend/data retention and frontend-only updates. Check or
explicitly exclude unsupported image/reader combinations, including old Portal
readers with unchanged migration heads. Reuse valid Step 11 evidence where the
sources/configuration are unchanged; rerun affected cases after packaging changes.

Validate workflow/configuration locally and rehearse the documented image-based
installation commands on a disposable local stack. Record actual local image IDs
or available digests and build inputs. Do not dispatch registry publication or
contact a staging server to satisfy this step. Missing remote inputs are deferred
ANY-767 work; an unverified essential local build/install path remains incomplete.

**Expected completion:** minimal build and installation changes pass their local
checks, the chosen configuration can be reproduced and existing runbooks explain
how to install/update it after review. Proceed to the PR readiness checklist;
remote publication/deployment is outside this plan.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 12. Follow both delivery instruction sets, Section 3.7 and the common protocol. Reuse Dockerfiles, Compose, runners and existing deployment safeguards; implement only minimal component builds, image inputs and installation commands/runbooks. Preserve frontend/backend independence, purchased-document reader compatibility, Kernel profile activation and data. Validate and rehearse locally, rerun affected integration checks and report actual results. Do not create a portable release manager or require remote server/registry inputs. Do not stage, commit, push, merge, rebase, switch branches, publish or deploy remotely. Keep remaining external acceptance in the Section 7 handoff.

**Proposed commit:** `ANY-766 - Prepare minimal image builds and installation`

### PR readiness checklist

- [ ] Inspect the final paired diff against the local DoD; resolve confirmed
  in-scope issues. Record the source revisions and evidence from Steps 11/12 and
  applicable Section 6 checks; rerun only checks invalidated by later changes.
- [ ] Keep affected as-built docs, generated contracts and existing runbooks
  accurate. Document supersession of obsolete ANY-286/287 access-check direction;
  do not edit external tickets without authorization.
- [ ] Prepare concise PR descriptions and the Section 7 handoff: behavior,
  actual validation, limitations and deferred ANY-767 deployment inputs. External
  PR review/corrections precede publication and server installation.

This checklist adds no numbered implementation step or second full acceptance
campaign. Completing it establishes local readiness for PR review, not approval,
remote deployment or production readiness.

## 6. Final Verification & Review

Run focused checks during implementation and the applicable broad checks on the
assembled local pair in Step 11, plus build/install checks in Step 12. Reuse valid
results in the PR checklist; do not repeat an unchanged full suite just for the
handoff. After PR review corrections, rerun affected checks before rollout.
Configure these runs for the isolated local test environment, with external
LBX/AI responses controlled as in Step 11.

**Portal:**

```bash
PATH="$PWD/.venv/bin:$PATH" npm run check:fast
PATH="$PWD/.venv/bin:$PATH" npm run check
PATH="$PWD/.venv/bin:$PATH" npm run generate:check
./.venv/bin/python scripts/check_kernel_manifest_contract.py --local
npm run test:e2e -- any766-kernel-launch.spec.ts any766-paid-execution.spec.ts session-races.spec.ts
```

**Kernel:**

```bash
./.quick-check-venv/bin/python scripts/agent/runner.py quick-check
./.quick-check-venv/bin/python scripts/agent/runner.py postgresql-check
./.quick-check-venv/bin/python scripts/agent/runner.py full-check
./.quick-check-venv/bin/python scripts/agent/runner.py validate-docs
./.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check
./.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance --portal-root /home/wstanley/www/work_unirec/runtime-research/payments-portal --portal-python /home/wstanley/www/work_unirec/runtime-research/payments-portal/.venv/bin/python
```

Run applicable atoms/Compose smoke gates for changed runtime paths. PostgreSQL verification requires actual disposable databases; skipped tests never satisfy the gate.

The final review must cover:

- Metric/unit/action binding and shared-counter meaning.
- Immutable terms, historical compatibility and renewal retention.
- Delegation, browser custody/recovery, identity-generation changes and paid events.
- Floor/cache/invalidation ordering, expiry/skew and post-wait refusal.
- Exact-N acknowledgement and durable exhaustion deduplication.
- Existing ANY-507 success/release/replay/recovery under paid authority.
- Owned historical result access and original-bucket finalization.
- Usage tuple/revision validation and honest unavailable states.
- Locally verified image/profile/data compatibility and independent updates.
- Actual local HTTP, PostgreSQL and browser evidence on the pinned sources.

Record **historical**, **new local**, **synthetic fixture/provider**, **real two-service HTTP**, **live LBX**, and **deployed/production** evidence separately.

The local result includes paid client events, usage/exhaustion delivery,
owner-bound browser recovery and minimal verified build/install support. Current
completion is recorded in Section 2. Section 3.8 separates local readiness from
future sales, external-service and deployment acceptance.

## 7. Local result and handoff to ANY-767

Deliver one compact handoff for PR review and parent ANY-504 stage 11:

- Paired source revisions, predecessor corrections and consumed ANY-507/814 versions.
- Migration heads/order, purchased-document reader floor, locally verified image IDs/digests and build inputs, supported configuration and installation/update/recovery commands.
- Contract versions/checksums, session/service-auth setup, permissions and implemented admission/readback/delivery attachment points.
- A correlated local trace: committed test purchase/access state → actual Portal snapshot HTTP → authenticated Kernel execution → accessible result → durable usage → cabinet display.
- Applicable replay, last-unit, revocation, events, same-cycle/rollover, restart and independent-update evidence, with its exact sources/configuration and limitations. Label external substitutes; do not claim a real payment or deployed acceptance.
- Remaining external inputs and owners: sales quantities/LBX associations, supported paid test purchase, server/operator, domains/TLS, registry access, secrets, SMTP, AI configuration and backups.

After PR review and corrections, **ANY-767 (parent ANY-504 stage 11)** owns actual
registry publication and staging installation of the reviewed versions, real
LBX/SMTP/provider wiring and the complete registration → offer/consent → test
payment → reconciliation → paid product/result/usage journey. It also owns remaining
natural-renewal/deployment acceptance and production rollout.

Reuse valid local and predecessor evidence; do not repeat completed research or
the entire unchanged local matrix. Verify the actual installed configuration,
remaining real-service lifecycle cases and behavior affected by review changes.
Missing remote inputs defer this later acceptance and do not prevent completion
of ANY-766's local plan. Missing core identity, enforcement, delivery, usage or
local browser/HTTP proof remains incomplete ANY-766 work.
