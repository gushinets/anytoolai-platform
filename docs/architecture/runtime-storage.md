# Runtime Storage

This document describes the SQLAlchemy-backed runtime storage slice for MVP-A.

It covers the design that was implemented for:

- `platform.scenario_sessions`
- `platform.jobs`
- `platform.action_runs`
- `platform.provider_calls`
- `platform.artifacts`
- `platform.guest_identities`
- `platform.guest_quota_usage`
- `platform.paid_allowance_usage`
- `platform.execution_reservations`
- `platform.allowance_exhaustion_outbox`
- `platform.product_handoffs`
- `platform.atom_lab_runs`
- `platform.model_catalog_state`

This is the durable runtime state layer for execution. It is not config storage.

`platform.model_catalog_state` is the narrow Atom Lab exception for one last-good OpenAI model
catalog snapshot per configured account scope. Its row owns TTL scheduling, manual refresh
coalescing, a crash-expiring worker lease, last-success time, and a safe last error. It is not a
workflow job and never creates scenario, action, artifact, event, or provider-call ledger rows.

## Scope

The runtime storage slice lives in these files:

- `migrations/platform/env.py`
- `migrations/platform/versions/0001_runtime_tables.py`
- `migrations/platform/versions/0003_guest_quota.py`
- `migrations/platform/versions/0004_handoffs.py`
- `migrations/platform/versions/0005_provider_calls_error_message_safe.py`
- `migrations/platform/versions/0007_guest_quota_dimension.py`
- `migrations/platform/versions/0008_handoffs_compat.py`
- `migrations/platform/versions/0010_handoffs_index_compat.py`
- `migrations/platform/versions/0012_atom_lab_runs.py`
- `migrations/platform/versions/0013_model_catalog_state.py`
- `migrations/platform/versions/0016_execution_reservations.py`
- `migrations/platform/versions/0017_guest_legacy_usage.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/storage/db.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/storage/transactions.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/scenarios/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/workflows/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/actions/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/providers/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/providers/catalog_repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/artifacts/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/identity/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/quotas/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/quotas/execution_repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/handoffs/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/atom_lab/repository.py`
- `packages/backend/platform-core/tests/unit/test_runtime_storage.py`

The runtime storage slice does not cover:

- config registry storage
- `platform.event_log` schema ownership, although rollback recovery now queries event-log existence
  to backfill missing lifecycle events
- product definition tables
- billing tables
- admin editing flows

## Migration Chain

The canonical runtime migration chain is append-only; new runtime state is added by a new revision.

For the Provider Gateway ADR-0007 realignment:

- `0001_runtime_tables.py` was realigned in place so fresh `upgrade head` creates the
  ADR-0007-compatible `platform.provider_calls` ledger directly
- `0002_event_log.py` now creates `platform.event_log` with the canonical
  `provider_policy_ref` correlation column for fresh installs
- `0005_provider_calls_error_message_safe.py` preserves the provider-call error-message
  compatibility change
- `0006_event_log_provider_policy_ref_compat.py` renames the old
  `platform.event_log.provider_policy_id` column to `provider_policy_ref` for databases already
  upgraded through the previous chain
- `0003_guest_quota.py` owns the current guest quota dimension schema for clean databases
- `0007_guest_quota_dimension.py` is a compatibility upgrade for databases already upgraded
  through the original A13 guest quota migration before `0003` was baseline-folded; its downgrade is
  a no-op because the current `0006` schema already includes the dimension fields from `0003`
- `0004_handoffs.py` creates the final `platform.product_handoffs` schema for clean databases
- `0008_handoffs_compat.py` creates that table only when absent, repairing databases stamped past
  the historical placeholder `0004`; its downgrade is intentionally a no-op so downgrading a
  compatibility marker never destroys backend-owned handoff history
- `0010_handoffs_index_compat.py` repairs already-upgraded handoff tables by dropping the obsolete
  target-session index and ensuring the canonical `status + expires_at` index exists; its downgrade
  restores the legacy target-session index for the historical revision boundary
- `0012_atom_lab_runs.py` adds the immutable Atom Lab admission snapshot linked one-to-one to its
  scenario session and job; action/artifact links remain nullable until execution creates them
- `0016_execution_reservations.py` prepares success-only metering storage without activating the
  admission/finalization mechanism; its stage boundary is described below

