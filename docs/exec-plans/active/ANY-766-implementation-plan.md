# ANY-766 — Portal–Kernel Paid Execution Integration

Status: **STEPS 1–4 COMPLETE; REV-3 lock-order defect resolved; paid runtime integration and later gates remain**

Date: **2026-11-09**

Issue: [ANY-766](https://linear.app/paveldik/issue/ANY-766)

- State: active
- Owner: mixed — Portal and Kernel execution owners
- Last updated: 2026-11-10
- Review date: 2026-11-10
- Next action: Step 5 production allowance derivation and V2 snapshots, only when separately requested. Step 4 REV-3 is resolved; Steps 5–14 have not been executed.
- Blocker: none for completed Steps 1–4. Step 4 PostgreSQL checks, including the REV-3 concurrency correction, pass under explicit local test-db/temporary-migration authorization; the historical Step 3 review selection was not rerun. Sales, live-proof, staging and production conditions apply only to their dependent actions under Section 3.8. The inherited broader Kernel permission-test limitation remains recorded below.

This replaces the previous proposal completely. PLAN-1 through PLAN-5 are addressed below.

Destination: `/home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md`.

Plan materialization is **COMPLETE** in both prepared repositories. Portal's file at the destination above is authoritative. Kernel's byte-for-byte working copy is `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform/docs/exec-plans/active/ANY-766-implementation-plan.md`. Update Portal first and synchronize the Kernel copy after every subsequent progress update, before handoff.

The user selected the two clones inside `/home/wstanley/www/work_unirec/runtime-research` as the active ANY-766 workspace. This supersedes the earlier workspace selection outside that directory. The earlier prepared clones were left unchanged and are not the active execution pair for this task.

The latest user-saved revised plan was already present at the authoritative Portal path above as an untracked file. Its original SHA-256 was `58871cc2838d422161251201e8a5c7870b3aba0e9a2c25b3ab4b7b077ca92a4a`; its exact pre-preparation bytes are preserved at `/tmp/ANY-766-user-saved-revision-58871cc2838d.md`. It was updated in place with the initial preparation results and shared execution rules; Section 2 now records the subsequent predecessor-base refresh. The older plan outside the repositories remains historical context. Materialization and branch preparation did not perform Step 1's contract work. The execution clarification in Section 3.1 removes the incorrectly added preliminary contract-approval requirement.

## 1. Goal & Final Expected Outcome

An authenticated Portal user with confirmed paid access can launch the selected Kernel products through the real browser and HTTP boundaries. Kernel verifies the existing Portal identity through scoped session delegation, obtains current access authority, resolves the scenario’s declared metric and passes the exact purchased allowance into ANY-507.

Acceptance commits the session/job and reservation atomically. One valid, durably saved, user-accessible final result consumes one unit. Terminal failure without that result releases the reservation. Replays return the original execution and bucket without another reservation or debit. The cabinet shows Kernel’s actual usage, reservations, remaining quantity and available capacity.

The user approved these production identities and shared counters:

- ProposalAI: `proposal_ai.generate_v1` → `proposal_ai.generations`, unit `generation`.
- Client Update Writer: `update_v1`, `prepaid_request_v1`, `reply_draft_v1` → `client_update_writer.messages`, unit `message`.
- Brief Decoder: `brief_decoder.decode_v1` → `brief_decoder.analyses`, unit `analysis`.
- Acceptance Builder: `draft_v1`, `check_v1` → `acceptance_builder.results`, unit `result`.

Counters are independent between products. Each successful scenario result consumes one unit. Internal workflow steps, provider calls and retries consume no additional units.

Existing test metrics and history retain their identities and TEST-ONLY meaning. Commercial quantities, exact LBX associations and sales enablement require separate owner approval.

ANY-766 delivers both applications’ integration, actual paid execution, truthful usage, durable delivery, image packaging and the selected staging implementation. ANY-767 receives this result for the complete billing journey, remaining natural-renewal verification, final deployment acceptance and production rollout.

## 2. Current State & Reusable Implementation

### Development bases and predecessor corrections

**Current re-preparation checkpoint — 2026-11-09 (Asia/Ulaanbaatar).** The user requested re-preparation of the existing runtime-research pair after ANY-715 merged, then explicitly authorized incorporating fresh predecessor commits after validation found the runbook-test follow-up. Numbered implementation steps have not started. This section records the latest actual bases and supersedes earlier preparation base selections.

- Portal repository: `/home/wstanley/www/work_unirec/runtime-research/payments-portal`; current local branch `ANY-766`.
- Fresh `git fetch --no-tags origin` verified Portal `origin/main` at **`576c2d88cf902ae7b5abddbc1e4f438f6c27366e`**, the merge of [ANY-715 PR #161](https://github.com/gushinets/payments-portal/pull/161), merged on 2026-11-09. [ANY-765 PR #164](https://github.com/gushinets/payments-portal/pull/164) remains open, based on that main, with head **`7f985031034f45fde0203f710eb64283cd086e86`**. PR state/ref metadata was freshly checked through GitHub; no current CI or live-acceptance PASS is inferred.
- Portal's actual refreshed ANY-766 base is **`7f985031034f45fde0203f710eb64283cd086e86`**, identical to refreshed `origin/ANY-765` and including merged ANY-715/main. There are zero ANY-766 commits above that base. The first re-preparation moved the empty own-change range with `git rebase --autostash --onto d86a31732faeb1f383610f78aa85ecd703b2ab6f ac8743ff35c5cfaf0fdaf108fa89ad5e71bf49cd ANY-766`. The latest authorized refresh used `git merge --ff-only 7f985031034f45fde0203f710eb64283cd086e86` from `d86a317`, without a new stash or merge commit. The untracked plan and existing documentation-index change were preserved exactly. No old ANY-715/765 patches were replayed onto main.
- The initial `ac8743ff35c5cfaf0fdaf108fa89ad5e71bf49cd` and rebased `2948010` trees are identical. Subsequent content changes are the `d86a317` scoped-primary/selected-digest fixes and documentation handoff, followed by `7f98503` runbook/test alignment. The latter changes only `test_billing_subscription_reconciliation.py` and the billing operations runbook: it normalizes whitespace in the documentation contract test, checks the scoped-primary/customer-wide distinction and states the existing six-hour trust formula. Application code, migrations and wire contracts are unchanged from `d86a317`.
- Kernel repository: `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform`; current local branch `ANY-766`. Fresh `git fetch --no-tags origin` left its actual base **`72ff15bc0b77903c87aa39f7b10186dccc556d09`**, exactly refreshed `origin/main`. No Kernel branch move was necessary; delivered ANY-507/814 remain included.
- Both repositories have one registered worktree. Both ANY-766 branches remain local with no upstream or push. Existing local predecessor/main branches were not moved. The initial state contained only the Portal plan/index preparation changes and the Kernel plan copy; no uncommitted application work or ANY-766 application commits had to be preserved or ported.
- Before the first re-preparation, both plans, the Portal index file, patches and branch/status records were backed up under `/tmp/any766-reprepare-owg__1m_/` with plan SHA-256 `021e7750cee1faa6a20ca3b9cd61b541242635482ac1d258519fff79e5e082d4`. Before the latest fast-forward, the same preparation artifacts were backed up under `/tmp/any766-base-refresh-b4a8s56r/`; both plans then had SHA-256 `26002a4b7f8d3dd86ec36acbf8420c4414f27419f433f374ee11db167724dfe6`. The initial user-saved snapshot also remains at the path recorded above.
- Actual migration heads remain Portal **`20261031_0006`** and Kernel **`0018`**, determined from revision/down-revision declarations. No database, migration, service, deployment, secret or environment configuration was changed by this re-preparation.

### Re-preparation progress and evidence

- [x] **PASS — existing work preserved and both remote-ref sets refreshed.** GitHub confirms ANY-715 merged and ANY-765 open at the SHAs above; Kernel main remains unchanged.
- [x] **PASS — Portal ANY-766 base refreshed to `7f98503`, Kernel ANY-766 base retained at current main.** Both authorized preparation refreshes preserved existing work. The earlier automatic stash was reapplied; the latest fast-forward required no stash. No unresolved paths, residual stash, new ANY-766 implementation, staged changes, commits or pushes were introduced.
- [x] **PASS — repository instructions and updated ANY-765 handoff inspected against source.** Section 2's alignment below records the consumed corrections and the remaining documentation ownership discrepancy.
- [x] **PASS — Portal environment diagnostic:** `PATH="$PWD/.venv/bin:$PATH" npm run repo:doctor`. Worktree `4973adb2` / Compose project `payments-4973adb2` and existing isolated ports remain usable; no workloads were started.
- [x] **PASS — Kernel environment diagnostic:** `./.quick-check-venv/bin/python scripts/agent/runner.py doctor`. Required tools/modules and the optional Docker client probe passed; no workloads were started.
- [x] **PASS — current-pair documentation:** Portal `PATH="$PWD/.venv/bin:$PATH" npm run docs:check`; Kernel `./.quick-check-venv/bin/python scripts/agent/runner.py validate-docs`. These are fresh results in runtime-research after the base/plan refresh.
- [x] **PASS — Portal inherited unit and affected reconciliation/runbook regressions on `7f98503`:** `./.venv/bin/python -m pytest -p no:cacheprovider -q apps/api/tests/test_any765_purchase_terms.py apps/api/tests/test_paid_access_policy.py apps/api/tests/test_paid_access_models.py apps/api/tests/test_billing_subscription_reconciliation.py` — **157 passed**. This includes the previously failing runbook contract test, which the earlier 65-case selection did not cover. These DB-free results do not establish PostgreSQL, browser or live acceptance.
- [ ] **FAIL — existing Kernel cross-user activation test, environment limitation:** `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user` was reproduced independently and fails because `sudo -n -u nobody` reports `sudo: a password is required`. System permission policy was not changed. Kernel config, architecture, docs and generated-doc checks passed during validation. The broader `quick-check` was interrupted after the reproduced failure and is not a full PASS; remaining cases are NOT_RUN. This limitation does not prevent Step 1 document/contract work, but the affected permission check needs a supported execution environment before its verification can pass.
- [x] **PASS — preparation integrity:** both branches/HEADs match the recorded bases with zero ANY-766 commits; Portal main is an ancestor of its refreshed base; both indexes are empty; no unresolved files, residual stash or active rebase exist. Portal tracked changes remain the one documentation-index addition, with this plan untracked; Kernel changes remain this untracked plan only. `git diff --check`, all pinned source-path existence checks and byte-for-byte plan equality pass. At that re-preparation checkpoint, all 14 step headings and the B10/delegation/admission decisions were unchanged; only predecessor preservation requirements and execution context were refined.
- [x] **COMPLETE — Step 1 plan materialization only.** Both repositories already had the complete revised plan; this refresh updates the same authoritative file and mirror rather than starting a numbered implementation step.
- **Historical preparation boundary:** Step 1 contract changes, schemas, fixtures and tests were NOT_RUN during re-preparation. They are now COMPLETE under the separate Step 1 execution checkpoint below; Steps 2–14 remained NOT_RUN at that checkpoint. Step 2 is subsequently completed below. Re-preparation itself did not complete a numbered implementation step.
- [ ] **NOT_RUN — broad application/PostgreSQL/browser/image/live-LBX/staging/production acceptance.** Re-preparation verifies the selected bases, environment and documentation; it neither starts workloads nor re-certifies inherited runtime behavior. Previous results remain dated evidence for their recorded snapshots.
- **Step 1 availability:** preparation originally left contract work READY without a separate preliminary approval; the subsequently requested Step 1 is now COMPLETE. Sales, live positive proof, staging and production retain their separately scoped conditions.

Initial preparation created both local ANY-766 branches from Portal `ac8743ff35c5cfaf0fdaf108fa89ad5e71bf49cd` and Kernel `72ff15bc0b77903c87aa39f7b10186dccc556d09`, materialized the same plan in both repositories and added Portal's documentation-index entry. Its diagnostics, documentation and integrity checks passed at that earlier checkpoint. Those base-selection facts are historical; the refreshed bases and new check outcomes above are current. The earlier prepared clones outside runtime-research are not the execution pair and remain unchanged by this re-preparation.

Development may proceed above the verified ANY-765 head while that PR is reviewed; its merge is not a prerequisite. After ANY-765 merges, transfer only ANY-766's own changes onto accepted main, preserving intervening corrections, under a separately authorized base refresh. Repeat affected migration, recovery, contract, concurrency and browser checks on the resulting pair. Extend the actual migration heads; do not rewrite existing migrations.

### Consumed ANY-765 handoff and preservation requirements

Read the [current Step 10 producer handoff](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/docs/engineering/billing-background-operations.md#step-10-handoff--any-765) and [completed review/evidence record](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/docs/exec-plans/completed/ANY-765-implementation-plan-refactor.md). “Step 10” in that handoff means the whole program ticket ANY-766, not only this plan's internal Step 10 cabinet work.

- Preserve the inherited trust-observation provenance, paused automatic UNKNOWN recovery, explicit GET-only recovery, informational `block_to_close_days`, metric admission before new financial sends, isolated paid reads and cancellation ownership.
- Keep selected-meaning `confirmation_digest()` separate from full-source/audit identity (`source_digest`, full `kernel_manifest_version`, technical `digest`). Another product or global source-version change cannot invalidate unchanged selected consent. Historical v2 full-audit-digest acceptances remain readable and replay the exact saved buyer digest; v1 receives no invented technical quantity. Steps 3/11 must preserve these regressions.
- Primary selection uses complete relevant product inventory and original owner/version/fence proof. Financial CREATE admission and `restore-original`/`bind-original` retain customer-wide completeness. Steps 5/11 must preserve independence from unrelated incomplete products without weakening financial admission.
- Preserve the sole whole-user paid writer, atomic revision/causal observation/outbox/deadline commit, finite source trust, immutable same-cycle allowance identity and calendar precision. Current local calendar documents are internal evidence, not the target HTTP snapshot contract. B10 and exact-N delivery/ACK remain ANY-766 implementation work.
- Current `/api/paid-access` requires an active verified-email session, derives scope/user server-side, is local and read-only after identity bookkeeping, and retains its reserved DB/thread budget and cancellation ownership. Step 10's separate usage API must preserve those authorization and availability guarantees.
- Reader compatibility is stricter than the unchanged migration head: pre-fix Step 9 binaries cannot read newly accepted selected-digest purchases. Step 12 release validation, Step 13 recovery and Step 14 handoff must record this format-compatibility floor; same migration head does not authorize rolling back to an older reader.
- At preparation, the refreshed handoff and Portal integration map still assigned production vocabulary to ANY-711. The [2026-11-09 ANY-766 scope clarification](https://linear.app/paveldik/issue/ANY-766) explicitly assigns selected production declarations/bindings to ANY-766 and leaves ANY-711 Done for its delivered manifest/TEST-ONLY baseline. **Step 1 now aligns both statements** without reopening ANY-711 or adding a dependency on new work there. Commercial quantity/LBX/sales approval remains separate.

### Reuse and actual gaps

- ANY-711 supplies real manifest delivery, independent consumer validation, fixture ownership and directional service authentication.
- ANY-765 supplies immutable accepted evidence, primary selection, calendar classification, stable allowance identities, semantic revisions, deadlines and atomic invalidation outbox updates.
- Production terms remain missing: current technical terms and positive allowance materialization are development/SIMULATED-oriented.
- ANY-507 supplies paid owner partitioning, replay, reserve/finalize/release, recovery and readback. It already uses the required immutable allowance tuple.
- Kernel HTTP still needs trusted paid identity and ownership protection. Its existing `ClientEventService` also rejects sessions without a verified guest; this must be extended for authenticated paid events.
- Portal invalidation transport and Kernel exhaustion delivery remain missing.
- Existing independent Compose projects, runners, migration services and Kernel profile activation are reusable. Image deployment must remove host application-build and managed-venv requirements.

Previous QA and CI results remain historical evidence. This revision used static inspection and checked the referenced existing paths. No new application, PostgreSQL, browser, live-LBX or deployment acceptance is claimed.

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

### 3.7 Runtime, images and compatibility

Ownership:

- Portal team: Portal code, migrations, embedded worker, images, app Compose and runner.
- Kernel team: Kernel code, migrations, worker, images, profile/activation and runner.
- Infrastructure owner assigned by Mikhail: host, domains/TLS, shared ingress/network, registry access, secrets and backups.

App-owned image Compose files:

- Portal: `deploy/compose.images.yml`.
- Kernel: `infra/compose/docker-compose.images.yml`.
- Both: `.github/workflows/publish-images.yml`.

Keep neutral joint-deployment templates in Portal `deploy/joint/`. The operator assembles their deployment copy under `runtime/portal-kernel/`; a new infrastructure repository is not required.

Use independent Compose projects, private databases, migration services and retained volumes. Only necessary peer callers join the integration network, including the Kernel exhaustion worker.

Build frontend/backend independently through manually dispatched GitHub Actions and publish immutable GHCR digests. Portal API/migration share one image. Kernel API/worker form one backend release from the same source revision. Keep environment-specific frontend builds for existing origins/base paths.

Each component artifact includes version-1 release metadata:

- Application/component, source SHA and immutable image digest(s).
- Backend migration head.
- Provided/required contract versions.
- Frontend-required or backend-provided web API compatibility IDs.
- Frontend build origins/base path.

Initial web compatibility IDs are `portal-web:any766-v1` and `kernel-web:any766-v1`. A selected frontend requires an ID explicitly provided by its backend. Older artifacts without this metadata are incompatible. A breaking API change introduces a new ID; retain an old ID only with its compatibility tests.

A selected `selection.json` identifies all four components and peer contract requirements. Validate metadata, web build origins, migration selection and peer compatibility before mutation. Do not infer compatibility from matching Git SHAs. Record the Portal purchased-document reader compatibility floor as well as migration heads: pre-fix Step 9 binaries cannot consume new selected-digest acceptances even though both use `20261031_0006`. Reject an incompatible rollback; do not rewrite accepted history to enable it.

Extend both runners with:

```text
deploy-images --release-dir ... --env-file ... --component backend|frontend|all
```

The release bundle includes matching app-owned runner/helper files, Compose and metadata. Image mode needs Docker Compose and Python 3.12, without a host application checkout, application dependency installation or source build.

Frontend-only deployment pulls/recreates only the frontend with `--no-deps`; it does not migrate, regenerate profiles, stop backend services or touch volumes.

Backend deployment preserves lifecycle locks, quiesce/drain, migration-before-start, activation and readiness. A migration failure keeps admission closed. Old binaries are not resumed against an incompatible schema; recovery uses the existing verified backup procedure.

**Kernel deployment profile**

- Generate the candidate profile inside the selected API image, overriding its normal entrypoint.
- Bind the operator-owned host profile root to `/release-profile`; generate `/release-profile/<candidate>/`.
- Preserve the generated manifest and its fingerprints.
- Derive host Compose mount paths explicitly from the selected host root/candidate. Do not interpret manifest container paths as host paths.
- Check the unmodified source fingerprint inside the selected API and worker images before profile mounts.
- Mount candidate products/manifest read-only into their existing runtime locations, run both effective-profile checks and activate the existing shared marker only after readiness.
- Parameterize existing lifecycle helpers with the release state root; do not add another activation system.
- Retain the previous profile until successful activation. Frontend-only updates preserve the active profile.

### 3.8 Commercial and operational gates

Contract formalization and consistency checks belong to Step 1. No additional Mikhail/designated-reviewer approval of Sections 3.3–3.6 is a prerequisite for that step or for implementation following the accepted strategy.

- **Base re-preparation — COMPLETE for this request:** Section 2 records the actual refreshed bases, diagnostics, documentation/unit checks and preservation evidence. ANY-715 is merged; verified ANY-765 may remain under review during development. Preparation did not execute Step 1 and does not authorize later Git integration.
- **Sales:** owner approves quantities, LBX account/tariff/service/period associations and enablement before publishing real sale configuration.
- **Live positive proof:** an authorized supported paid test purchase and authoritative eligible cycle must exist. Otherwise live acceptance remains BLOCKED.
- **Staging:** infrastructure owner supplies host/operator, domains/TLS, secret delivery, GHCR access, data roots, backups, SMTP, approved AI configuration and deployment authorization before Step 13.
- **Production:** ANY-767 owns production rollout.

Missing operational inputs do not block independent implementation. A failed gate prevents its dependent action; it does not turn synthetic evidence into live acceptance.

## 4. Functional DoD & Acceptance Coverage

- Known-user empty revision zero is read-only; refusal creates no job, reservation or debit.
- All seven selected scenarios use the approved metric; shared product counters behave consistently.
- A real Portal–Kernel execution produces one accessible result and one debit; cabinet and Kernel readback agree.
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
- Independent image updates preserve databases, usage and active profiles; incompatible selections are refused before mutation.

Steps 2–10 implement these behaviors. Step 11 proves actual HTTP integration, Step 13 proves the selected staging release, and Step 14 closes review and handoff.

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
9. Portal remains the authoritative plan. Update its progress and evidence first, then synchronize the entire file byte-for-byte to Kernel at the path above after every progress update and verify equality before handoff. Do not maintain divergent plan copies.

Repository roots:

- Portal: `/home/wstanley/www/work_unirec/runtime-research/payments-portal`.
- Kernel: `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform`.

Commands below run from the indicated root. New test targets are planned additions and must be created by their step.

Use Portal’s root `.venv` and Kernel’s `.quick-check-venv`. Bootstrap through existing setup commands if needed; do not install into system Python. Portal root npm aliases need a command-scoped PATH:

```bash
PATH="$PWD/.venv/bin:$PATH" npm run check:fast
```

Portal PostgreSQL cases require its isolated test server/configuration. Kernel cases require `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` pointing to a maintenance database for disposable test databases. Do not print credentials. Skipped database cases are NOT_RUN, never PASS.

All prompts below require the complete authoritative plan file and this common protocol, including Russian communication with the user. Step 1 plan materialization is already complete; a request to execute Step 1 starts its remaining contract formalization and validation work without a separate approval prerequisite. If the plan file is absent or ambiguous, report the exact problem instead of reconstructing it from the historical external file.

After each code step, run its focused checks and applicable non-fixing lint/type/architecture checks. Fix failures introduced by the step. Broad suites run on the assembled result.

### Step 1 — Formalize and validate Portal–Kernel contracts

**Preparation checkpoint (2026-11-09): plan materialization COMPLETE; predecessor-base re-preparation recorded in Section 2.** Actual refreshed bases, predecessor corrections, migration heads and shared execution rules remain unchanged. The user subsequently requested Step 1; its contract work and technical consistency review are **COMPLETE** at the execution checkpoint below. No runtime implementation or later step is included.

#### Step 1 execution checkpoint — 2026-11-09

- [x] **PASS — prepared state verified and preserved.** Portal remains local branch `ANY-766` at `7f985031034f45fde0203f710eb64283cd086e86`; Kernel remains local branch `ANY-766` at `72ff15bc0b77903c87aa39f7b10186dccc556d09`. Revision/down-revision inspection confirms unchanged migration heads `20261031_0006` / `0018`. Existing plan/index preparation work was retained; indexes remain empty. No staging, commit, push, merge, rebase, branch switch, reset or stash occurred.
- [x] **PASS — canonical target formalization.** Both Portal canonical designs now have explicit dated ANY-766 sections covering Sections 3.3–3.6, with scoped precedence over the preserved September text. V2 removes UTC period fields, includes unit, retains finite authority and freezes the exact ANY-507 tuple. Identity/recovery, coherence/admission/paid events, exact-N delivery, usage/exhaustion and cabinet authorization/capacity are specified as future runtime work.
- [x] **PASS — producer/consumer artifacts.** The [paired target bundle](../../contracts/portal-kernel-paid/README.md) contains 12 reviewed JSON schemas, an explicit route-host/payload-owner/permission/status index, 25 positive and 126 negative payload cases (117 before the REV-1 follow-up below), six valid-shape contextual rejection cases, and clock/ACK/exhaustion/usage-tuple vectors. Portal owns identity, snapshot and invalidation; Kernel owns usage/exhaustion. Both directories, including SHA256SUMS and README, match byte for byte. Existing manifest V1 fixtures, TEST-ONLY identities and semantic digest pins are unchanged.
- [x] **PASS — independent offline validation.** Portal has a test-only strict Pydantic oracle and a resolved schema-shape comparison. Kernel uses JSON Schema with strict integer handling and independent semantic/context checks, plus existing ANY-507 PaidAllowance/readback compatibility. Neither imports peer code or adds a runtime dependency. Cases include known-user empty revisions, unsupported versions, zero/maximum/bool/float/overflow, missing unit/forbidden calendar fields, unknown/foreign usage, ordered completeness, busy versus exhausted, duplicate/historical exhaustion, full-tuple mismatch and PKCE/expiry consistency.
- [x] **PASS — consumed handoff/scope alignment.** The current Linear ANY-766 description was read through the connected read-only tool. Both stale ANY-711 production-vocabulary statements in Portal's consumed handoff/integration map now assign the selected declarations/bindings to ANY-766, preserve ANY-711 Done and retain separate commercial approvals. Kernel's integration map records the new target without rewriting historical observations.
- [x] **PASS — technical consistency review.** Applied Portal correctness/payment-security checklists and Kernel's agent review checklist to the paired change. Checked producer versus host ownership, authority/version precedence, canonical scope, no calendar conversion, no double clock haircut, replay/transaction/ownership rules, observational events, exact-N ACK, durable exhaustion acknowledgement, historical usage and independent cabinet resources. Review corrected identity-request ownership, correlated PKCE fixtures and added shape-valid observed-tuple mismatch vectors. All introduced fixture/oracle/lint failures were fixed; no production code was changed to make tests pass.

Initial Step 1 verification (historical local/offline checkpoint; current REV-1 results follow below):

- **PASS — Portal:** `PATH="$PWD/.venv/bin:$PATH" npm run docs:check`.
- **PASS — Portal:** `./.venv/bin/python -m pytest -q apps/api/tests/test_any766_contracts.py` — **168 passed**, no skips.
- **PASS — Portal:** `./.venv/bin/python scripts/check_kernel_manifest_contract.py --local` — `LOCAL_SPEC_CONFORMANCE=PASS`; its separate `REAL_KERNEL_CONFORMANCE=DEFERRED_NOT_IMPLEMENTED` marker remains unchanged. This command tests the retained local mock/client contract, not new real paid HTTP.
- **PASS — Kernel:** `./.quick-check-venv/bin/python scripts/agent/runner.py validate-docs`.
- **PASS — Kernel:** `./.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check` — generated documentation is current. The optional LiteLLM remote cost-map lookup was unavailable in the restricted environment and used its shipped backup; no generated artifact or dependency was modified.
- **PASS — Kernel:** `./.quick-check-venv/bin/python -m pytest -o addopts='' -q apps/platform-api/tests/test_paid_contract_fixtures.py` — **156 passed**, no skips. The addopts override only restores pytest's visible pass count; it selects the exact planned test module.
- **PASS — applicable static checks:** Portal `npm run architecture:check` with command-scoped venv PATH; Kernel `runner.py validate-architecture`; scoped `ruff check` and `ruff format --check` on all three new Python files.
- **PASS — diagnostics/integrity:** Portal `PATH="$PWD/.venv/bin:$PATH" npm run repo:doctor` and Kernel managed `runner.py doctor`; paired bundle/plan byte equality, migration-head inspection and both `git diff --check` checks. Portal's sandbox-only Docker/loopback attempts initially failed; the read-only doctor and temporary-loopback checker passed outside that restriction. No permanent services or LBX clients were started.
- **NOT_RUN — broader quick/full/PostgreSQL/browser/real two-service suites:** not part of this document/schema/fixture-only step; no runtime/migration/config changes were made. The pre-existing Kernel `sudo -n -u nobody` quick-check limitation in Section 2 remains unresolved and is not relabelled PASS.
- **NOT_RUN — live LBX, publication, staging and production:** no such actions were performed. Section 3.8 gates remain in force; synthetic Q=1 and fixture-shaped secrets approve neither sales nor live authority. Future runtime endpoints and generated web DTOs remain unimplemented.

**Step 1 result: COMPLETE.** Portal's plan remains authoritative and its whole-file Kernel copy is synchronized. Steps 2–14 remained unexecuted at this checkpoint; the subsequent Step 2 checkpoint is recorded below.

#### Step 1 review follow-up — REV-1, 2026-11-09

- **CONFIRMED — test-oracle defect, no runtime impact.** A raw JSON `valid_until: "1794196800"` was accepted by Portal's strict Pydantic oracle as `2026-11-09T04:00:00Z`, while Kernel/schema rejected it. The previous after-conversion UTC check lost the original wire format, and the resolved shape comparison ignored timestamp patterns. The nine new epoch-string regression cases all failed against Portal's pre-fix oracle and passed against the unchanged Kernel oracle.
- **FIXED — raw timestamp parsing and shape comparison.** Every test-only timestamp field now uses one annotated timestamp type that checks the raw UTC RFC3339 pattern before datetime conversion. The same pattern is present in the oracle's JSON schema, and timestamp patterns are no longer excluded from resolved schema comparison. Nullable grant deadlines still accept null. Producer wire schemas and runtime code are unchanged.
- **PASS — paired fixtures and controls.** Nine negative fixtures cover snapshot refresh/expiry, nullable grant deadline, code/delegation expiry, introspection deadline, usage read time, exhaustion time and nested cabinet read time. Both fixture/checksum copies are synchronized. Raw-JSON controls confirm rejection of the reported epoch string and acceptance of UTC `Z`, `+00:00` and fractional-second RFC3339 timestamps.
- **PASS — Portal contracts:** `./.venv/bin/python -m pytest -q apps/api/tests/test_any766_contracts.py` — **177 passed**, no skips; includes the timestamp-pattern schema comparisons and all existing positive/negative/contextual vectors.
- **PASS — Kernel contracts:** `./.quick-check-venv/bin/python -m pytest -o addopts='' -q apps/platform-api/tests/test_paid_contract_fixtures.py` — **165 passed**, no skips, using the unchanged independent validator.
- **PASS — affected static/documentation checks:** Portal scoped `ruff check` and `ruff format --check` on the two changed test Python files; Portal `PATH="$PWD/.venv/bin:$PATH" npm run architecture:check` and `npm run docs:check`; Kernel managed `runner.py validate-architecture` and `validate-docs`; both bundle/plan byte comparisons, checksums and `git diff --check`.
- **NOT_RUN — unrelated runtime/operational verification:** manifest HTTP, generated-doc, broader quick/full/PostgreSQL/browser/live/staging checks were not repeated for this test-oracle/fixture correction. Their prior results remain historical. The inherited `sudo -n -u nobody` limitation remains open. No remote refs were refreshed; local ANY-766 HEADs and empty indexes remain unchanged. No Git integration, financial action or later implementation step was performed.

**REV-1: RESOLVED. Step 1 remains COMPLETE within its offline contract scope.**

#### Local commit authorization — 2026-11-09

The user explicitly requested local commits in both repositories after REV-1 was
resolved. This narrowly overrides the common protocol's no-staging/no-commit rule
for the completed Step 1 changes, preparation artifacts and REV-1 correction.
Use one commit per repository titled `ANY-766 - Define Portal Kernel paid contracts`.
Earlier no-commit/empty-index statements describe their historical checkpoints.
This authorization does not permit push, merge, rebase, branch switching, later
implementation steps or operational actions. Preserve the paired plans and target
contract bundles byte for byte; retain all recorded verification limits.

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

#### Step 2 execution checkpoint — 2026-11-09

**Result: COMPLETE within configuration and manifest-inventory scope.** Only Step 2
was executed. Paired starting/current HEADs remain Portal
`791d41d36d451de30c19f6439be1abd42fde2b8e` and Kernel
`0ff8dfca2763f71214a3eed441e2188191b950c5`, both local `ANY-766` branches,
plus the uncommitted Step 2 diff. No staging, commit, push, branch move, database
migration, deployment or financial operation was performed.

Implemented:

- Added optional nonblank `paid_metric_key` to Core/SDK scenario definitions and
  existing ConfigLoader parsing/reference validation. References must resolve
  within the scenario's product, including when commercial flags are disabled;
  missing/foreign references and incompatible scalar values are rejected.
- Declared all four approved production metric/unit pairs and all seven
  bindings from Section 1. Shared scenarios resolve the same product metric.
  All ordinary product/metric commercial flags remain disabled. Existing
  TEST-ONLY identities, guest policies (including Client Update Writer's absent
  guest quota), Task Finder surfaces and historical runtime data are unchanged.
- Updated the complete current manifest inventory to six products/six metrics.
  The ordinary disabled digest is
  `sha256:359cc0ff7c7bbacb69ba8e0de0444738b46032c846b10a962298bfb8e0d9cf85`;
  the isolated current test-enabled digest is
  `sha256:5a743b1eb5e50ebed25259fb745e6b2dda743f01bd0def1cae77d12e9697aa62`.
  Only the original two TEST-ONLY metrics are enabled in the synthetic profile.
  Portal retains independent current fixture copies. Historical positive,
  digest and negative fixture bytes are unchanged; the former ordinary disabled
  fixture is preserved byte-for-byte as `historical-disabled-manifest.json`.
- Updated the existing manifest conformance harness for the current inventory
  and removed references to Portal's already removed webhook settings. Its
  report distinguishes current inventory from TEST-ONLY enablement. No Portal
  runtime source changed. Updated configuration/contract/integration documents.

Fresh verification (all commands run from their respective repository roots):

- **PASS — Kernel doctor:** `./.quick-check-venv/bin/python scripts/agent/runner.py doctor`.
- **PASS — required focused tests, 160 passed:** `./.quick-check-venv/bin/python -m pytest -o addopts='' -q packages/backend/platform-core/tests/unit/test_config_loader.py apps/platform-api/tests/test_paid_metric_bindings.py apps/platform-api/tests/test_capability_manifest_contract.py`.
- **PASS — config and architecture:** `./.quick-check-venv/bin/python scripts/agent/runner.py validate-configs` and `./.quick-check-venv/bin/python scripts/agent/runner.py validate-architecture`.
- **PASS — related regressions, 179 passed:** `./.quick-check-venv/bin/python -m pytest -o addopts='' -o faulthandler_timeout=60 -q apps/platform-api/tests/test_capability_manifest.py apps/platform-api/tests/test_capability_projection.py packages/backend/platform-core/tests/test_contract_field_compatibility.py packages/backend/platform-sdk/tests/test_contracts_importable.py tests/test_manifest_conformance.py tests/test_validate_configs.py`.
- **PASS — projection/documentation tests, 43 passed:** `./.quick-check-venv/bin/python -m pytest -o addopts='' -q apps/platform-api/tests/test_capability_projection.py tests/test_validate_docs.py tests/test_docs_generation.py`.
- **PASS — real local Kernel → Portal typed-consumer HTTP conformance:** `./.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance --portal-root /home/wstanley/www/work_unirec/runtime-research/payments-portal --portal-python /home/wstanley/www/work_unirec/runtime-research/payments-portal/.venv/bin/python`. Ordinary/test/reordered/material inventories, authentication/scope/rotation, fault recovery, restart, concurrency, poisoned-dotenv isolation and zero storage/provider side effects pass. Its isolated Portal regression subprocess reports **94 passed**. This is actual local TCP HTTP evidence using synthetic test configurations, not paid execution, live LBX or deployed TLS evidence.
- **PASS — Portal consumer regressions, 93 passed:** `./.venv/bin/python -m pytest -o addopts='' -q apps/api/tests/test_kernel_manifest_client.py apps/api/tests/test_kernel_contract_checker.py`.
- **PASS — contract artifacts:** `./.quick-check-venv/bin/python scripts/agent/check_capability_manifest_contract.py --portal-root ../payments-portal`; independent fixture/schema/digest checks and current consumer-copy equality pass. Historical positive byte SHA-256 remains `25f39800090615eeba04cb27ab020332d0cf7cf7250fac6d2e5c38754c89b354`.
- **PASS — docs/generation:** Kernel `./.quick-check-venv/bin/python scripts/agent/runner.py validate-docs`, `./.quick-check-venv/bin/python scripts/agent/runner.py generate-docs` and `./.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check`; Portal `PATH="$PWD/.venv/bin:$PATH" npm run docs:check`. Generation produces no artifact drift.
- **PASS — lint ratchet:** non-fixing Ruff checks pass for changed Python files except the two files with inherited diagnostics. Comparing those and every other changed/new Python file against HEAD gives **25 baseline / 25 current / 0 introduced** diagnostics. **FAIL (inherited) — unrestricted whole-file Ruff** still reports those existing loader/unit-test violations; they were not suppressed or expanded. No new Python typechecking gate was introduced; Core/SDK field compatibility and boundary validation tests pass.
- **PASS — scope/integrity:** diff inspection and `git diff --check` in both repositories; empty indexes, unchanged HEADs/branches, retained historical fixture bytes, current consumer fixtures and byte-for-byte whole-plan equality. Portal was updated first and the entire Kernel copy synchronized.

Resolved verification failures and limits:

- The first new SDK compatibility test incorrectly used `dataclasses.asdict` on
  frozen registry metadata; it now validates from attributes. A pre-existing
  digest mutation test assumed the first product and metric had different
  owners; the expanded inventory exposed that assumption, and the test now
  explicitly selects a different owner. All affected reruns pass.
- The first conformance run exposed the obsolete webhook-settings references
  above; the updated harness passes. Sandbox TCP restrictions caused five
  Portal HTTP-test failures and prevented conformance startup. HTTP checks were
  rerun with approved local-socket access and pass. A combined sandbox ASGI
  regression run stalled and was terminated; it is not counted as a PASS.
  Its focused and related replacements above completed successfully.
- **NOT_RUN — broad quick/full/PostgreSQL/browser/image/live-LBX/staging/production
  acceptance:** outside this configuration-only step. No schema/storage change
  requires a new database test. The inherited cross-user activation permission
  limitation in Section 2 remains unresolved and was not bypassed.
- **BLOCKED — actual sale publication/enablement and operational acceptance**
  retain Section 3.8's owner-approved quantities/LBX associations, supported
  paid purchase and infrastructure/authorization inputs. These do not block
  completed Step 2. Paid identity, enforcement, usage delivery and immutable
  purchased terms remain later steps; no production-readiness claim is made.


#### Step 2 local commit authorization — 2026-11-09

After Step 2 verification, the user explicitly requested local commits in both
repositories. This narrowly overrides the common protocol's no-staging/no-commit
rule for the completed Step 2 changes and their synchronized plan/evidence.
Use one commit per repository titled
`ANY-766 - Declare production metrics and scenario bindings`.
Earlier unchanged-HEAD/empty-index/no-commit statements describe their execution
checkpoints. This authorization does not permit push, merge, rebase, branch
switching, later implementation steps or operational actions. Preserve both
plan copies byte for byte and retain all recorded verification limits.

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

#### Step 3 execution checkpoint — 2026-11-09

**Result: COMPLETE within publication, immutable acceptance and pre-consent UI scope.**
Only Step 3 was executed. Starting/current HEADs remain Portal
`338edf22fbdc9101f25039b49e3a060b87ba32c4` and Kernel
`b9b6c78bf524a613496f1053278c074c4c4554cc`, both on local `ANY-766` branches,
plus this uncommitted diff. Both working trees and indexes were clean initially.
No staging, commit, push, branch change, real association publication, sales
enablement, live LBX call or application-database migration was performed.

Implemented:

- The existing protected CLI requires `--metric-key`, `--unit` and
  `--allowance-quantity` for dry-run/publication. `--quantity` retains its LBX
  commercial service meaning. The shared exact technical-offer value type lives
  in Catalog, avoiding a Catalog dependency on Purchases. Strict integer bounds
  remain 0…2^53−1; bool, float, string, negative and overflowing quantities fail.
- `product-link-v3` pins one fixed-per-cycle technical offer in the existing
  immutable mapping table. Publication validates fresh enabled product/metric
  ownership/unit and the selected LBX offer through existing source clients.
  Configured terms require configured Kernel/LBX provenance. OS principal,
  source deadlines, product-head CAS, offer ownership, history, no-op publication
  and uncertain-commit recovery remain on their original paths.
- `purchased-technical-terms:v2` and `accepted-purchase:v3` pin configured terms,
  mapping identity/revision, account/selection, commercial fingerprint and fresh
  manifest evidence. The final acceptance transaction checks the current head
  and exact published technical binding. `confirmation_digest()` semantics are
  unchanged; selected meaning stays separate from full source/audit digests.
  Unrelated source/manifest changes do not require fresh selected consent.
- Legacy v1/v2 mapping/purchase documents and SIMULATED technical terms remain
  readable without rewriting their fields/digests. Exact historical full-digest
  v2 replay is preserved. Original acceptance replay and uncertain-operation
  recovery run before new-sale I/O. New production purchases require a published
  quantity; legacy history cannot supply an invented production offer. Existing
  subscriptions retain their original accepted quantity after republication and
  through proven subsequent cycles.
- Purchase review and paid-read response contracts now represent both provenance
  values; OpenAPI/TypeScript were regenerated. The UI shows exact quantity/unit
  before consent, labels SIMULATED evidence only when applicable, and resets
  consent after changed terms. The generic limit label is updated in all seven
  catalogs. Runbook, schema reference and Portal integration map are updated.

Fresh verification (repository-root commands):

- **PASS — required API/PostgreSQL selection, 68 passed / 0 skipped:**
  `./.venv/bin/python -m pytest -q apps/api/tests/test_any765_purchase_terms.py apps/api/tests/test_commercial_mapping_postgres.py apps/api/tests/test_any766_purchase_terms_postgres.py`.
  Executed through `/tmp/any766_step3_tests.py`, which uses the repository's
  `canonical_check_environment()`, test defaults and
  `api_test_environment('api-postgres', ...)`, then assigns a unique disposable
  `_tests` database. PostgreSQL 18 was started through
  `./.venv/bin/python scripts/repo.py test-db up` using the already-local image.
  The final HTTP cases use production settings with fully intercepted synthetic
  sources; no real provider endpoint is contacted. Local evidence:
  `.harness/any766-step3-required.log` and `.harness/any766-step3-required.xml`.
- **PASS — related PostgreSQL regressions, 48 cases:**
  `apps/api/tests/test_any765_purchase_terms_postgres.py`,
  `apps/api/tests/test_any709_step1_postgres.py` and
  `apps/api/tests/test_paid_access_terms_postgres.py`, included in the passing
  combined **115-test / 0-skip** run. This covers selected/global-source changes,
  exact saved full-digest replay, legacy history, concurrent publication,
  credentials/origin rotation, uncertain commits and frozen cycle issuance.
  Evidence: `.harness/any766-step3-final.log` and its XML report. The final
  production-legacy rule and production-mode HTTP cases also pass the subsequent
  required 68-test run above.
- **PASS — source, architecture and documentation tests, 304 passed:**
  `./.venv/bin/python -m pytest -q apps/api/tests/test_any709_step1_sources.py apps/api/tests/test_repository_docs.py apps/api/tests/test_architecture.py`.
  Documentation tests were rerun after the as-built map/schema/runbook changes
  (**195 passed**).
- **PASS — web components, 54 passed:**
  `npm --workspace @anytoolai/web run test:components -- tests/components/any766-purchase-terms.test.tsx tests/components/any709-step4.test.tsx tests/components/any765-paid-access.test.tsx`.
  Covers configured/zero/maximum, SIMULATED/unknown history, display before
  consent and fresh unchecked consent after a quantity/revision change.
- **PASS — non-fixing checks:** Ruff check and format check on all **15** changed
  Python files; `npm run lint:web`; `npm run typecheck:web`;
  `npm run test:boundaries:web` (**38 passed**);
  `PATH="$PWD/.venv/bin:$PATH" npm run architecture:check` and `npm run docs:check`.
- **PASS — generation:** `PATH="$PWD/.venv/bin:$PATH" npm run generate` and
  `PATH="$PWD/.venv/bin:$PATH" npm run generate:check`. Existing local Node
  dependencies were copied from a checkout with the byte-identical lockfile;
  nothing was installed or updated.
- **PASS — focused browser rendering:** eight desktop/mobile screenshots of the
  actual `PurchaseTerms` component with repository CSS and synthetic inputs
  (configured Q=7, Q=0, Q=2^53−1 and SIMULATED). All eight axe runs report zero
  violations, no page errors and no horizontal overflow; representative desktop
  and maximum-quantity mobile screenshots were visually inspected. Evidence:
  `.harness/any766-step3-ui/report.json` and adjacent PNGs. This local Vite
  component preview uses a fallback font, not a full Next.js route or two-service
  execution. All browser requests outside loopback were blocked.
- **PASS — Kernel documentation-only scope:** repository doctor; documentation
  validation and whole-plan equality are checked after synchronization. Kernel
  runtime/configuration and both repositories' dependency locks are unchanged.

Resolved verification failures and remaining limits:

- Initial UI tests lost the intl provider on rerender and compared nonbreaking
  spaces without normalization; the corrected tests pass. The updated CLI
  rotation fixture also needed the same configured-source mode after credential
  rotation; its regression now passes.
- Two overlapping pytest processes initially collided on the same disposable
  database and invalidated that regression attempt. The runner now assigns a
  unique `_tests` database; the full sequential rerun and final required gate
  pass. Only disposable test databases were affected. The web boundary gate's
  sandbox subprocess `EPERM` was resolved by a local unsandboxed rerun; no
  network access or installation was required.
- **NOT_RUN — Section 6 broad suites, full routed Next.js/browser journey,
  real two-service paid HTTP, live LBX, publication, staging and production:**
  these are later-step or separately gated evidence, not Step 3 acceptance.
  Current proofs use real disposable PostgreSQL and synthetic source/provider
  transports; no synthetic quantity approves a commercial offer.
- **BLOCKED — real sale configuration/live positive acceptance:** approved launch
  quantities, LBX associations and sales enablement remain owner inputs under
  Section 3.8. Ordinary Kernel commercial flags remain disabled. This does not
  block the completed independent Step 3 implementation.
- Production allowance derivation/provenance admission and V2 snapshot serving
  remain Step 5. This step only preserves the existing issuer's immutable
  quantity behavior and widens customer response provenance. New v3 purchased
  documents additionally require a **Step 3-compatible reader**, even though
  migration head `20261031_0006` is unchanged; pre-Step-3 binaries cannot consume
  them. Steps 12–14 must retain that reader floor alongside the earlier ANY-765
  selected-digest floor. No historical document rewrite enables rollback.

Portal remains authoritative; the entire file is synchronized byte-for-byte to
Kernel and equality is verified before handoff. Steps 4–14 remain unexecuted.

#### Step 3 review follow-up — REV-2, 2026-11-10

**REV-2: RESOLVED.** The top-level Status, Next action and Blocker now agree
with the completed Step 3 checkpoint. The next implementation step is Step 4,
requiring a separate user request; no Step 3 repetition is directed.

The supplied review reports no confirmed functional defect in the inspected
Portal/Kernel diff. Its fresh API (1949), UI (420), web-boundary (38), Kernel
contract/binding/manifest (211) and exact-JSON quantity (10 scenarios) results
are reviewer-reported evidence, not reruns performed by this documentation
correction. The earlier PostgreSQL 68/115 reports were reused by that review.
Its attempted fresh PostgreSQL rerun was blocked by automatic approval review
because starting the local container requires explicit infrastructure permission.
The pasted permission request does not grant that permission. This correction
starts no container and claims no fresh database verification; Step 3 remains
complete with that review-verification limitation. Whole-program readiness,
live LBX and joint paid runtime remain unproven. REV-1 remains resolved.

Only the authoritative plan and its full Kernel mirror are changed by this
follow-up. Existing source changes and indexes are preserved. Documentation
checks, non-plan integrity and byte-for-byte mirror equality are verified before
handoff.

#### Step 3 local commit authorization — 2026-11-10

After the Step 3 review and REV-2 correction, the user explicitly requested
local commits in both repositories. This narrowly overrides the common
protocol's no-staging/no-commit rule for the completed Step 3 changes and their
synchronized plan/evidence. Commit the Portal implementation as
`ANY-766 - Publish immutable production allowance terms` and the Kernel plan
mirror as `ANY-766 - Record purchased allowance terms progress`.
Earlier unchanged-HEAD/empty-index/no-commit statements describe their execution
checkpoints. This authorization does not permit push, merge, rebase, branch
switching, later implementation steps or operational actions, including the
blocked fresh PostgreSQL review rerun. Preserve both plan copies byte for byte.

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

#### Step 4 execution checkpoint — 2026-11-10

**Result: COMPLETE within scoped server-side identity delegation.** Only Step 4
was executed. Starting/current HEADs remain Portal
`4a34948eb02d034b46871d739bbf066ffc67d48a` and Kernel
`89296ddce3c7b187881cb1730bf7fbacf3ffd302`, on local `ANY-766` branches,
plus this uncommitted diff. Both working trees and indexes were clean initially.
No staging, commit, push, branch change, dependency installation, real service
configuration, live LBX, publication or deployment was performed.

Implemented:

- Portal migration `20261110_0007` adds one hash-only
  `kernel_session_delegations` table, with unique code/token hashes, exchange
  shape constraint and `ON DELETE CASCADE` to the existing AuthSession. No user
  directory or identity matching is added. Portal now has 28 application tables;
  Kernel's migration head remains `0018`.
- `POST /api/kernel-session-codes` authenticates the existing Portal bearer and
  issues a random 32-byte S256-bound code for at most 60 seconds. Internal
  exchange is atomic and single-use; the random delegated token expires at the
  earlier of 30 minutes and parent expiry. Fixed audience is `platform-kernel`.
  Writes lock User → AuthSession → delegation and recheck authority after waits.
- Internal introspection reads delegation/session/user together, verifies scope,
  audience, active user, parent revocation/deletion/expiry and token expiry, and
  returns only canonical identity with the configured clock budget subtracted.
  Public session bookkeeping is separated from `validate_session`; identity
  reads perform no last-seen mutation or commit. Existing logout and password
  reset invalidate parent authority. `UserStatus.INACTIVE` explicitly represents
  deactivation without adding an administration endpoint.
- Reverse-direction credentials have current/previous rotation, explicit
  receiver-owned exchange/introspection permissions (empty by default), trusted
  scope and directional-secret separation. Internal receivers reject Origin
  before public CORS. Validation errors are redacted, dependency failures are
  safe `503`, identity `401` codes distinguish expiry from parent invalidation,
  and responses/refusals use no-store.
- Kernel implements `POST /v1/portal-session/exchange` and the reusable
  `authenticate_portal_user` dependency. It validates the independent wire
  version/scope/UUID/UTC/deadline contract and returns the existing Core
  Portal-user ExecutionOwner. Every dependency invocation introspects; no local
  identity cache, refresh token or guest fallback exists. TLS verification,
  socket timeout, response-size limit, redirect/proxy refusal and no automatic
  exchange retry keep secrets in the selected service direction.
- Generated Portal OpenAPI/schema/TypeScript and Kernel OpenAPI/CE-kit types,
  the current data model, both integration maps and paired contract README are
  updated. No fixture/schema checksum or commercial enablement was changed.

Fresh verification (repository-root commands):

- **PASS — Portal required selection plus HTTP/security cases: 55 passed,
  0 skipped, including 8 PostgreSQL cases.**
  `./.venv/bin/python -m pytest -p no:cacheprovider -q apps/api/tests/test_api_identity_session.py apps/api/tests/test_kernel_session_delegation.py apps/api/tests/test_kernel_session_delegation_postgres.py`.
  `/tmp/any766_step4_portal_tests.py` uses the existing
  `canonical_check_environment()` / `api_test_environment('api-postgres', ...)`
  and a unique disposable `_tests` database. Evidence:
  `.harness/any766-step4-identity.log` and `.harness/any766-step4-identity.xml`.
  Covers PKCE/single-use races, scope/audience, TTL/clock bounds, logout, actual
  password reset, deactivation, parent changes during exchange waits, cascade,
  migration round trip preserving parent rows, rejected partial exchange state,
  read-only introspection, rotation/permissions, outages and secret canaries.
- **PASS — Portal related regressions: 481 passed, 0 skipped:**
  `./.venv/bin/python -m pytest -p no:cacheprovider -q apps/api/tests/test_architecture.py apps/api/tests/test_repository_docs.py apps/api/tests/test_presentation_di.py apps/api/tests/test_any766_contracts.py apps/api/tests/test_api_password_reset.py apps/api/tests/test_api_email_verification.py`.
  Evidence: `.harness/any766-step4-regressions.xml`. Existing SQLite FK-sort and
  Python datetime-adapter warnings remain; they are not skipped tests.
- **PASS — Kernel required identity module: 63 passed, 0 skipped:**
  `LITELLM_LOCAL_MODEL_COST_MAP=True ./.quick-check-venv/bin/python -m pytest -p no:cacheprovider -o addopts='' -q apps/platform-api/tests/test_portal_session_api.py`.
  HTTP is intercepted. Includes independent positive/negative contract fixtures,
  canonical principal, request-by-request introspection, refusal without guest
  authority, directional auth, malformed owner/version/expiry, safe identity
  codes, dependency/error-body outages and secret-log canaries. Evidence:
  `/tmp/any766-step4-kernel-identity.xml`.
- **PASS — Kernel manifest/service-auth and contract regressions: 215 passed,
  0 skipped:** the same command selects
  `apps/platform-api/tests/test_capability_manifest.py apps/platform-api/tests/test_paid_contract_fixtures.py`.
  Evidence: `/tmp/any766-step4-kernel-regressions.xml`.
- **PASS — applicable non-fixing checks:** Portal Ruff check/format check on all
  16 changed/new Python files, `npm run architecture:check`, `npm run docs:check`
  and `npm run typecheck:web`; Kernel Ruff check/format check on all 6 changed/new
  Python files, `runner.py validate-architecture`, `validate-configs`,
  `validate-docs`, and `pnpm --filter @anytoolai/ce-kit typecheck`.
- **PASS — generation:** Portal `PATH="$PWD/.venv/bin:$PATH" npm run generate`
  and `npm run generate:check`; Kernel `runner.py generate-docs`,
  `generate-docs --check`, `pnpm --filter @anytoolai/ce-kit generate-api-types`
  and `generate-api-types:check`. Kernel commands set
  `LITELLM_LOCAL_MODEL_COST_MAP=True` to use the shipped local cost map.
- **PASS — diagnostics/integrity:** Kernel doctor; Portal doctor after stopping
  the test server; both `git diff --check`, unchanged HEADs/branches, empty
  indexes, paired contract README equality and byte-for-byte plan equality.

Authorization, corrections and limits:

- The user explicitly authorized starting the isolated local test-db and applying
  migrations **only to a temporary test database**. The existing local pinned
  PostgreSQL image was used through `scripts/repo.py test-db up`; no image was
  downloaded. Fixtures created/migrated/dropped unique `_tests` databases.
  `scripts/repo.py test-db stop` stopped the server afterwards without removing
  its volume. No application database was migrated. This is fresh Step 4
  evidence, not a rerun of the historical Step 3 review selection.
- Introduced fixture mistakes (registration/reset data, UTC serialization and
  interrupted HTTP-error body) were corrected. Architecture checks required SQL
  availability translation in a focused infrastructure capability; its neutral
  failure is exposed by the identity use case, with transaction ownership left
  in Application. No boundary guard or failure was suppressed. All affected
  checks now pass. Sandbox TestClient restrictions and the doctor's busy port
  while the test server was running were resolved by local checks and shutdown.
- **NOT_RUN — assembled broad suites, real two-service TCP HTTP, browser launch/
  recovery, paid runtime ownership/admission, V2 snapshots, live LBX, staging and
  production.** These remain later steps and operational gates. In particular,
  Step 6 must attach the identity dependency to paid runtime surfaces and Step 8
  must implement browser custody/recovery. Step 4 does not enable paid execution
  or alter existing guest routes. Earlier broader Kernel permission-test limits
  remain historical and were not reclassified as passing by these selections.
- **BLOCKED — commercial/live/staging actions** retain Section 3.8 owner inputs;
  none blocks the completed Step 4 server slice. Real configuration, application
  migration and deployment still require their own authorization.

Portal remains authoritative; the complete file is synchronized byte-for-byte to
Kernel. Next is Step 5 only on a separate request. Steps 5–14 are unexecuted.

#### Step 4 review follow-up — REV-3, 2026-11-10

**REV-3: RESOLVED (important).** The original Step 4 checkpoint verified serial
password-reset invalidation but missed the real reset/exchange lock inversion.
The supplied earlier diagnostic log `/tmp/any766-step4-review-race.log` records
PostgreSQL `40P01`. This follow-up independently reproduced it with checked-in
regressions before changing the production function.

Cause and correction:

- With `autoflush=False`, `confirm_password_reset()` updated AuthSession rows
  before flushing its dirty User at commit, while delegation locked User first.
  Each transaction could retain the row needed by the other. Both actual
  exchange-first and reset-first interleavings reproduced the deadlock.
- Reset now resolves the scoped token owner without writes, acquires the existing
  active scoped User lock, then atomically claims the reset token using fresh
  time sampled after the wait. Password replacement, token invalidation and
  all-session revocation retain the same application-owned transaction. Thus
  reset and delegation use User before AuthSession, without a retry loop or
  error suppression. Public HTTP contracts and persistence schema are unchanged.
- Taking User before the token claim also prevents two different reset tokens
  from each holding one token while invalidating the other. A new concurrent
  test requires exactly one committed reset and one ordinary invalid-token
  refusal. Another test expires the token while reset waits for User and proves
  that no password, session or token mutation commits after expiry.

Fresh evidence:

- **FAIL — pre-fix reproduction, expected red result:**
  `./.venv/bin/python /tmp/any766_rev3_tests.py red apps/api/tests/test_kernel_session_delegation_postgres.py -k 'password_reset_and_exchange_share_user_first_lock_order or concurrent_distinct_password_reset_tokens'`
  — **3 failed / 8 deselected**, each with a real PostgreSQL deadlock. Both
  exchange/reset orderings and distinct-token concurrency execute the actual
  service functions with SQL barriers. Evidence:
  `.harness/any766-rev3-red.log` and `.harness/any766-rev3-red.xml`.
- **PASS — same three regressions after the correction:** the same command with
  `green` — **3 passed / 8 deselected**. Evidence:
  `.harness/any766-rev3-green.log` and `.harness/any766-rev3-green.xml`.
- **PASS — final affected selection, 541 passed / 0 skipped:**
  `./.venv/bin/python /tmp/any766_rev3_tests.py final apps/api/tests/test_api_identity_session.py apps/api/tests/test_kernel_session_delegation.py apps/api/tests/test_kernel_session_delegation_postgres.py apps/api/tests/test_api_password_reset.py apps/api/tests/test_password_reset_persistence_postgres.py apps/api/tests/test_architecture.py apps/api/tests/test_repository_docs.py apps/api/tests/test_presentation_di.py apps/api/tests/test_any766_contracts.py apps/api/tests/test_api_email_verification.py`.
  This includes the four new PostgreSQL cases, the original Step 4 migration/
  single-use/cascade/security checks, actual reset/logout behavior and the
  existing architecture, documentation and contract regressions. Evidence:
  `.harness/any766-rev3-final.log` and `.harness/any766-rev3-final.xml`.
  Existing SQLite FK-sort/datetime-adapter warnings remain; there are no skips.
- **PASS — non-fixing checks:** Ruff check and format check on the two Python
  files changed by this follow-up; Portal `npm run architecture:check`,
  `npm run generate:check` and `npm run docs:check`; Kernel
  `runner.py validate-docs`; both `git diff --check` and byte-for-byte plan
  equality. No generated file, contract fixture/checksum or dependency changed.
- **PASS — preservation and cleanup:** the earlier explicit local test-db /
  temporary-migration authorization was reused. The runner derives the existing
  isolated test configuration and assigns a unique `_tests` database; fixtures
  create/migrate/drop only that database. The test server was stopped afterwards
  without removing its volume. All other pre-existing Step 4 files, both HEADs
  and both empty indexes remain unchanged outside the production reset function,
  its PostgreSQL regressions and the synchronized plan follow-up.
- **REUSED, not rerun here — Kernel identity 63 and regressions 215:** Kernel
  runtime and all wire contracts are unchanged by REV-3. Earlier Step 4 evidence
  remains recorded above. Real paired HTTP, browser recovery, paid runtime and
  whole-program readiness remain **NOT_RUN** under their later steps/gates.

Step 4 is complete with REV-3 corrected. REV-1 and REV-2 remain resolved;
Steps 5–14 remain unexecuted. Portal is authoritative and its complete Kernel
copy is synchronized before handoff. No Git staging/commit, publication,
application-database migration or external service operation was performed.

#### Step 4 local commit authorization — 2026-11-10

After the Step 4 implementation and REV-3 correction, the user explicitly
requested local commits in both repositories. This narrowly overrides the
common protocol's no-staging/no-commit rule for the completed Step 4 changes,
its reset lock-order correction and synchronized plan/evidence. Commit Portal as
`ANY-766 - Delegate Portal sessions to Kernel` and Kernel as
`ANY-766 - Authenticate delegated Portal sessions`.
Earlier unchanged-HEAD/empty-index/no-commit statements describe their execution
and review checkpoints. This authorization does not permit push, merge, rebase,
branch switching, later implementation steps or publication/deployment.

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

**Repository / Read before implementation:** Portal; [paid writer](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/billing/paid_access.py), [allowance issuance](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/billing/paid_allowances.py), [paid read](https://github.com/gushinets/payments-portal/blob/7f985031034f45fde0203f710eb64283cd086e86/apps/api/app/domains/billing/paid_read.py).

**Implement / reuse:** replace simulation-only derivation switches with explicit provenance policy. Reuse primary/cycle classification, issuance, deadline scheduling and the sole paid commit. Preserve complete relevant product proof for primary decisions and customer-wide proof for financial CREATE/original-resolution admission; unrelated incomplete products must not block a proven primary. Add a scoped committed-state read and authenticated V2 producer with bounded serving capacity. Update customer DTO provenance and generated contracts.

**Invariants:** no source I/O or state writes in snapshot GET; no guessed calendar conversion or repricing existing subscriptions.

**Verification:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_access_snapshot_postgres.py apps/api/tests/test_paid_access_recovery_postgres.py apps/api/tests/test_paid_access_capacity_postgres.py apps/api/tests/test_paid_access_terms_postgres.py apps/api/tests/test_paid_access_primary_scope_postgres.py
PATH="$PWD/.venv/bin:$PATH" npm run generate
PATH="$PWD/.venv/bin:$PATH" npm run generate:check
```

Cover revision zero/N, no-op, rollback, source/UTC deadlines, future starts, simulation isolation, renewal retention and unrelated-product survival. Retain the scoped-primary/operator regressions and stricter financial admission when another product remains incomplete.

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

Cover crashes around send/apply/ack, N/N+1, lease/generation loss, outage, permanent failure and deadline progress under saturation.

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

### Step 11 — Prove independent runtime and real HTTP execution

**Goal / Expected behavior:** both applications run independently and jointly with retained state and actual protected execution.

**Repositories / Read before implementation:** both Compose/runners and [metering cutover](https://github.com/gushinets/anytoolai-platform/blob/72ff15bc0b77903c87aa39f7b10186dccc556d09/infra/deployment/execution-metering-cutover.md).

**Implement / reuse:** add optional peer-network/config inputs and the Kernel development PostgreSQL named-volume correction. Pin the selected PostgreSQL 18 patch/digest without changing database major versions or abandoning retained volumes.

Add a bounded Portal-owned joint harness under `tools/joint_paid_runtime/`. Reuse existing process/composition/test seams; launch real APIs/workers with separate disposable PostgreSQL databases and TCP HTTP. Use temporary enabled product profiles, isolated purchased quantities and deterministic provider/LBX substitutes.

**Verification — Portal:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_any766_joint_http_postgres.py
npm run test:e2e -- any766-kernel-launch.spec.ts any766-paid-execution.spec.ts
```

The new browser cases use the harness-provided Portal/Kernel origins and run existing desktop/mobile projects.

Verify all service directions, session launch, seven scenarios, paid events, replay, exhaustion, revocation, last-unit competition, same-cycle recovery, new cycle and process restart. Regress selected-digest/historical replay and product-scoped primary decisions while an unrelated product is incomplete; financial admission must retain its customer-wide requirements. Recreate containers and compare retained identities, purchases, floors and usage. Collect accessibility evidence for changed Portal surfaces.

**Invariants:** no shared database, global cleanup, real financial mutation or new orchestration framework.

**Expected completion:** real transport and storage prove the assembled system; synthetic provider evidence remains explicitly labelled.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 11. Follow both runtime instruction sets and the common protocol. Reuse runners, independent Compose projects and recovery gates; implement the bounded joint harness and required storage/network corrections. Run actual HTTP/PostgreSQL/browser checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED with evidence labels. Do not stage, commit, push, merge, rebase or switch branches. Preserve unrelated volumes. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Prove durable joint Portal Kernel execution`

### Step 12 — Package independent image releases

**Goal / Expected behavior:** compatible selected components deploy without application builds on staging.

**Repositories / Read before implementation:** both Dockerfiles, production Compose, CI and runners; Kernel profile generation/activation.

**Implement / reuse:** add component-selectable GHCR workflows, release metadata, selection validation, image Compose and `deploy-images`. Package matching runner/helper files. Implement the explicit host/container profile mapping and frontend-only behavior from Section 3.7.

**Verification — Portal:**

```bash
./.venv/bin/python -m pytest -q apps/api/tests/test_image_deploy.py
```

**Verification — Kernel:**

```bash
./.quick-check-venv/bin/python -m pytest -q tests/test_image_deploy.py tests/test_runner.py
```

Use fixture selections to verify incompatible IDs, origins, peer versions and image pairs are rejected before mutation. Include rejection of a pre-selected-digest Portal reader against new acceptance history even when migration heads match; retain historical v1/v2 readability with compatible readers. Rehearse actual image deployment on a disposable local stack where Docker is available. Verify no host build, profile fingerprints/mounts/activation, migration failure handling, frontend-only update and retained data.

Workflow publication requires authorized dispatch; implementing workflows does not authorize publication.

**Expected completion:** matching release bundles reproduce selected images and enforce compatibility before changing runtime.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 12. Follow both delivery instruction sets and the common protocol. Reuse Dockerfiles, runners and deployment safeguards. Implement explicit compatibility metadata, image-mode deployment and profile path mapping; preserve frontend-only independence. Run focused tooling/build/rehearsal checks, fix introduced failures and report PASS/FAIL/NOT_RUN/BLOCKED. Do not stage, commit, push, merge, rebase or switch branches. Do not dispatch publication or perform live LBX/production operations without authorization. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Package compatible independent image releases`

### Step 13 — Deploy and verify the selected staging pair

**Goal / Expected behavior:** approved staging runs selected immutable images and preserves existing data.

**Read before implementation:** both release runbooks, approved `selection.json`, infrastructure inputs and ANY-768 owner decisions.

After the staging gate passes, publish/select exact images, configure ingress/private connectivity and deploy through app-owned commands. The operator supplies the following variables as absolute paths to the assembled release bundles and secret env files.

**Portal deployment:**

```bash
python3.12 "$ANY766_PORTAL_RELEASE_DIR/scripts/repo.py" deploy-images --release-dir "$ANY766_PORTAL_RELEASE_DIR" --env-file "$ANY766_PORTAL_ENV_FILE" --component all
```

**Kernel deployment:**

```bash
python3.12 "$ANY766_KERNEL_RELEASE_DIR/scripts/agent/runner.py" deploy-images --release-dir "$ANY766_KERNEL_RELEASE_DIR" --env-file "$ANY766_KERNEL_ENV_FILE" --component all
```

Run acceptance from the prepared development/CI environment, without installing test dependencies on staging:

```bash
./.venv/bin/python tools/joint_paid_runtime/staging_probe.py --release-dir "$ANY766_SELECTION_DIR"
npm run test:e2e -- any766-kernel-launch.spec.ts any766-paid-execution.spec.ts
```

The staging probe uses approved origins/test identity from secret environment inputs. It performs only explicitly authorized test execution and reconciliation; it never creates a payment or subscription.

Verify HTTPS/readiness, actual identity/snapshot/invalidation/usage/exhaustion, an accessible paid result, cabinet agreement, backend update, restart and recovery. Enforce the purchased-document reader compatibility floor during rollback/recovery; an unchanged migration head does not prove binary compatibility. Select a second compatible frontend digest and demonstrate `--component frontend` without restarting backend or migrating.

Use an existing authorized paid test purchase for live positive proof. If absent, an owner-operated payment is a separate input. Do not infer live PASS from deterministic evidence.

**Expected completion:** selected staging works reproducibly. Missing essential inputs leave this step BLOCKED and prevent a claim of completed staging delivery.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 13. Follow both app runbooks, infrastructure ownership and the common protocol. Verify the staging gate, then use approved release digests and app deployment commands. Preserve databases and history. Run the specified staging/browser checks, fix integration failures and report PASS/FAIL/NOT_RUN/BLOCKED by evidence source. Do not stage, commit, push, merge, rebase or switch branches. Execute only authorized publication/staging actions; never perform unapproved financial or production operations. Continue independent work when an operational input is missing.

**Proposed commit:** `ANY-766 - Record verified selected staging integration`

### Step 14 — Complete review and handoff

**Goal / Expected behavior:** ANY-767 receives the working integration, reproducible releases and honest acceptance status.

**Repositories / Read before implementation:** final paired diff, this plan’s DoD, predecessor records and applicable review checklists.

**Implement / reuse:** update as-built architecture/integration maps, security/reliability, schema references and runbooks. Prepare traceable supersession of obsolete ANY-286/287 access-check direction; ANY-79 is already canceled. External ticket edits require their own authorization.

Review authority, identity, transaction boundaries, ownership, recovery, delivery and actual end-to-end behavior. Verify the consumed ANY-765 corrections, production-vocabulary attribution and purchased-document rollback floor remain reflected in as-built docs and release metadata. Resolve confirmed findings and repeat affected checks.

**Verification:** run Section 6 on the assembled pair.

**Invariants:** no parallel `POST /v1/access/check`, speculative cleanup, hidden skipped acceptance or production-readiness claim.

**Expected completion:** exact paired sources/builds and their evidence are ready for human review; required blocked scenarios remain explicit.

**AI execution prompt:**

> Read /home/wstanley/www/work_unirec/runtime-research/payments-portal/docs/exec-plans/active/ANY-766-implementation-plan.md and complete only Step 14. Follow both repositories’ delivery instructions and the common protocol. Review the combined result against DoD, reuse valid evidence and fix confirmed ANY-766 omissions. Run the broadest supported canonical checks and affected reruns. Produce the Section 7 handoff with PASS/FAIL/NOT_RUN/BLOCKED evidence. Do not stage, commit, push, merge, rebase, switch branches or mutate external tickets without authorization. Do not perform unapproved live LBX or production operations. Stop only for an irresolvable material decision.

**Proposed commit:** `ANY-766 - Finalize integration evidence and handoff`

## 6. Final Verification & Review

Run focused checks during steps and broad checks on the final paired result.

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
- Migration/image/profile compatibility and independent updates.
- Real HTTP, browser and selected staging evidence.

Record **historical**, **new local**, **synthetic fixture/provider**, **real two-service HTTP**, **live LBX**, and **deployed/production** evidence separately.

This revised plan closes:

- **PLAN-1:** existing paid client-event ingestion and browser tracking are included in Steps 6/8.
- **PLAN-2:** usage variants, exhaustion identity and durable acknowledgement are specified.
- **PLAN-3:** token custody and original-operation recovery are specified.
- **PLAN-4:** release compatibility and host/container profile mapping are specified.
- **PLAN-5:** Step 1 materialization and contract formalization/technical review are complete in both repositories; Portal remains authoritative and the Kernel copy is synchronized after progress updates. Every later prompt names the exact Portal path and every step has concrete verification targets. Step 2 supplies production declarations and scenario bindings; Step 3 supplies immutable purchased quantities and pre-consent presentation. Step 4 supplies scoped server-side session delegation and the Kernel principal adapter. Paid runtime integration and later delivery remain for Steps 5–14.

Remaining gates concern commercial and operational inputs for their dependent actions. Step 1 and implementation following the accepted strategy require no additional preliminary protocol approval. No launch quantity, LBX association, credential or host is invented.

## 7. Handoff to ANY-767

Deliver one compact handoff containing:

- Final Portal/Kernel SHAs, predecessor correction disposition and consumed ANY-507/814 versions.
- Migration heads/order, purchased-document reader compatibility/rollback floor, component digests, release metadata, selection and actual staging deployment.
- Reviewed contract versions, fixtures/checksums and producer/consumer ownership.
- Delegation, browser recovery, directional credentials, permissions, rotation and expiry behavior.
- Actual coherence/admission/finalization/readback/delivery attachment points.
- Deployment, readiness, inspection/retry, backup and recovery commands.
- A correlated trace from committed Portal authority through real snapshot HTTP, paid Kernel execution, accessible result, durable usage and cabinet display.
- Replay, last-unit, revocation, paid events, same-cycle recovery, rollover, restart and independent-update evidence.
- Exact remaining sales, live-provider, renewal, infrastructure and production gates with owners.

ANY-767 owns the complete registration → Widget/payment → reconciliation → product journey, remaining natural-renewal verification, final deployment acceptance and production rollout. Unfinished identity, enforcement, usage delivery, core connectivity or staging implementation must remain visible as incomplete ANY-766 work.
