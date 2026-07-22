# Handoff Model

Handoff is a backend-owned, tokenized, user-confirmed transition from a completed source scenario
session to a config-declared target scenario. A Chrome Extension may request a handoff and open its
consent surface, but it never receives the hidden mapped context and never passes raw results to
another extension.

The implemented ownership chain is:

```text
Handoff API router
  -> HandoffService
    -> HandoffRepository
    -> HandoffPayloadBuilder
    -> ScenarioRuntimeService.create_linked_session(...)
    -> EventEmitter
```

## Definition contract

Each `handoffs.yaml` definition declares:

- stable `handoff_id`;
- source product and completed source scenario;
- target product, enabled frontend, and target scenario;
- `consent_required: true`;
- `target_start_policy`: `immediate` or `deferred`;
- `context_mapping`: target input field to `artifact.content_json...` path;
- `preview_mapping`: frontend-safe preview field to `artifact.content_json...` path.

The config loader rejects unknown or mismatched products/scenarios/frontends, disabled target
frontends, non-consensual definitions, missing mappings, and paths outside
`artifact.content_json`. Routes are therefore deployment-owned config, not arbitrary user-created
destinations.

## Canonical source artifact

Creation accepts only the selected completed source session's latest succeeded job result. The
selected artifact must be a stored JSON-object `structured_output`, belong to that session and job,
have no action-run owner, and carry `metadata.artifact_role: workflow_result` plus workflow/schema
metadata from normal finalization.

`HandoffPayloadBuilder` resolves only allowlisted config paths. The mapped target context must pass
the target workflow input schema. Raw provider responses, structured-output debug artifacts,
prompts, provider/model fields, provider-call metadata, and the complete source artifact are never
stored in the handoff row or returned to the frontend.

## Tokens and expiry

- Token format: `hnd_` plus `secrets.token_urlsafe(32)` (256 bits of random input).
- Storage: only `sha256(token).hexdigest()` is persisted; plaintext is returned once on creation.
- Default lifetime: 30 minutes; the service clock and TTL are injectable for tests.
- Expiry is enforced before preview, accept, and decline.
- Only `created` and `viewed` can expire. Consent already recorded as `accepted` does not later
  expire.
- Unknown tokens return safe `404`; accepting an expired token returns safe `410`.
- Request logs use the route template `/v1/handoffs/{handoff_token}` and never the plaintext token.

## Lifecycle and guarded operations

```text
created -> viewed -> accepted -> consumed
   |          |          \
   |          |           +-- accepted (deferred target, terminal to repeated acceptance)
   |          +--> declined | expired | failed
   +------------> declined | expired | failed
```

Statuses are `created`, `viewed`, `accepted`, `declined`, `consumed`, `expired`, and `failed`.
The repository has explicit operations rather than a generic status update:

| Operation | Guard |
|---|---|
| `create` | inserts only a new `created` record |
| `get_by_id` | tenant/region-scoped internal lookup |
| `get_by_token_hash` | tenant/region-scoped public-flow lookup |
| `mark_viewed` | atomic `created -> viewed`; repeat is unchanged |
| `claim_accept` | compare-and-swap from unexpired `created|viewed -> accepted` |
| `attach_target` | accepted record and valid target session/job linkage |
| `decline` | atomic `created|viewed -> declined` |
| `expire_if_due` | atomic due `created|viewed -> expired` |
| `consume` | `accepted -> consumed` with the matching linked durable job |
| `mark_failed` | `created|viewed -> failed` after rolled-back orchestration |

Concurrent or sequential accept calls cannot both claim the record. A repeated accept returns
`409 handoff_already_accepted` and does not create another target session, job, quota consumption,
or accepted event. Declined, consumed, expired, and failed are terminal.

## Safe preview contract

`GET /v1/handoffs/{handoff_token}` marks the first valid view and returns only:

```text
handoff_id, status,
source_product_id, source_product_display_name,
target_product_id, target_product_display_name,
target_scenario_id, preview, expires_at,
target_scenario_session_id nullable, target_job_id nullable
```

Preview data comes only from `preview_mapping`. It is JSON-safe and deterministically bounded to
four nesting levels, 20 items per collection, 512 characters per string, and 8 KiB serialized.
Target context is separate, is not truncated, and must validate against the target input schema.
The response never exposes token hashes, mapped target context, source session/job/artifact IDs,
artifact metadata, prompts, providers/models, or debug fields. An expired preview returns HTTP 200
with `status: expired` so a consent UI can render a safe terminal page.

## Acceptance and session linkage

Acceptance pre-generates and creates a target scenario session in the same transaction that claims
and links the handoff. The target session stores:

- the source session in `parent_scenario_session_id`;
- the inherited source chain (or source session id) in `scenario_chain_id`;
- mapped input, runtime `handoff_id`, source session id, and source artifact id in metadata.

The handoff row stores both source and target session IDs and an optional target job ID. Handoff and
runtime events carry the same runtime `handoff_id`, making the relationship auditable in either
direction.

Start behavior is config-owned:

- `immediate`: validate and consume target quota, create the target session as
  `started/processing`, create one `created` target job, attach it, then mark the handoff
  `consumed`. Execution remains queue-and-return; the worker later claims the job.
- `deferred`: create a target session as `waiting_for_user/handoff_ready`, create no job, consume no
  quota, and leave the handoff `accepted` for a future guarded start/consume operation.

Deferred sessions are valid A12 snapshots: `job_id` is null, there is no result, and
`allowed_next_actions` is empty. If the immediate job runs, its action runs, provider calls,
artifacts, and workflow events use the target `scenario_session_id` and retain `handoff_id`; source
and target execution lineage is never collapsed.

If target orchestration fails after acceptance is claimed, that transaction rolls back. A separate
transaction changes the original pre-consent row to `failed`, stores a bounded safe error code, and
emits `handoff.failed`. Acceptance conflicts are not treated as orchestration failures.

## API

- `POST /v1/handoffs` creates from a definition, source session, and canonical result artifact.
- `GET /v1/handoffs/{handoff_token}` returns the safe preview and records first view.
- `POST /v1/handoffs/{handoff_token}/accept` records consent and creates/links the target session.
- `POST /v1/handoffs/{handoff_token}/decline` records a terminal decline.

Public lookup is token-based. Runtime ID lookup remains internal; A17 does not add an arbitrary
public handoff-ID route.

## Event chain

The service emits `handoff.created`, `handoff.viewed`, `handoff.accepted`, `handoff.declined`,
`handoff.expired`, `handoff.failed`, and `handoff.consumed` exactly when the matching durable state
transition succeeds. All include tenant, region, runtime handoff id, and scenario chain.

Immediate successful chain:

```text
handoff.created
handoff.viewed
handoff.accepted
scenario.started (target)
handoff.consumed
workflow.started (when the worker claims the target job)
action/provider/artifact events under the target session
```

Events may contain safe definition/source/target IDs, policy, expiry, and safe error codes. They
must not contain the token, mapped context, preview source paths, raw artifact data, prompts, or LLM
debug/provider payloads.

MVP-A implements the generic backend and a `kernel_demo` smoke definition. Real Freelancer route
maps remain MVP-B config work.