### Execution metering storage (ANY-507 stage 1)

Stage 2 connects this schema to ordinary-start/immediate-handoff admission using one caller-owned
savepoint for session, job, reservation and counter writes. Admission changes `reserved_count`,
not historical usage. Revision `0017` reconciles the historical guest contribution at quiesced
application cutover as total used minus consumed guest reservations, retaining all successful
usage, active reserves and result history. Old admission must stay stopped after reconciliation. The
[quota model](quota-model.md) records the reserve/replay, terminal recovery and client/readback
contracts implemented through stage 4. Stage 5 still owns cutover/activation verification.

Revision `0016` appends to `0015`. It preserves every existing identity, scope, usage count and runtime
row. Guest usage gains `reserved_count=0` and `legacy_used_count=used_count`. Successful guest usage
will be the difference `used_count - legacy_used_count`; migration never labels historical attempts
as successful and never refunds or reassigns a window. Historical usage may exceed a later policy
limit, so the new guest constraints do not require `used_count <= limit_count`.

`paid_allowance_usage` stores one bucket per `tenant_id + region + allowance_id`, independent of
guest policies/windows. Its owner/product/metric/unit/quantity tuple is immutable: repository
insert-or-select rejects conflicting bindings, and a PostgreSQL trigger rejects direct SQL
rebinding. Quantity and used/reserved counters are `BIGINT`; quantity is limited to `0..2^53-1`,
counters are nonnegative, and their sum cannot exceed quantity. The typed `PaidAllowance` excludes
boolean/fractional quantities and requires a canonical Portal UUID owner. Metric and unit strings
come from the registry; checking their product membership belongs to stage-2 admission, not storage.
A read returns no row for an unobserved allowance and creates no bucket.

`execution_reservations` stores the original owner, session/job, product/scenario/frontend,
guest-or-paid bucket, optional replay namespace/key/hash and final result linkage. Foreign keys
protect all bucket/runtime/handoff/result references. Checks require exactly one bucket matching the
owner kind, complete replay identity (mandatory for paid), and a final artifact only for `consumed`.
`handoff` replay uses the stable runtime handoff ID. Unique constraints cover session, job, and
`tenant + region + owner kind/id + product + scenario + namespace + replay key`; allowance ID is
excluded so replay can retain its original bucket across cycles. Repository creation validates
owner/scope/product/scenario/frontend links and exposes no generic identity-changing update.

Jobs have the server-owned `JobConsumptionMode`: `legacy | unmetered | reserved`. Historical jobs
remain `legacy`; new metered jobs are `reserved` and other starts are `unmetered`. Migration preserves
both guest `used_count` and its historical `legacy_used_count` contribution. Job repository updates
cannot change the mode.
PostgreSQL deferred constraint triggers require exactly one reservation for a `reserved` job and no
reservation for other modes, at transaction completion. This permits job-then-reservation insertion
while rejecting a committed reserved job with a missing reservation. SQLite metadata construction
does not provide this PostgreSQL trigger guarantee.

`PaidAllowanceUsageRepository` and `ExecutionReservationRepository` live in
`quotas/execution_repository.py`, accept the caller's `Session`, and never commit or roll back it.
They supply storage binding, creation and lookup. ANY-507 stages 2–4 connect reserve/replay,
transactional publication/release/recovery and readback through Core quota services. Portal authority,
AccessSnapshot and paid HTTP remain ANY-766 responsibilities.

Downgrade to `0015` is refused once paid buckets or reservations exist; restoring an old runtime after
activation requires the coordinated backup/quiesce procedure from the
[execution plan](../exec-plans/completed/ANY-507-implementation-plan.md). Upgrade was designed to leave
old tables intact, and repeated `upgrade head` does not backfill legacy usage a second time.

### Atom Lab run snapshots

`platform.atom_lab_runs` is a narrow laboratory-owned exception to the general rule that definitions
live only in YAML/Markdown. It does not replace the config registry or execution ledgers. It records
the immutable settings accepted for one internal Atom Lab job: exact definition identities and
versions, full saved workflow/action/config/schema documents, base and edited prompt, exact input,
selected model and reasoning effort, snapshotted provider limits, capability provenance, preset
version, and a canonical definition hash.

