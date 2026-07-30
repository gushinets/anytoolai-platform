# Scenario Session Model

Every accepted scenario start creates `scenario_session_id`.

For A12, the public API creates the scenario session before it creates the linked workflow job.
With A13 guest quota enabled, `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` first
passes product, scenario, frontend, input, workflow, and guest quota validation, then consumes quota
in the same transaction as session/job creation. The endpoint is therefore the ownership boundary
for backend quota enforcement, initial session creation, durable session input, and the first
frontend-safe polling response.
The quota policy decides whether the consumed counter is product-wide or specific to the scenario
being started.

Scenario session stores:

- `id`;
- `tenant_id`;
- `region`;
- `product_id`;
- `frontend_id`;
- `scenario_id`;
- `scenario_version`;
- `guest_id` nullable;
- `user_id` nullable;
- `status`;
- `current_checkpoint_id` nullable;
- `current_step` nullable;
- `scenario_chain_id` nullable;
- `parent_scenario_session_id` nullable;
- `source_frontend_instance_id` nullable;
- `metadata` JSON;
- `created_at`;
- `started_at`;
- `last_event_at`;
- `completed_at` nullable;
- `expires_at` nullable.

For worker-owned workflow execution, `metadata["input"]` is the durable JSON object passed as
`scenario.input` to the workflow runner. The worker loads it from the linked scenario session,
not from the job row. Missing or non-object input is recorded as a safe failed job.

For A12, `metadata["input"]` is owned by the API start request and must remain a JSON object. The
job row keeps correlation metadata, but the session remains the authoritative store for scenario
input.

Initial statuses:

- `started`
- `waiting_for_user`
- `running`
- `completed`
- `failed`
- `expired`

## A12 runtime checkpoints

`current_checkpoint_id` is the frontend-safe runtime checkpoint for the session.

Current A12 checkpoints are:

- `processing`: non-actionable state while the job is `created` or `running`;
- `handoff_ready`: non-actionable state for an accepted deferred handoff with no job yet;
- `result_ready`: actionable success state after the linked workflow job succeeded;
- `failed`: terminal safe-failure state with no next actions.

`allowed_next_actions` is derived from the current checkpoint:

- `processing` -> `[]`
- `handoff_ready` -> `[]`
- `failed` -> `[]`
- `result_ready` -> `ScenarioDefinition.allowed_next_actions`

The public polling response also exposes `current_checkpoint_id` so the frontend can send it back
to `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}` for stale-check protection.

## A12 session progression

The A12 public lifecycle is:

```text
API start:
  quota consumed + started + processing + created job

Worker claim:
  running + processing

Workflow success:
  completed + result_ready + result_artifact_id

Workflow failure or worker cancellation:
  failed + failed
```

An accepted scenario start is the queue-and-return transaction that commits the consumed quota,
started scenario session, and created linked job. If quota is exhausted, the start is not accepted,
no scenario session or job is created, and the API returns standardized `quota_exhausted`.
For quota-protected products, a missing `guest_id` is also rejected before session/job creation with
frontend-safe `422`; an unknown `guest_id` is rejected before session/job creation with
frontend-safe `404`.

If a queued job is canceled before the worker claims it, polling must still resolve the frontend
snapshot as terminal `failed + failed` even if the stored session row still carries the initial
`processing` checkpoint. Frontends must never observe a terminal failed status paired with the
processing checkpoint.

`GET /v1/scenario-sessions/{id}` is the frontend-safe polling endpoint for this progression. The
response must not expose prompts, provider policies, provider/model names, retry budgets,
PydanticAI run ids, or LiteLLM response ids.

Without `scenario_session_id`, there is no user journey.

## ANY-150 idempotent scenario start

`POST /v1/products/{product_id}/scenarios/{scenario_id}/start` accepts an optional
`Idempotency-Key` request header. A client that retries the same logical start (browser back-button
resubmit, fetch-timeout retry, flaky mobile network) sends the same key on every attempt so the
backend can collapse duplicates instead of creating a second `scenario_sessions` row and consuming a
second guest quota unit for one user click.

`scenario_sessions` stores two additional columns:

- `idempotency_key` nullable `String(256)`;
- `idempotency_request_hash` nullable `String(64)`, a `sha256` digest over `tenant_id`, `region`,
  `product_id`, `scenario_id`, `frontend_id`, `guest_id` (or empty string), `user_id` (or empty
  string), and the canonicalized (`sort_keys=True`, compact separators) `input` payload.
  `source_frontend_instance_id` is deliberately excluded from the hash: it is request telemetry
  (which tab/instance originated the call), not part of "the same logical request" -- including it
  would make a retry from a second tab fail idempotency even though it is the same duplicate the
  header exists to catch.

