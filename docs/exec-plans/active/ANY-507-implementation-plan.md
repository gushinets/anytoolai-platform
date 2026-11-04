# ANY-507 — Reserve capacity and consume only for a successful result

## Status

- State: active
- Owner: mixed
- Created: 2026-11-04
- Last updated: 2026-11-04
- Review date: 2026-11-04
- Next action: stop after stage 4 and its documentation review; stage 5 requires a new user instruction.
- Blocker: general baseline/full gate requires passwordless sudo; no stage-4 implementation blocker.

## 1. Basis, version and scope

This repository-local English execution plan preserves the reviewed PLAN-1–3 corrections.
Stages 1–3 are implemented in `805110b7`, `98c92121` and `02639ec7`. The current user instruction
authorizes stage 4 only. Section 6 preserves the historical stage-0 observations; section 7 records
stage 3. Stage 4 preserves ANY-766's ownership of paid HTTP/access and interservice integration.

Sources: [ANY-507](https://linear.app/paveldik/issue/ANY-507),
[parent ANY-504](https://linear.app/paveldik/issue/ANY-504), Mikhail's 2026-11-03 M2 decision,
and the supplied PLAN-5 implementation plan for [ANY-766](https://linear.app/paveldik/issue/ANY-766).
Section 2 freezes the shared internal Kernel contract; section 6 records the inspected baseline,
transaction owners, concrete attachment points and stage-0 evidence.

**Kernel baseline:** `feature/ANY-507` at
[`2b4920999e7839b12e90b6b05cd6dc0667e5e7b4`](https://github.com/gushinets/anytoolai-platform/commit/2b4920999e7839b12e90b6b05cd6dc0667e5e7b4).
The checked-in migration graph has one head, `0015`. ANY-711/#225 is included at
`331e086ca9e0c72eb757aacc476bad5bacb5bae5`, supplying the capability registry, metric vocabulary
and trusted deployment scope. These are source observations, not deployed-database evidence.

Read before implementation: [AGENTS](../../../AGENTS.md), [architecture](../../../ARCHITECTURE.md),
[knowledge map](../../index.md), [MVP scope](../../product-specs/mvp-scope-source-of-truth.md),
[core beliefs](../../core-beliefs.md), [platform boundaries](../../architecture/platform-boundaries.md),
[package layering](../../architecture/package-layering.md), [LLM runtime](../../architecture/llm-runtime.md),
[MVP-A1](../../product-specs/mvp-a-platform-kernel.md),
[MVP-A2](../../product-specs/mvp-a2-client-surfaces.md),
[harness map](../../agent/harness-engineering-map.md), [coding conventions](../../agent/coding-conventions.md),
[quota](../../architecture/quota-model.md), [jobs](../../architecture/job-lifecycle.md),
[scenarios](../../architecture/scenario-session-model.md), [workflows](../../architecture/workflow-model.md),
[handoffs](../../architecture/handoff-model.md), [storage](../../architecture/runtime-storage.md),
and the [Portal integration map](../../integrations/payment-portal.md).

Ownership:

- ANY-507 delivers one reserve/finalize/release/recovery mechanism for guests and typed paid inputs,
  ordinary start and immediate handoff, internal readback, and the corresponding migrations.
- ANY-766 delivers Portal authentication, AccessSnapshot, freshness/floor/cache/invalidation,
  scenario `paid_metric_key` selection, paid HTTP integration, interservice usage/exhaustion and real
  joint acceptance. It consumes this mechanism instead of introducing a second debit path.
- Final Portal ANY-715/765 handoffs gate the corresponding ANY-766 integration. They do not gate
  implementation or independent acceptance of ANY-507.
- Historical body `user_id` does not become a trusted Portal owner. Guest-to-user linking, sale
  quantities, stacking and resizing an existing paid quantity are out of scope.

## 2. Shared internal contract

### Types and entry points

Platform Core owns these frozen dataclass/domain contracts, following its existing SQLAlchemy Core
tables and record conventions. Closed kinds/states use Core enums; Core does not import SDK types.
These are implementation contracts, not new HTTP DTOs or already-existing Python exports:

- `ExecutionOwner`: `tenant_id`, `region`, `owner_kind` (`guest | portal_user`), `owner_id`.
  Guest IDs retain the existing opaque identity; paid owner IDs are canonical Portal UUIDs.
  Scope is deployment-derived. ANY-766 supplies the authenticated paid owner.
- `PaidAllowance`: `owner: ExecutionOwner` (Portal user only), `allowance_id`, `product_id`,
  `metric_key`, `unit`, `quantity`. It carries no LBX IDs/calendar, snapshot revision, provider
  policy or billing state. Authority/freshness checks remain in ANY-766.
- `ExecutionReservation`: reservation identity, owner, exactly one original guest/paid bucket
  reference, `scenario_session_id`, `job_id`, product/scenario/frontend correlation, replay
  namespace/key/hash when applicable, `reserved | consumed | released` state and final artifact
  linkage for consumption.
- `ExecutionAcceptance`: original session/job and bucket linkage, with `is_replay: bool` visible to
  admission orchestration. Legacy guest replay has no synthesized historical reservation.
- `ConsumptionReadback`: owner/bucket identity, `quantity`, `used`, `successful_used`,
  `legacy_used`, `reserved`, `remaining`, `available` and timezone-aware `read_at`.
- `ConsumptionTransition`: applied transition versus replay of an earlier decision, resulting
  reservation state and bucket/job/result linkage, plus `became_exhausted: bool`. A repeated or
  losing transition cannot report a new exhaustion edge.

The metering operations explicitly receive the caller's SQLAlchemy `Session`. Repositories may
flush; none of these operations commits or rolls back the outer transaction:

```text
reserve_execution(session, owner, execution, quota_input) -> ExecutionAcceptance
finalize_success(session, job_id, final_result) -> ConsumptionTransition
release_execution(session, job_id) -> ConsumptionTransition
read_consumption(session, owner, bucket) -> ConsumptionReadback | None

find_execution_replay(session, owner, replay_identity, request_hash)
    -> ExecutionAcceptance | None
```

`execution` identifies the candidate session/job and validated runtime dimensions/input.
`quota_input` is the existing resolved guest policy/dimension/window input or `PaidAllowance`;
guest and paid authority/counters remain separate. `final_result` is the validated final artifact
candidate with stable identity, payload and workflow/schema provenance, retained unchanged for
success recovery. Exact implementation placement stays within Core's quota/runtime modules;
the names and semantic boundary above are shared with ANY-766.

Runtime ordinary start and handoff accept explicitly receive `execution_owner` and
`paid_allowance` as internal arguments; an HTTP body cannot construct that authority.
`ScenarioRuntimeService` exposes owner-scoped `find_execution_replay` and returns acceptance with
`is_replay` to its admission caller. This preparation adds no shared Portal/Kernel runtime package.

### First paid allowance binding — PLAN-3

Before accepting new paid execution, validate:

- Allowance owner and tenant/region match the trusted execution owner.
- Allowance product matches the requested product and session/job.
- The metric belongs to that product, and its unit matches the registry.
- Quantity is a strict integer, excluding `bool`, in `0…2^53−1`.
- Reservation, session/job and bucket have consistent scope and linkage.

ANY-766 selects the expected metric from the scenario definition and checks current grant/allowance.
ANY-507 validates the integrity of the typed input; it does not itself grant paid access.

On first acceptance, freeze owner/product/metric/unit/quantity for that allowance ID.
Reject any later tuple change without changing usage. Commercial `enabled` alone cannot revoke
an already-accepted allowance.

### Buckets, history and replay

Keep distinct counters:

- Guest: existing `guest_quota_usage` policy/dimension/window.
- Paid: separate `paid_allowance_usage`, selected by scoped allowance ID.
- Shared lifecycle: `execution_reservations`.

Within tenant/region, an allowance ID is bound to one owner. The same ID with a different owner
is a conflict. A new ID creates a separate bucket even if every other field matches.
Reservations remain bound to their original bucket: finalization/release never recomputes the guest
window or substitutes a new paid cycle.

Paid start requires `Idempotency-Key`. Replay uniqueness is:

```text
tenant + region + owner_kind + owner_id
+ product + scenario + namespace + replay_key
```

Server namespaces are `start` and `handoff`; the latter uses the stable runtime handoff ID,
not the handoff definition ID or plaintext token.
The request hash covers product/scenario/frontend, normalized input and applicable handoff;
allowance ID and access revision are excluded.

Accepted replay:

- Checks trusted owner and request hash.
- Returns the original execution/bucket, including a terminal failure.
- Requires no new allowance and does not reserve again.
- Remains available across cycle changes or loss of new-start access while owner authentication
  remains valid.

A concurrent unique race uses a savepoint covering all candidate session/job/reservation writes.
The loser rolls back its candidate rows and reads the winner.
Legacy guest replay keeps its existing lookup without historical reservations. Paid lookup through
the guest path with `guest_id=NULL` is forbidden.

### Transactions and terminal arbitration — PLAN-2

**Acceptance:** session, created job, reservation, reserved increment and transition events commit
together. The caller may still reject the entire acceptance before outer commit.

**Success:** an accessible canonical result, `job=succeeded`, permitted scenario completion,
`reserved−1`, `used+1`, `reservation=consumed` and events commit together.

Consumption uses the same availability criterion as Result API: schema validity, canonical linkage,
workflow/schema versions, normalized output and no forbidden internal fields.
An artifact row or successful provider call alone is insufficient; the user need not view the result.
Extract/reuse the Result API validation boundary, including its forbidden-key check, rather than
charging on a weaker artifact-only predicate.

For new reserved executions:

1. Already-committed success replays without a new debit or scenario mutation.
2. New publication requires expected job/reservation states and a conditional scenario transition
   from `running`.
3. If another terminal scenario state won before publication, preserve it, publish no result,
   safely fail the job and release without debit.
4. A late worker cannot restore terminal execution to `running` or publish after release.

Existing-row lock order for these transitions and competing terminal writers is:

```text
job -> scenario -> reservation -> bucket
```

Legacy reconciliation continues to preserve independently expired scenarios.

**Release:** terminal failure/cancellation without published success and reservation release commit
together. `consumed` never becomes `released`; `released` never becomes `consumed`.

### Final admission check — PLAN-1

ANY-766 performs authentication and necessary HTTP refresh outside the admission transaction.
Inside it:

1. Lock the scoped user/floor.
2. Repeat owner-scoped replay lookup.
3. For a new execution, perform acceptance/reservation.
4. **After waiting for admission locks**, recheck revision and time boundaries before commit.
5. On denial, roll back the complete acceptance.

Hold user/floor and bucket locks until this decision. No HTTP/provider I/O runs under these locks.
Replay lookup must be possible before mandatory snapshot refresh: snapshot unavailability cannot
hide an accepted execution from its currently authenticated owner.

### Readback

Preserve historical guest usage without refunds or claiming old attempts were successful:

```text
used      = legacy_used + successful_used
remaining = max(quantity - used, 0)
available = max(quantity - used - reserved, 0)
exhausted = remaining == 0
```

Paid `legacy_used=0`. With Q=1 and one active reserve:
`used=0, reserved=1, remaining=1, available=0, exhausted=false`.

Read one consistent snapshot in one query. Unknown paid bucket returns `None`/`unobserved`;
a read does not create it. Storage unavailability cannot become zero usage.

## 3. Implementation stages

### Stage 0. Freeze the executable contract

**Outcome:** repository-local plan, concrete internal types, transaction ownership and compatible
baseline, with verification limits recorded in section 6.

**Components:** Core contracts, API/worker composition and ANY-766 handoff.

**Dependencies:** reviewed shared ANY-507/766 contract and ANY-711 baseline. Portal ANY-715/765
readiness/final handoffs are unnecessary for this stage or independent ANY-507 acceptance.

**Checks:** HEAD/ancestry/migration head, `doctor`, and the same TEST-ONLY bundle through existing
composition/loader seams. Follow Kernel AGENTS and coding conventions.

**Stop:** no migration, runtime type/service, endpoint or frontend implementation in this stage.
Stages 1–5 remain unstarted.

### Stage 1. Add storage and migration — done

**Outcome:** counters/reservations without changing historical usage.
**Components:** Alembic, SQLAlchemy tables, records and repositories.
**Dependency:** stage 0.

- Append a new revision after current `0015` (`0016` on this baseline; recheck before adding it).
- Add `reserved_count=0` and `legacy_used_count=used_count` to guest usage; preserve `used_count`.
- Add paid counters using `BIGINT`, range constraints and immutable tuple enforcement.
- Add reservations with FKs, unique session/job and owner-scoped replay, and exactly one bucket kind.
- Add server-owned job `consumption_mode: legacy | unmetered | reserved`. Existing jobs are
  `legacy`; new metered jobs are `reserved`. A reserved job lacking its reservation is an
  integrity error.

**Checks:** clean upgrade, populated `0015` upgrade, constraints, unchanged identities/scopes/
counters/runtime history, and repeated `upgrade head` without data changes.

### Stage 2. Connect reserve and replay — done

**Outcome:** ordinary start and immediate handoff share guest/typed-paid reservation.
**Components:** quota/reservation services, scenario runtime, handoff and API error mapping.
**Dependency:** stage 1.

- Replace accepted-start debit with reservation when `used + reserved < quantity`.
- Enforce first paid binding checks from section 2.
- Pass trusted paid owner explicitly; `source_session.user_id` does not create paid authority.
- Repeated accepted handoff returns its original target linkage; check accepted replay before token
  expiry denial. Unaccepted tokens retain normal expiry.
- Deferred handoff without a job reserves nothing.
- Distinguish `429 quota_capacity_reserved` from `429 quota_exhausted`.
- Capacity-reserved rollback leaves handoff retryable without target execution. Final exhaustion
  retains critical failed/audit recovery.

**Checks:** concurrent replay, hash conflicts, same key/different owners, invalid first paid binding,
independent counters and handoff accept/decline/expiry races. Every denial leaves consistent rows.

**Stage-2 checkpoint (`98c92121`, 2026-11-04):** common guest/typed-paid reservation and owner-scoped
replay are implemented atomically with session/job creation. Paid bucket bindings are immutable;
accepted handoff replay precedes expiry checks, deferred handoff reserves nothing, and busy capacity
leaves acceptance retryable. Paid HTTP/access integration remains ANY-766 scope.

### Stage 3. Unify finalization and recovery — done

**Outcome:** one terminal decision per metered job; unknown outcomes cannot produce a free published
result or duplicate debit.
**Components:** workflow runner, shared finalizer, artifact/result validation, worker handler,
repositories and orphan reconciliation.
**Dependency:** stage 2.

- Ordinary success and rollback success recovery call the same `finalize_success`.
- For metered final artifacts, remove independent final-artifact-only recovery commit; recovered
  publication and consumption remain atomic.
- Register success recovery after validating the final candidate and before attempting finalization,
  retaining immutable result data and the same artifact ID.
- Recovery first reads durable terminal state. Failure/cancellation recovery cannot release after
  `consumed`; success recovery cannot publish after `released`.
- Connect release to workflow failure, preclaim cancellation, worker cancellation,
  disabled-product/poison-job failure and orphan terminalization.
- Apply section 2 terminal arbitration, including expired-scenario races.
- Preserve action/provider/debug recovery and causal event backfill without another
  `workflow.started`.
- Guard runtime updates by current status.
- Use JobLease and current job state; neither release by timeout nor automatically requeue unknown
  execution.

**Checks:** rollback/unknown commit at publication/debit boundaries, repeated callbacks, scenario
completion failure, expired-scenario race, SIGKILL/restart, live lease, lease-connection loss and late
worker after release.

### Stage 4. Connect readback and client states — done

**Outcome:** API/events/guest UI distinguish consumption, reservations and available capacity.
**Components:** guest quota API, Core readback, event catalog, OpenAPI, CE-kit and shared web/handoff.
**Dependencies:** stages 2–3.

- Preserve guest fields; add reserved/available, historical contribution and read time.
- Move `quota.consumed` to success; add reserve/release/capacity-reserved events.
- Emit transitions only on actual state changes with required owner/scope/session/job/handoff/bucket
  dimensions.
- Temporary reservation must not open exhausted/paywall state; retry/read refresh does not mint a
  new logical execution.
- Update DTOs/parsers/generated drift assertions and required locale catalogs.
- Update accepted-start wording in quota/job/scenario/workflow/handoff/result and MVP-A1 docs.
- Paid HTTP quota branch and interservice usage endpoints remain ANY-766.

**Checks:** HTTP/parser regressions, busy/exhausted states, refresh after success/release, handoff busy
retry, generated drift and no internal-data leakage.

### Stage 5. Verify cutover and prepare handoff

**Outcome:** verified mechanism delivery and safe activation procedure.
**Components:** quiesce/deployment procedure, PostgreSQL suites, canonical checks and evidence.
**Dependencies:** stages 1–4.

1. Close admission using existing quiesce and drain legacy workers.
2. Confirm no legacy `created/running` jobs, stop workers and take a consistent backup.
3. If drain times out, verification fails or outcomes remain unresolved, defer cutover; synthesize
   no reservations/refunds.
4. Apply migration, compare history, start compatible API/worker, smoke and reopen admission.

Do not mix old debit-on-start code with the new mechanism. Legacy terminal jobs are never charged
again. After new reservations exist, rollback to old code requires a consistent backup restore;
ordinary updates preserve history.

**Checks:** successful drain, refusal with unfinished jobs, migration failure, restart/data retention
and consistent rollback.

## 4. PostgreSQL evidence and independent acceptance

Use disposable databases, the real Alembic chain and independent connections/processes through the
existing harness. Required cases:

- Faults between acceptance writes commit all execution state or none.
- One accessible canonical result gives one debit; actions/retries/repeated finalize add none.
- Terminal failure/cancellation with partial artifacts releases without consumption.
- Q=1: one new start wins, competitors get capacity-reserved; failure restores capacity, success
  produces exhaustion.
- Concurrent duplicate, lost HTTP response, restart and replay after allowance change return the
  original execution.
- Invalid initial owner/scope/product/metric/unit creates no durable acceptance.
- Caller denial after reservation but before outer commit rolls back session/job/reservation/
  counters/events. Inject a caller-controlled rejection without implementing AccessSnapshot,
  revision floor or Portal HTTP.
- Terminal scenario versus success yields one allowed outcome without overwriting terminal state,
  duplicate debit or publication after release.
- Unknown commit, failed recovery, lost lease and late worker preserve counters/publication.
- Same-cycle ID preserves used; new ID creates a separate bucket; old job/replay uses its old bucket.
- Guest execution crossing UTC windows completes against its original bucket.
- Migration/restart preserve legacy usage without recalculation.

Actual AccessSnapshot expiry while waiting for a bucket lock is ANY-766 integration acceptance.
ANY-507 independently proves the caller-owned transaction rollback necessary for it.

After focused suites, run canonical `quick-check`, `postgresql-check`, `full-check`,
`validate-docs`, `generate-docs --check`, `atoms-proof` and affected Compose/handoff smoke.
The PostgreSQL gate must actually execute the new marked tests. Stage-0 observations below are
not evidence that this unimplemented mechanism passes these checks.

## 5. Handoff to ANY-766

Deliver reviewed PR/SHA, compatible base, migration revision and:

- Exact internal types/signatures, trusted inputs, replay lookup and `is_replay`.
- First-binding/immutable-allowance validation.
- Acceptance/finalization/release/recovery boundaries and lock order.
- Migration/quiesce/rollback procedure and legacy-history preservation.
- Readback fixtures for busy, exhausted and unobserved.
- PostgreSQL commands, versions and actual results.

ANY-766 ordinary paid admission uses this semantic sequence (the `access.*` methods are ANY-766-owned
planned interfaces):

```python
# Authenticate and perform necessary snapshot HTTP outside the admission transaction.
# Try owner-scoped replay before requiring snapshot refresh for a new start.
with transaction_boundary(session_factory) as session:
    access.lock_user_floor(session, owner)
    replay = runtime.find_execution_replay(session, owner, replay_identity, request_hash)
    if replay is not None:
        accepted = replay
    else:
        access.require_current_locked(session, owner, expected_revision)
        accepted = runtime.start_session(
            ...,
            execution_owner=owner,
            paid_allowance=allowance,
            idempotency_key=key,
        )
        if not accepted.is_replay:
            access.require_current_locked(session, owner, expected_revision)
            # This final check runs after waiting for admission locks.
```

Only the outer boundary commits after the last check; denial rolls back new acceptance.
No `access.*` call performs HTTP under locks.
Immediate handoff follows the same order with the target product allowance and namespace
`handoff`/runtime handoff ID.

ANY-766 writes exhaustion outbox work from `became_exhausted` in the shared success orchestration
before that same commit, for both ordinary success and recovery.
It adds an explicit transactional write, not a second debit path or generic callback framework.

PLAN-5 stays intact: guest total used includes immutable legacy usage; capacity-reserved handoff is
retryable; new metered jobs use terminal arbitration without changing legacy reconciliation.
Portal predecessor handoffs gate only the corresponding integration.

## 6. Stage-0 checkpoint — 2026-11-04

Historical evidence below describes stage 0 only. Its unstarted stages and debit-on-start observations
are superseded by the current stage statuses and checkpoints 7–8; they are not current runtime rules.

### Baseline and verification scope

- Branch: `feature/ANY-507`. HEAD/local `main`/local tracking `origin/main` all resolve to
  `2b4920999e7839b12e90b6b05cd6dc0667e5e7b4`. This stage did not refresh the remote ref.
- `git merge-base --is-ancestor 331e086c HEAD` passed. ANY-711 registry/manifest/metric/scope
  implementation and handoff are present; manifest service authentication is not paid-user auth.
- `alembic -c migrations/platform/alembic.ini heads` reports only `0015 (head)`.
  No deployed database was inspected or migrated. Stage 1 must recheck the head before allocating
  `0016`.
- At entry only the supplied ANY-507 and ANY-766 plan files were untracked. No tracked source diff
  was present. Neither plan was previously a committed implementation handoff.
- Peer sources were read from Portal commit
  [`b727b44589ae20dffb8248e94f2da383f8f7f1a0`](https://github.com/gushinets/payments-portal/commit/b727b44589ae20dffb8248e94f2da383f8f7f1a0):
  AGENTS, architecture and the accepted access-contract design. The peer checkout has unrelated
  ANY-715 edits; only committed source was used. This is an observation, not an accepted final
  ANY-715/765 handoff or a Portal readiness claim.
- Portal's committed canonical access specification still describes V1 with calendar bounds.
  The provider-neutral no-calendar V2 wire in ANY-766 remains its coordinated spec/DTO/fixture
  change and review gate. Freezing this internal typed contract does not approve or implement V2.
- Existing runtime documentation/code still describes debit on accepted start. That remains current
  behavior until the implementation stages update it; stage 0 does not claim success-only charging
  is already available.

### Inspected transaction owners and attachment points

Paths below are repository-relative. They name existing seams, not new code shipped by this stage.

- `apps/platform-api/src/anytoolai_platform_api/routers/scenario_runtime.py`:
  `start_scenario` owns the ordinary-start `transaction_boundary`; `_runtime_service` composes
  session-bound Core repositories/services. ANY-507 replaces the accepted-start debit inside
  `ScenarioRuntimeService.start_session`. ANY-766 adds trusted authentication/access orchestration
  around this boundary and performs its final locked check before exit/commit.
- `apps/platform-api/src/anytoolai_platform_api/routers/handoffs.py`:
  `accept_handoff` owns the acceptance transaction and failure recovery orchestration;
  `HandoffService.accept` calls `ScenarioRuntimeService.create_linked_session`.
  ANY-507 shares reserve/replay/release with ordinary start and preserves lifecycle-lock cleanup
  after recovery. ANY-766 supplies the trusted owner and target allowance; inherited body
  `user_id` provides no authority.
- `packages/backend/platform-core/src/anytoolai_platform_core/storage/transactions.py`:
  `transaction_boundary` owns outer commit/rollback, then recovery and cleanup. Recovery opens a
  separate caller-owned transaction only after rollback. Reservation operations do not commit.
  Rejected candidate acceptance must never be recreated by rollback callbacks.
- `packages/backend/platform-core/src/anytoolai_platform_core/quotas/service.py` and
  `quotas/repository.py`: current guest policy/window resolution and conditional accepted-start
  debit. ANY-507 owns replacement with the common lifecycle and separate paid bucket storage.
- `packages/backend/platform-core/src/anytoolai_platform_core/workflows/runner.py`:
  `_run_started_job` currently creates the final artifact, marks success, then registers recovery.
  ANY-507 moves metered final publication and debit into one finalizer, registering immutable
  success recovery before finalization. The common normal/recovery success orchestration is the
  explicit pre-commit exhaustion-outbox attachment point for ANY-766.
- `packages/backend/platform-core/src/anytoolai_platform_core/artifacts/canonical.py` and
  `results/service.py`: canonical linkage/schema normalization and Result API forbidden-field guard.
  ANY-507 reuses the full availability criterion before consumption.
- `apps/platform-worker/src/anytoolai_platform_worker/handlers/run_workflow.py`:
  separate claim and execution boundaries, scenario completion, preclaim poison/disabled failure,
  cancellation and handler recovery. ANY-507 routes all metered terminal decisions through the
  shared finalizer/release, preserving the earlier durable claim event and JobLease.
  `reconciliation.py` calls `terminate_orphaned_job`; this is the orphan release attachment.
- Admission lock ordering: ANY-766 scoped user/floor precedes ANY-507 admission locks. Terminal
  writers use `job -> scenario -> reservation -> bucket`. Existing handoff lifecycle advisory
  ownership/cleanup remains outside its acceptance rollback. No new reverse lock dependency,
  HTTP or provider I/O is introduced under admission/terminal locks.
- `apps/platform-api/src/anytoolai_platform_api/routers/identity_quota.py` reads guest quota.
  ANY-507 supplies internal readback and guest fields; ANY-766 adds paid auth/HTTP quota and
  interservice usage. Readback creates no allowance.

### TEST-ONLY composition contract

Use the same explicitly supplied fixed fixture bundle through:

- `apps/platform-api/src/anytoolai_platform_api/bootstrap.py:build_runtime(bundles=...)`;
- `apps/platform-worker/src/anytoolai_platform_worker/composition.py:build_worker(bundles=...)`;
- `scripts/agent/validate_configs.py:load_registry(bundles=...)`.

All resolve `bundle.config_roots()` through the existing Core loader. Passing bundles replaces
production defaults. Passing worker `config_registry` bypasses bundle loading, so it cannot by
itself prove bundle parity. Do not add environment-driven runtime overrides or change any of the
three identical production `DEFAULT_PRODUCT_BUNDLES` sets.

Existing `fixture_bundle`/`fixture_product` in
`apps/platform-api/tests/test_bundle_composition.py` and
`tests/architecture/test_bundle_composition_parity.py` prove these seams. They are generic composition
fixtures, not a paid ANY-507 proof or the final ANY-766 staging bundle. That staging fixture uses the
same seams with identical API/worker content and keeps TEST-ONLY metric/Q approvals separate from
production enablement.

### Checks and limitations

Commands run from the Kernel root using managed Python 3.12.13 in `.quick-check-venv`, with
uv/node/npm on PATH:

```bash
python scripts/agent/runner.py quick-check --bootstrap-only
python scripts/agent/runner.py doctor
python -m alembic -c migrations/platform/alembic.ini heads
python scripts/agent/runner.py validate-configs
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
```

- **PASS:** managed-environment bootstrap using the repository's locked dependency workflow;
  `uv.lock` is unchanged. Bootstrap-only is not a completed baseline `quick-check` run.
- **PASS:** `doctor`; pytest, yaml, pydantic, uv, node and npm are available. Docker reports an
  optional-tool warning; a usable Docker daemon/deployment has not been established.
- **PASS:** Alembic reports one `0015 (head)`; an additional AST check confirms 15 revisions,
  a single head and no missing predecessor.
- **PASS:** `validate-configs`, `validate-docs` and `generate-docs --check`.
- **PASS:** a direct composition probe supplied the same existing `FixtureProductBundle` to API,
  worker and validator, comparing products, scenarios, workflows, action configurations and schemas.
  It also confirmed production fixture exclusion. A SQLite engine was used only to construct the
  worker graph; no database/workflow execution or paid-runtime proof was performed.

**PASS:** the focused six-file regression suite below completed with exit code 0, covering bundle
composition, documentation validation and the existing ANY-711 manifest/auth/scope/fixture baseline.
This is baseline evidence, not success-only consumption acceptance.

The focused regression command is:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True python -m pytest -q -o faulthandler_timeout=30 \
  tests/architecture/test_bundle_composition_parity.py \
  apps/platform-api/tests/test_bundle_composition.py \
  tests/test_validate_docs.py \
  apps/platform-api/tests/test_capability_manifest.py \
  apps/platform-api/tests/test_capability_manifest_contract.py \
  apps/platform-api/tests/test_capability_projection.py
```

The initial shell had no `python`; its `python3` could not import `tomllib`. An available bare
Python 3.14 lacked dependencies. A compatible existing Python 3.12 environment allowed initial
doctor/migration inspection, but was not a complete Kernel environment. The canonical bootstrap
then prepared the dedicated managed environment; the initial sandbox PyPI DNS failure was resolved
by rerunning bootstrap with network access. No peer environment or source was modified.

The initial sandbox regression run was interrupted after an in-process HTTP test stalled; its
partial dots are not a PASS. The focused command above was rerun outside the sandbox. The local
model-cost-map setting avoids unrelated LiteLLM metadata-fetch warnings seen during the successful
generated-docs/composition probes. These are environment observations, not implementation failures.

**NOT_RUN:** `postgresql-check`, migrations against a live database, the complete `quick-check`,
`full-check`, atoms/Compose smoke and real Portal integration. They are not stage-0 proof requirements.
`ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset, so later PostgreSQL acceptance needs a disposable
maintenance database. No runtime feature, production approval, sale or real Portal acceptance is
claimed. Portal ANY-715/765 readiness is not a blocker for the independent ANY-507 mechanism.

### Progress and decisions

- [x] Read the complete ANY-507/766 plans, root instructions and relevant ownership/runtime sources.
- [x] Freeze shared types, replay/bucket invariants, caller transaction ownership and ANY-766 seams.
- [x] Recheck Kernel baseline, ANY-711 ancestry and migration graph head.
- [x] Complete/record the supported stage-0 environment and composition checks.
- At stage 0, stages 1–5 were unstarted and outside that instruction; see later checkpoints.

The stage-0 instruction stopped at preparation. Its later PostgreSQL/canonical checks and reviewed
implementation handoff were still future work at that checkpoint; later results are recorded below.

## 7. Stage-3 checkpoint — 2026-11-04

**Done:** atomic result publication/debit, terminal release and durable-state-first recovery.
Terminal arbitration, original buckets, causal event backfill and event dimensions are covered.

**PASS:** 43 focused PostgreSQL tests plus 2 final event-dimension cases; `postgresql-check`
(602 tests before the final focused fixes); `frontend-check`; 226 product tests;
`atoms-proof` (11/11 atoms, 3/3 composites); doctor, config, architecture, docs and generated checks.

At this stage-3 checkpoint, stages 4–5 and ANY-766 integration were not started.

## 8. Stage-4 checkpoint — 2026-11-04

**Implemented:** scoped single-query `ConsumptionReadback`; expanded guest quota HTTP with
successful/legacy used, reserved, available and aware read time; atomic reserve/consume/release
and capacity-rejection events; CE-kit parser/classifier; shared web terminal refresh and same-key/
same-token busy retry; seven locale catalogs; regenerated OpenAPI/types/event catalog and aligned
runtime/MVP docs. Unknown buckets stay unobserved; storage failure never becomes zero usage.
See [quota contracts and ownership](../../architecture/quota-model.md).

**PASS:** `postgresql-check` (615 tests); `frontend-check`; 226 product backend tests; 30 schema/docs
regressions; doctor, docs/generated checks, focused Ruff and diff checks. Focused proofs additionally
cover one-query/scoped readback, legacy contribution, exactly-once recovery events, all guest/paid
terminal releases, last-unit audits and same-token HTTP handoff retry after real release. All 427
web tests pass; final CE-kit parser/lifecycle/type checks pass.

**PASS:** canonical `atoms-proof` (11/11 atoms, 3/3 composites) and `proposal-ai-smoke` (10/10
Chromium scenarios) over isolated real API/worker/PostgreSQL with deterministic fake providers.
These are local mechanism/client proofs, not deployment or Portal evidence.

**FAIL (environment):** final `full-check` with `PYTEST_ADDOPTS=-x` stops in its canonical
quick-check baseline: 407 passed, 1 failed, 615 deselected. The failed test is
`tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`:
`sudo: a password is required`, independently reproduced and also present in stage 3's full-check
log. Earlier unbounded quick/full runs were interrupted after this failure was confirmed. No test
bypass/skip or infrastructure change was added; frontend and product checks ran separately.
Canonical sanitized failure context was collected. This is not a green full-check/activation gate.

**NOT_RUN:** Compose activation and headed extension handoff smoke (no display/Xvfb). Backend HTTP
handoff, component handoff and Chromium web execution pass separately. ANY-766 retains paid HTTP,
AccessSnapshot/floor/cache/invalidation, interservice usage/exhaustion and outbox ownership; its plan
was used read-only. Stage 5/cutover and peer repository changes are not started. Stop after stage 4.

## 9. Documentation review follow-up — 2026-11-04

**Done:** checked current architecture/product/client docs against the implemented Core/API/CE-kit
contracts and ANY-766's ownership. Corrected stale consumption-at-start text and quota event list,
old scenario replay/savepoint descriptions, handoff TTL versus accepted replay, terminal-scenario
arbitration and recovery boundaries. Completed readback/HTTP/event field descriptions and metering
table inventories. Explicitly separated historical plan evidence and the demo's independent daily
admission cap from current product quota. Updated older active-plan wording where it implied an
obsolete current rule; completed historical plans remain evidence of their original implementation.

**PASS:** doctor, `validate-docs`, `generate-docs --check`, 21 documentation/generator tests and diff
checks. A source cross-check confirms all 6 quota events, 10 readback fields, 5 added HTTP fields and
both metering tables in current inventories. No remaining contradiction found in the reviewed
ANY-507 documentation. Runtime code, the ANY-766 plan and stage-5 activation remain unchanged.