The snapshot is created in the same caller-owned transaction as its already-created laboratory
scenario session and job. `AtomLabRunRepository` rejects ordinary sessions and inconsistent runtime
dimensions. The worker reloads the snapshot by job, verifies its definition hash and registry
compatibility, and fails explicitly with `atom_lab_snapshot_incompatible` when it cannot reproduce
the admitted run. It never silently migrates to current definitions.

`action_run_id` and `artifact_id` are fill-once execution links. Existing `action_runs`, `artifacts`,
and `provider_calls` remain the only execution/result ledgers; `atom_lab_runs` is admission
provenance, not a second executor history.

This keeps fresh installs and already-upgraded databases on the same final schema.

### Handoff storage and transition enforcement

`platform.product_handoffs` stores the hashed token, source and target dimensions, explicit policy,
mapped context and preview JSON, safe failure code/metadata, and timestamps for every lifecycle
state. It has a unique token hash, unique nullable target-session linkage, foreign keys to runtime
sessions/jobs/artifacts, and indexes for definition, source session, and status/expiry lookups.

`HandoffRepository` follows the caller-owned transaction rule but deliberately does not expose a
generic status-changing update. `mark_viewed`, `claim_accept`, `decline`, `expire_if_due`,
`consume`, and `mark_failed` use conditional SQL updates. The acceptance compare-and-swap is the
storage-level double-accept guard. Token-driven lifecycle operations also acquire a PostgreSQL
session-level advisory lock keyed by `handoff_id`; `transaction_boundary()` releases it with a
cleanup callback only after commit or rollback recovery completes. This lets immediate accept roll
back its temporary `accepted` claim while still serializing decline/expiry until quota recovery has
committed the terminal outcome.

`finalize_quota_failure_recovery` conditionally changes an unclaimed `created`/`viewed` row directly
to `failed`; the same critical recovery transaction persists safe `quota_exhausted`, quota audit
state, and all recovery events. It never commits an intermediate `created/viewed + error_code`
reservation. If recovery cannot persist this state and the `quota.checked` / `quota.exhausted` pair,
the accept path must not return `429 quota_exhausted`. `attach_target` validates that the record is
accepted and the target rows belong to the same tenant/region and expected target session. State,
linkage, quota, and events therefore commit or roll back together.

### Provider Policy Ref Compatibility

The provider-policy migration fix matters because the runtime contract had drifted across two
surfaces:

- config, provider-call storage, and Provider Gateway runtime code already used
  `provider_policy_ref`
- the historical `0002_event_log.py` migration still created `platform.event_log.provider_policy_id`

The canonical runtime field name is now `provider_policy_ref` everywhere that the platform stores
or emits provider-policy identity.

Final upgrade behavior:

- fresh databases get `platform.event_log.provider_policy_ref` directly from
  `0002_event_log.py`
- databases that were already upgraded through the older chain reach the same schema through
  `0006_event_log_provider_policy_ref_compat.py`, which renames
  `platform.event_log.provider_policy_id` to `provider_policy_ref`

This means the durable storage contract no longer depends on whether a database was created after
the baseline migration cleanup or upgraded from an older local/dev chain.

The provider-event correlation contract also became explicit at the event-log table level. Provider
request events now persist correlation both as top-level `platform.event_log` columns and inside
`event_log.properties`, so joins remain deterministic while the JSON properties still preserve the
full provider-attempt context.

## SQLAlchemy Choice

The implementation uses SQLAlchemy Core tables plus small repository classes.

It does not use SQLAlchemy ORM mapped classes.

That choice was intentional:

- the repo already used simple frozen dataclasses for core models
- there was no existing ORM convention to preserve
- the MVP-A storage requirements are CRUD-oriented and explicit
- the task required caller-owned transaction boundaries
- Core tables are enough for inserts, selects, updates, indexes, and migration DDL

The current package dependency is `sqlalchemy>=2.0`, and the repo lock currently resolves to the
SQLAlchemy `2.0.x` line.

## Storage Layers

The implementation is split into four layers.

### 1. Migration layer

`migrations/platform/versions/0001_runtime_tables.py` defines the durable schema for the initial
runtime tables, and later revisions extend that shared storage slice with quota and handoff state.

Responsibilities:

- create the `platform` schema when the backend dialect supports schemas
- create the original execution runtime tables
- create indexes for common runtime lookups
- define the initial enum constraints at the database level
- support downgrade for the same tables

