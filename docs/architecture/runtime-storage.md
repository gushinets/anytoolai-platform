# Runtime Storage

This document describes the SQLAlchemy-backed runtime storage slice for MVP-A.

It covers the design that was implemented for:

- `platform.scenario_sessions`
- `platform.jobs`
- `platform.action_runs`
- `platform.provider_calls`
- `platform.artifacts`

This is the durable runtime state layer for execution. It is not config storage.

## Scope

The runtime storage slice lives in these files:

- `migrations/platform/env.py`
- `migrations/platform/versions/0001_runtime_tables.py`
- `migrations/platform/versions/0005_provider_calls_error_message_safe.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/storage/db.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/storage/transactions.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/scenarios/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/workflows/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/actions/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/providers/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/artifacts/repository.py`
- `packages/backend/platform-core/tests/unit/test_runtime_storage.py`

The runtime storage slice does not cover:

- config registry storage
- `platform.event_log` schema ownership, although rollback recovery now queries event-log existence
  to backfill missing lifecycle events
- quota tables
- handoff tables
- product definition tables
- billing tables
- admin editing flows

## Migration Chain

The canonical runtime migration chain remains the existing files only.

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

This keeps fresh installs and already-upgraded databases on the same final schema.

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

`migrations/platform/versions/0001_runtime_tables.py` defines the durable schema for the runtime
tables.

Responsibilities:

- create the `platform` schema when the backend dialect supports schemas
- create the five runtime tables
- create indexes for common runtime lookups
- define the initial enum constraints at the database level
- support downgrade for the same tables

`migrations/platform/env.py` was also turned from a placeholder into a minimal working Alembic env
so tests and future commands can execute migrations programmatically.

### 2. Shared SQLAlchemy table layer

`packages/backend/platform-core/src/anytoolai_platform_core/storage/db.py` is the shared storage
source of truth for table objects.

Responsibilities:

- define `PLATFORM_SCHEMA`
- define a shared `MetaData`
- define all five `Table(...)` objects
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

Repository responsibilities:

- `create(record)`
- `get(id)`
- `update(record)`

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

1. row recovery for runtime tables such as `platform.artifacts`, `platform.provider_calls`,
   `platform.action_runs`, and `platform.jobs`;
2. event recovery that backfills only missing `platform.event_log` rows in causal order.

This lets the runtime rebuild durable history after a rollback without introducing a durable
workflow engine. Recovered rows become the source for replayed timestamps and correlation values,
while event-level existence checks prevent duplicate event-log rows when recovery runs against
partial durable state.

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
- `cancel_created(job_id)` conditionally changes only `created` to `canceled`;
- `mark_failed_from_created(...)` exists for poison-job terminalization when runtime integrity
  checks prove a `created` job cannot be executed safely;
- `mark_succeeded(...)` and `mark_failed(...)` conditionally transition only `running` jobs;
- the job service persists `workflow.started` in the claim transaction and `workflow.canceled` in
  the cancellation transaction;
- failed transitions always fill `completed_at`, `error_code`, and `error_message_safe`;
- the worker commits claim/start before opening the workflow execution transaction.

Critical job invariants are repository-enforced, not just conventional:

- job creation requires a real scenario-session row with matching tenant/region/product/frontend
  dimensions;
- successful terminal transitions require `completed_at` plus an existing final artifact linked back
  to the same job and `scenario_session_id`;
- unrestricted `update(...)` is limited to same-status mutations so lifecycle status changes must go
  through explicit repository transition methods.

Repeated claims and claims of terminal jobs are no-ops. No lease, distributed lock, or queue engine
is part of this MVP slice. The runnable worker performs minimal PostgreSQL polling to discover a
created job id; the conditional update, not the discovery query, owns claim idempotency.

## Testing Strategy

The storage slice is covered in:

- `packages/backend/platform-core/tests/unit/test_runtime_storage.py`

The test approach is important:

- it runs the real Alembic migration chain through `head`
- it verifies CRUD against the migrated schema
- it uses SQLite for lightweight CI compatibility
- it attaches a second SQLite database as the `platform` schema so schema-qualified table names are
  still exercised

What the tests cover:

- migration applies on a clean database
- required fields fail at the DB layer
- create/read/update for all five repositories
- status transitions
- artifact text storage
- artifact JSON storage
- explicit transaction-boundary behavior

This does not fully replace a PostgreSQL integration test, but it gives strong coverage of the
implemented SQLAlchemy layer while keeping the repo's current baseline checks fast and local.

## Known Compromises

The current design intentionally accepts a few compromises:

### SQLite-based verification

The migration was validated through real Alembic execution on SQLite with an attached schema, not on
a live PostgreSQL server.

Why:

- the current repo baseline is DB-light
- the task still needed real schema and repository verification

Consequence:

- PostgreSQL-specific behavior is represented through SQLAlchemy variants, but not fully exercised by
  a live PostgreSQL engine in the current baseline suite

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