`platform.scenario_sessions` carries a unique constraint on
`(tenant_id, region, product_id, scenario_id, guest_id, idempotency_key)`
(`uq_scenario_sessions_idempotency_key`, migration `0009`). When a start request carries an
`Idempotency-Key`:

- if an existing row matches that scope and its stored `idempotency_request_hash` equals the
  hash computed for this request, the endpoint returns that row's snapshot (`200`) without
  consuming quota or creating a new job -- a true replay;
- if an existing row matches that scope but the stored hash differs, the endpoint returns
  `409 idempotency_key_conflict` before touching quota -- the same key was reused for a different
  request, which is a caller bug (mint a new key per logical request) rather than a duplicate;
- otherwise the request is genuinely new and follows the ordinary accepted-start path.

`ScenarioRuntimeService.start_session()` does its own `get_by_idempotency_key()` lookup on the raw,
unvalidated request identifiers *before* running any product/scenario/frontend/quota validation, so a
sequential replay of an already-accepted key returns immediately without re-validating config that
only a genuinely new request needs. The row insert-or-select itself
(`ScenarioSessionService.start_or_get_existing()`) has no pre-read of its own -- it goes straight to
an insert guarded by `begin_nested()`/`IntegrityError` recovery on the unique constraint, since its
only caller already ruled out a sequential match a moment earlier; a second, genuinely concurrent
duplicate that missed that earlier lookup is still caught here via the real constraint violation. This
insert-or-select runs **before** quota is consumed. That ordering is what makes concurrent duplicate
submission safe: N requests racing with the same `Idempotency-Key` all attempt the atomic insert
first, exactly one can win it, and only the winner proceeds to quota consumption -- the other N-1
short-circuit to the replay path and never touch quota. Consuming quota before the atomic insert (the
pre-ANY-150 order) cannot give this guarantee, because it cannot tell N concurrent instances of the
same logical request apart from N distinct requests until after quota has already been spent. See
`docs/architecture/quota-model.md` for what happens when quota is exhausted after this insert wins.

A replay (sequential lookup match, or the losing side of a concurrent insert race) resolves the
scenario definition from the persisted row's own `product_id`/`scenario_id`, **without** pinning to
the row's stored `scenario_version`. This is deliberate: the config registry only ever holds the
current definition per `scenario_id`, not a history, so pinning to the original version would 404
(`ScenarioNotFoundError`) every replay whose scenario was bumped to a new version by an ordinary
config deploy in between -- exactly the retry case `Idempotency-Key` exists for. The unpinned
resolution only affects `allowed_next_actions` on an already-completed session (see
`resolve_checkpoint_state`), which is a cosmetic drift risk, not a correctness one. Two known,
accepted residual gaps from this: (1) if the scenario is removed from config entirely (not just
version-bumped), the replay still 404s -- there is no definition left to resolve at all, matching the
pre-existing limitation `GET /v1/scenario-sessions/{id}` already has; (2) under a rolling deploy where
two API instances race on a brand-new key with different config snapshots, the losing instance's
returned `allowed_next_actions` reflects *its own* (possibly newer) config, not necessarily the
version the winning instance actually persisted -- closing this fully would require persisting a
frozen scenario snapshot at accept time, which is out of scope here.

Known, accepted gap: both SQLite and PostgreSQL treat `NULL` as distinct from itself in unique-index
semantics, so a start with `guest_id IS NULL` (a pure `user_id` session, no guest) is not deduplicated
by this constraint even when the same `Idempotency-Key` is reused. This is consistent with the rest
of the guest-quota model -- `consume_for_accepted_start` already requires a non-empty `guest_id` (see
`docs/architecture/quota-model.md`), so the double-charge this ticket fixes is specifically the guest
quota path. Deduplicating the `guest_id IS NULL` path is not fixed here.

Idempotency-Key is orthogonal to the request body: `ScenarioStartRequest`/`ScenarioStartResponse`
are unchanged. CE-kit's `startScenario()` client is still a demo stub deferred to A16 (see
`packages/frontend/ce-kit/src/scenarios/startScenario.ts`); the real client must send
`Idempotency-Key` once it makes a real HTTP call.

## A17 linked handoff sessions

Handoff acceptance always creates the target session immediately. It sets
`parent_scenario_session_id` to the source session, inherits the source `scenario_chain_id` (falling
back to the source session id), and persists `handoff_id`, source session id, source artifact id, and
mapped target input in target metadata.

For an `immediate` definition the target session is `started/processing` and has a newly queued job.
For a `deferred` definition it is `waiting_for_user/handoff_ready`, has no job, consumes no quota,
and is still a valid polling snapshot. Consequently `ScenarioSessionSnapshot.job_id` and the public
`ScenarioSessionResponse.job_id` are nullable, while ordinary start responses continue to return a
non-null job id.