`migrations/platform/env.py` was also turned from a placeholder into a minimal working Alembic env
so tests and future commands can execute migrations programmatically. The env bootstrap now adds the
repository root before branching into offline vs. online mode, which keeps shared migration helper
imports working even when Alembic runs from a different current working directory.

The repo also keeps a checked-in `migrations/platform/alembic.ini` for explicit CLI invocations
such as `uv run alembic -c migrations/platform/alembic.ini upgrade head --sql`. Compatibility
revisions that inspect live schema state remain online-only in practice; during offline SQL
generation they either no-op because the baseline revisions already own the final schema or emit the
canonical handoff-index cleanup SQL needed for fresh-install `head` output.

For `product_handoffs` compatibility work specifically, historical revisions keep their
table/index checks inline so recorded Alembic behavior does not depend on mutable helper modules.
`0008_handoffs_compat.py` intentionally keeps its schema-qualified `has_table(...)` guard
self-contained, and later handoff compatibility logic follows the same revision-local pattern.

### 2. Shared SQLAlchemy table layer

`packages/backend/platform-core/src/anytoolai_platform_core/storage/db.py` is the shared storage
source of truth for table objects.

Responsibilities:

- define `PLATFORM_SCHEMA`
- define a shared `MetaData`
- define the shared runtime `Table(...)` objects, including guest identity, quota, and handoff state
- define reusable SQLAlchemy types
- expose a small engine factory

Important shared helpers in this file:

- `UtcDateTime`
  - requires timezone-aware datetimes on write
  - normalizes result values back to UTC-aware datetimes
- `_json_document_type()`
  - uses generic SQLAlchemy `JSON`
  - swaps to PostgreSQL `JSONB` on the PostgreSQL dialect
- `_enum_type(...)`
  - stores enum values as validated strings
  - avoids depending on database-native enums for this MVP slice

### 3. Repository layer

Each runtime entity has a small repository class:

- `ScenarioSessionRepository`
- `JobRepository`
- `ActionRunRepository`
- `ProviderCallRepository`
- `ArtifactRepository`
- `GuestIdentityRepository`
- `QuotaUsageRepository`
- `HandoffRepository`

Repository responsibilities:

- `create(record)`
- `get(id)`
- `update(record)`

`AtomLabRunRepository` is the immutable, fill-once exception. It provides `create(record)`, lookup
methods, and `bind_runtime_ids(...)`; the latter fills nullable execution links exactly once instead
of exposing `update(record)`. It also validates that those links remain within the snapshot's
laboratory-owned scenario and job.

Repository non-responsibilities:

- opening the database engine
- owning transactions
- calling `commit()`
- handling cross-entity orchestration
- doing business-level validation beyond what the DB schema enforces

### 4. Record model layer

The repository return type is a frozen dataclass record, not an ORM instance.

These records live next to the rest of the domain models:

- `scenarios/models.py` -> `ScenarioSessionRecord`
- `workflows/models.py` -> `JobRecord`
- `actions/models.py` -> `ActionRunRecord`
- `providers/models.py` -> `ProviderCallRecord`
- `artifacts/models.py` -> `ArtifactRecord`
- `identity/models.py` -> `GuestIdentityRecord`
- `handoffs/models.py` -> `HandoffRecord`
- `atom_lab/models.py` -> `AtomLabRunRecord`

This keeps the runtime storage surface aligned with the repo's existing model style.

## Why Frozen Dataclass Records

The runtime records are database-backed, but they are not treated as active ORM entities.

They are immutable snapshots passed into and out of repositories.

That has a few advantages for this repo:

- no hidden session-attached object behavior leaks into domain code
- no lazy loading or implicit flushes
- repository outputs are easy to compare in tests
- transaction ownership stays explicit
- the runtime record style matches the existing config/domain dataclass style

The tradeoff is also explicit:

- the dataclass fields and SQLAlchemy table columns must be kept in sync manually

For MVP-A that tradeoff was acceptable because the storage slice is still small and explicit.

## Transaction Boundary Pattern

Transaction ownership belongs to the caller.

This is implemented in:

- `packages/backend/platform-core/src/anytoolai_platform_core/storage/transactions.py`

The main helpers are:

- `build_session_factory(engine)`
- `transaction_boundary(session_factory)`

Rules:

- repositories may `flush()`
- repositories must not `commit()`
- callers decide whether a unit of work commits or rolls back

This was chosen because the task explicitly required an explicit transaction boundary and no hidden
commit behavior inside repositories.

Escaped rollback recovery also lives in `storage.transactions.py`. Recovery callbacks register with
explicit rollback phases instead of depending on accidental FIFO callback order. The current
contract separates:

1. quota-rejection recovery: exhaustion re-ensures the usage dimension and checked/exhausted audit;
   temporary capacity rejection records its observed snapshot without recreating execution;
2. row recovery for runtime tables such as `platform.artifacts`, `platform.provider_calls`,
   `platform.action_runs`, and `platform.jobs`;
3. event recovery that backfills only missing `platform.event_log` rows in causal order.

This lets the runtime rebuild durable history after a rollback without introducing a durable
workflow engine. Recovered rows become the source for replayed timestamps and correlation values,
while event-level existence checks prevent duplicate event-log rows when recovery runs against
partial durable state.

Rollback recovery callbacks can be marked critical when the caller must not return its normal
domain error unless recovery succeeds. Handoff quota exhaustion uses this path: a returned
`429 quota_exhausted` proves the `failed` handoff and quota audit pair are already durable.
Reserved success recovery is also critical: its final artifact and debit cannot recover
independently. Non-critical workflow/action/provider/debug-artifact callbacks keep their earlier
behavior, attaching failures as notes to the original exception. Handoff capacity-rejection audit
is critical too, but leaves the token retryable and never marks it failed or creates a target.

## Common Runtime Dimensions

Every runtime row carries the shared execution dimensions required by MVP-A where applicable.

These include:

- `tenant_id`
- `region`
- `product_id`
- `frontend_id`
- `scenario_session_id`
- `job_id`
- `action_run_id`
- workflow and step identifiers where applicable

This keeps runtime state queryable along the same dimensions used across execution, events, and API
contracts.

## Table Design

### `platform.scenario_sessions`

Purpose:

- the root durable record for every scenario start

Key columns:

- identity and tenant dimensions
- `scenario_id`
- `scenario_version`
- `status`
- checkpoint/step progression fields
- `metadata`
- `created_at`
- lifecycle timestamps

Scenario session status values:

- `started`
- `waiting_for_user`
- `running`
- `completed`
- `failed`
- `expired`

### `platform.jobs`

Purpose:

- track workflow execution attempts linked to a scenario session

Key columns:

- `scenario_session_id`
- `workflow_id`
- `workflow_version`
- `status`
- `input_artifact_id`
- `result_artifact_id`
- safe error fields
- lifecycle timestamps
- `metadata`

Job status values:

- `created`
- `running`
- `succeeded`
- `failed`
- `canceled`

### `platform.action_runs`

Purpose:

- track execution of a specific workflow step/action configuration

Key columns:

- `scenario_session_id`
- `job_id`
- `workflow_id`
- `step_id`
- `action_type`
- `action_config_id`
- `status`
- input/output artifact links
- timestamps

Action run status values:

- `created`
- `running`
- `succeeded`
- `failed`
- `canceled`
- `skipped`

### `platform.provider_calls`

Purpose:

- persist provider gateway physical attempts and their safe operational metadata

Key columns:

- all common dimensions through action-run granularity
- `workflow_version`
- `provider_policy_ref`
- `provider`
- `model`
- `gateway_backend`
- `gateway_model`
- `semantic_attempt_index`
- `transport_attempt_index`
- `physical_call_index`
- `status`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `latency_ms`
- `estimated_cost`
- `error_code`
- `error_message_safe`
- `failure_kind`
- `http_status`
- `pydantic_run_id`
- `litellm_response_id`
- timestamps

Provider call status values:

- `created`
- `running`
- `succeeded`
- `failed`
- `timed_out`

These fields were chosen to match the ADR-0007 provider-gateway contract. The row is a runtime
ledger entry for one physical ProviderGateway attempt, not one logical high-level request.

Invariants:

- one `provider_calls` row == one physical transport attempt
- validation retries create additional rows
- transport retries create additional rows
- rows are created by the gateway, not by LiteLLM callbacks or synthetic bookkeeping

Additional safe operational details such as timeout metadata, retry metadata, request/correlation
ids, fixture selection, and response annotations may be stored in the row `metadata` JSON. Raw
prompt bodies, secrets, and unsafe payloads should not be persisted there.

Provider-call persistence is gateway-owned. The gateway may receive an explicit
`provider_call_repository` dependency or may construct `ProviderCallRepository(session)` from a
caller-owned session, but it must not own commits.

Retry ownership stays split across runtime layers:

- LiteLLM transport uses `retry_policy.transport`
- PydanticAI validation uses `retry_policy.validation`
- the gateway enforces
  `retry_policy.hard_limits.max_physical_provider_calls_per_action`

Provider-call rows should be written only when required execution dimensions are valid. If required
dimensions such as `tenant_id` or `region` are missing or blank, the gateway should skip
`provider_calls` persistence rather than writing an invalid row.

Failure rows should persist safe platform-facing error codes, not raw exception class names, while
still keeping safe operational metadata for debugging.

When the shared event emitter is configured on `ProviderGateway`, provider request lifecycle events
should be emitted through that emitter before or alongside persistence work, so invalid required
event dimensions fail fast and do not leave behind unsafe provider-call rows.

Provider-event correlation data is persisted in both top-level `platform.event_log` columns and
`event_log.properties`, including:

- `provider_call_id`
- `action_run_id`
- `provider_policy_ref`
- `physical_call_index`
- `semantic_attempt_index`
- `transport_attempt_index`
- `pydantic_run_id` when present
- `litellm_response_id` when present

### `platform.artifacts`

Purpose:

- persist runtime outputs and intermediate materialized results

Key columns:

- `artifact_type`
- `status`
- `content_text`
- `content_json`
- `object_storage_key`
- `metadata`
- `created_at`

Artifact status values:

- `created`
- `stored`
- `failed`

Artifact content behavior:

- text stays in `content_text`
- structured JSON stays in `content_json`
- object storage remains a future extension point through `object_storage_key`

### `platform.guest_identities`

Purpose:

- persist opaque frontend-safe guest identifiers created by the API

Key columns:

- `id`
- `tenant_id`
- `region`
- `created_at`
- `last_seen_at`
- `metadata`

Guest identity is intentionally product-neutral. Product access is enforced by quota usage rows and
product policy resolution, not by encoding product meaning into the guest id.

### `platform.guest_quota_usage`

Purpose:

- persist backend-owned guest quota state for access-lite products

Key columns:

- `tenant_id`
- `region`
- `guest_id`
- `product_id`
- `quota_policy_id`
- `quota_dimension`
- `dimension_key`
- `scenario_id` nullable
- `period_key`
- `limit_count`
- `used_count` (legacy plus successful consumption)
- `legacy_used_count` (preserved historical debit)
- `reserved_count` (active executions)
- timestamps and metadata

The unique runtime dimension is:

```text
tenant_id + region + guest_id + product_id + quota_policy_id + quota_dimension + dimension_key + period_key
```

For product-wide policies, `quota_dimension = product`, `dimension_key = product_id`, and
`scenario_id` is null. For scenario-specific policies, `quota_dimension = scenario`,
`dimension_key = scenario_id`, and `scenario_id` stores the scoped scenario.

Capacity reservation uses a locked conditional update:

```text
WHERE used_count + reserved_count < limit_count
```

Success moves one original reserve to used atomically with result publication; terminal failure
releases it without debit. Readback derives all counters from one row snapshot. This conditional
update is the concurrency guard for repeated or concurrent accepted starts.
It is independent from provider-call rows, transport retries, validation retries, and provider
usage/cost telemetry.

## JSON And Text Strategy

The artifact and metadata strategy was kept intentionally simple.

Rules:

- generic metadata columns use JSON
- PostgreSQL uses `JSONB` through SQLAlchemy type variants
- text artifacts are not coerced into JSON
- structured outputs can be stored directly as JSON

This supports MVP-A structured output work without introducing object storage or a custom document
layer too early.

## ID And Timestamp Conventions

The implementation reused existing repo helpers instead of inventing a new storage convention.

IDs:

- generated through `anytoolai_platform_core.common.ids.new_id(prefix)`
- current format is `prefix_<uuid4 hex>`

Examples:

- `scenario_session_<hex>`
- `job_<hex>`
- `action_run_<hex>`
- `provider_call_<hex>`
- `artifact_<hex>`

Timestamps:

- generated through `anytoolai_platform_core.common.time.utc_now()`
- expected to be timezone-aware UTC datetimes
- normalized at the SQLAlchemy type layer by `UtcDateTime`
- scenario sessions now carry both `created_at` and the existing lifecycle timestamps
  `started_at`, `last_event_at`, `completed_at`, and `expires_at`

## Index Strategy

Indexes were added for the runtime query paths explicitly called out in the task.

The implemented pattern covers:

- `scenario_session_id`
- `job_id`
- `product_id`
- `created_at`
- `status`

Not every table gets every index blindly. The indexes are applied where the column exists and where
that lookup is expected to matter for runtime querying.

## Repository Behavior

The repositories are intentionally boring and explicit.

`create(...)`:

- inserts the full record
- calls `flush()`
- reads the row back through `get(...)`
- returns the stored record snapshot

`get(...)`:

- selects by primary key
- returns `None` if not found
- maps SQLAlchemy row data into the frozen record dataclass

`update(...)`:

- updates by primary key
- raises `LookupError` when the row is missing
- calls `flush()`
- reads the row back
- returns the updated snapshot

This keeps behavior easy to read, easy to test, and easy to replace later if the runtime grows.

Job lifecycle operations add the worker coordination boundary without changing the repository's
caller-owned transaction rule:

- `claim_created(job_id)` conditionally changes only `created` to `running` and sets `started_at`;
- `cancel_created(job_id, metadata=...)` conditionally changes only `created` to `canceled`, sets
  `completed_at`, and may persist caller-supplied metadata in that same update;
- `mark_failed_from_created(...)` exists for poison-job terminalization when runtime integrity
  checks prove a `created` job cannot be executed safely;
- `mark_succeeded(...)` and `mark_failed(...)` conditionally transition only `running` jobs;
- the job service persists `workflow.started` in the claim transaction and `workflow.canceled` in
  the cancellation transaction;
- the worker-owned pre-claim cancellation path validates the linked scenario session before calling
  `cancel_created`, merges available `guest_id`, `user_id`, and `scenario_chain_id` into job
  metadata, and relies on the standard job-derived event context for cancellation dimensions;
- failed transitions always fill `completed_at`, `error_code`, and `error_message_safe`;
- the worker commits claim/start before opening the workflow execution transaction.

In the production PostgreSQL worker path, job coordination is lease-first. Multiple independent
workers can discover the same `created` job id, but each handler attempts the PostgreSQL advisory job
lease before it calls `claim_created(job_id)`. Only the lease winner proceeds to the conditional
repository transition. Lease losers return before the repository claim and never invoke the workflow
runner.

Critical job invariants are repository-enforced, not just conventional:

- job creation requires a real scenario-session row with matching tenant/region/product/frontend
  dimensions;
- successful terminal transitions require `completed_at` plus an existing final artifact linked back
  to the same job and `scenario_session_id`;
- unrestricted `update(...)` is limited to same-status mutations so lifecycle status changes must go
  through explicit repository transition methods.

Repeated claims and claims of terminal jobs are no-ops. The advisory lease is not permanent job
ownership, queue assignment, or an external queue engine; it is a session-scoped PostgreSQL
coordination primitive held while the worker processes the job. The conditional repository update
remains necessary because a lease winner may still find that the job is no longer `created` after
cancellation, terminalization, or a stale retry. The runnable worker performs minimal PostgreSQL
polling to discover a created job id; the lease plus conditional update, not the discovery query,
own execution idempotency.

## Testing Strategy

The storage slice is covered in:

- `packages/backend/platform-core/tests/unit/test_runtime_storage.py`

The test approach is important:

- it runs the real Alembic migration chain through `head`
- it verifies CRUD against the migrated schema
- it provisions a disposable PostgreSQL database from
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`
- it exercises the real `platform` schema layout against the production PostgreSQL dialect

Run the runtime-storage suite with a PostgreSQL maintenance database URL:

```powershell
$env:ANYTOOLAI_POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -m "slow and postgresql" -q
```

The suite creates and drops disposable databases, applies the real Alembic migration chain, then
verifies repository CRUD, schema constraints, compatibility upgrades, and explicit transaction
behavior against PostgreSQL.

The reusable disposable-database helpers live in `tests/db_support.py`. Root `conftest.py` remains
pytest wiring only; tests import the helper module explicitly instead of treating `conftest.py` as a
shared library.

Quota concurrency remains a separate PostgreSQL production-semantics check in:

- `apps/platform-api/tests/test_quota_concurrency_postgresql.py`

```powershell
$env:ANYTOOLAI_POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q
```

The test creates and drops a disposable database, applies Alembic migrations, then runs concurrent
scenario starts through the API transaction path. It verifies that PostgreSQL row locking and the
conditional quota update allow the first `N` reservations, return
`429 quota_capacity_reserved` while reserves occupy capacity and `429 quota_exhausted` after consumption, and keep session/job/quota/event counts consistent.

Worker claim concurrency has its own PostgreSQL production-semantics smoke in:

- `apps/platform-worker/tests/test_worker_claim_postgresql.py`

```powershell
$env:ANYTOOLAI_POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q
```

The smoke creates and drops a disposable database, applies Alembic migrations once during test setup,
seeds one runnable `created` job, then runs two composed workers with independent engines and
session factories against the same database. Both workers poll the real queue and reach a test-only
pre-lease synchronization point before delegating to the real PostgreSQL advisory lease. Exactly one
worker acquires the lease, only that worker reaches the real conditional claim, and the loser returns
without invoking the workflow runner. The smoke verifies both the successful `succeeded` terminal
path and the safe `failed` terminal path from a fresh session.

The backend GitHub Actions workflow uses the required `postgresql-quota-concurrency` job with a
disposable PostgreSQL service for all production-dialect tests. It runs the canonical
`python scripts/agent/runner.py postgresql-check` command, which selects every `postgresql`-marked
test under platform core/actions, platform API, and platform worker roots. Marker-driven root
selection automatically includes new PostgreSQL tests without maintaining file or node-ID lists.
Runtime-storage CRUD, migrations, quota/handoff concurrency, artifact/event recovery, API behavior,
and worker execution therefore share one PostgreSQL-backed gate; `quick-check` remains intentionally
DB-free and fast. Runtime and database-specific test infrastructure is PostgreSQL-only.

`python scripts/agent/runner.py quick-check` excludes `slow` tests with `-m "not slow"` so the
required fast path stays deterministic.

What the tests cover:

- migration applies on a clean database
- required fields fail at the DB layer
- create/read/update for all runtime repositories
- status transitions
- artifact text storage
- artifact JSON storage
- explicit transaction-boundary behavior

These checks now validate the implemented SQLAlchemy layer on the same PostgreSQL dialect used by
runtime state in production.

## Known Compromises

The current design intentionally accepts a few compromises:

### PostgreSQL verification is opt-in locally

The migration and repository suite now validates against disposable PostgreSQL databases, but local
execution still depends on `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`.

Why:

- the current repo baseline remains DB-free for fast checks
- PostgreSQL-backed validation needs an explicit disposable maintenance database URL

Consequence:

- local quick checks do not execute the storage migration/repository suite by default
- full runtime-storage validation now requires the PostgreSQL commands above

### Manual sync between tables and record dataclasses

Because the implementation uses SQLAlchemy Core plus frozen dataclass records, schema and record
shapes must stay aligned manually.

Why this was still acceptable:

- the runtime surface is still small
- the fields are explicit
- the repositories are simple
- the tests catch most drift quickly

## When To Revisit This Design

This SQLAlchemy design is appropriate while MVP-A storage remains:

- explicit
- small
- CRUD-oriented
- repository-driven

It should be revisited if the platform later needs:

- richer relational graphs
- ORM identity/session semantics
- complex query composition
- optimistic locking/versioned writes
- bulk execution patterns
- many cross-table workflows inside one storage layer

If those pressures appear, the likely next step is not to abandon SQLAlchemy, but to decide whether
the repo has grown enough to justify ORM mapped classes or a more formal storage service layer.


## Paid exhaustion outbox — ANY-766 Step 14

Migration `0021` adds `platform.allowance_exhaustion_outbox`. Its immutable columns
store the full V1 tuple, event type and UTC occurrence time; identity is unique
by tenant/region/user/allowance/event type. Successful normal and rollback-recovery
orchestration insert only on `became_exhausted` before the same commit. No consumer
or revision dimension is added to usage or replay. Existing usage is not backfilled
into events. Mutable delivery fields are state, next attempt, attempt count, paired
lease token/expiry and safe last error. A worker claims pending due rows with
SKIP LOCKED, sends outside SQL, then locks and checks the live lease using database
wall time before settlement. Crash/restart naturally resumes unresolved rows.
