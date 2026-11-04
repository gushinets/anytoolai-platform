# Execution metering cutover — ANY-507

This procedure changes admission from historical debit-on-start to reserve/consume-on-success.
Use it for the first application cutover, including a database already prepared at `0016`.
Storage preparation alone does not activate the mechanism. Never run old admission/workers beside
new admission/workers. Paid HTTP, Portal access and joint acceptance remain ANY-766-owned.

## Preconditions and evidence

Use one named operator with exclusive maintenance ownership from before quiesce through backup,
migration, smoke and reopening. Runner lifecycle locks cover individual commands, not the whole
maintenance window or raw database commands. Disable competing deployment automation and close
all ingress/admission paths, including demo, Atom Lab and handoff accept. Stop every API replica
and every external queue producer; quiesce must see the entire deployment's database.

Record old/new reviewed SHAs or immutable image digests, Compose/env selection, trusted scope,
PostgreSQL version, source Alembic revision, UTC time, backup checksum and restore verification.
Require green `quick-check`, `postgresql-check`, `full-check`, docs/generated and affected smoke
gates. A failed check, unresolved job outcome or unverifiable backup means **defer cutover**.
Local rehearsal is not evidence that a deployed database is safe to activate.

Keep the database's PostgreSQL major version and volume unchanged for this metering cutover.
If a PostgreSQL major upgrade is also required, perform its separately verified procedure in
[the deployment guide](README.md#upgrading-postgresql-16-to-18) first; do not combine rollback plans.

## Drain and backup on the running revision

Use the running checkout's existing lifecycle commands. They must include `prod-quiesce` and
`prod-recovery-postgres-up` (or the corresponding `atom-lab-*` commands). If tooling is missing,
deploy a compatible tooling-only revision before the maintenance window.

For production, keep the current secret environment file and project selection:

```bash
PROD="docker compose --project-name anytoolai-prod --env-file infra/compose/.env.prod \
  -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml"
python scripts/agent/runner.py prod-quiesce
```

Require exit zero. Quiesce stops API admission, waits for **all** jobs to leave `created/running`
(not only lab, current product, current scope or metered jobs), then stops the worker. PostgreSQL
stays up. A timeout/query error keeps the worker running: keep ingress closed, take no backup,
do not migrate, inspect durable state and worker logs. Do not fabricate reservations, refunds,
success or cancellation to empty the queue. Resolve unknown outcomes through the existing old
worker/lease recovery. To abort before changing code/schema, resume the old revision through its
normal runner readiness path; reopen ingress only when it is healthy.

After a successful drain, verify there are no extra API/worker replicas and confirm:

```bash
$PROD exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' <<'SQL'
SELECT status, count(*) FROM platform.jobs
WHERE status IN ('created', 'running') GROUP BY status;
SELECT version_num FROM alembic_version;
SQL
umask 077
$PROD exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > /operator/backups/any507-before-cutover.dump
sha256sum /operator/backups/any507-before-cutover.dump
```

Require an empty nonterminal query and successful dump exit, then restore the custom-format dump
into a **separate empty verification database**, using the same server's clients:

```bash
$PROD exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" any507_verify'
$PROD exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d any507_verify --exit-on-error' \
  < /operator/backups/any507-before-cutover.dump
```

Creation must fail if that database already exists; choose another unused verification name rather
than restoring over data. Compare the Alembic version, all runtime row counts and ordered row
exports/checksums; a file existing or `pg_restore --list` alone is insufficient. Keep backup files
owner-only. The source remains closed and unmodified throughout verification.

Inventory `scenario_sessions`, `jobs`, `action_runs`, `provider_calls`, `artifacts`, `event_log`,
`guest_identities`, `guest_quota_usage`, `email_captures`, `paywall_intents`, `product_handoffs`,
`atom_lab_runs`, `atom_lab_presets`, `model_catalog_state` and any other existing platform tables.
If already at `0016`, also inventory `paid_allowance_usage` and `execution_reservations`.
Retain source column lists for comparing history after migration, excluding only newly added columns.

## Migrate and activate compatible applications

1. Keep ingress closed. Run `prod-down` without volume deletion, select the reviewed new revision
   and its compatible API/worker/web images and configuration. Preserve the database volume and
   trusted tenant/region; do not rename historical scopes or identities.
2. Run `prod-up`. Its existing one-shot `migrate` service applies the real Alembic chain before
   API/worker startup; it must exit zero. The head for this delivery is `0016`, after `0015`.
   A database already at `0016` receives a no-op migration. No direct Compose application `up`
   or `start` may bypass deployment-profile, activation or readiness gates.
3. Run `prod-ready`, inspect migrate/API/worker logs and verify the head and preserved history.
   Every old job remains `consumption_mode=legacy`; guest `used_count` is unchanged,
   `legacy_used_count` equals pre-cutover used, and `reserved_count=0` at a fresh `0015` upgrade.
   Existing `0016` counters/reservations must instead match their backup exactly. No historical
   reservation is synthesized, including for legacy terminal jobs or legacy replay.
4. While public ingress remains closed, exercise an approved disposable guest through the same
   deployed start → worker → canonical Result API path. Check reserve before execution, exactly
   one consumption after success, failure release, same-key replay and busy versus exhausted
   responses. Inspect the original bucket/session/job/result linkage and transition events.
   Deterministic fake-provider `prod-smoke` is test-environment evidence; it does not validate a
   live production provider configuration. Do not enable internal proof products on production
   merely to run the test smoke.
5. Reopen ingress only after history comparison, application readiness and smoke pass. Record
   acceptance and take a fresh verified backup. Ordinary later updates preserve all history.

For Atom Lab, use `atom-lab-quiesce`, its existing verified backup/recovery procedure, then
`atom-lab-down`, `atom-lab-up` and `atom-lab-ready`; retain its project, volume and secret selection.
The queue check still covers every job in its shared database.

## Failure and rollback

Migration failure, history mismatch or failed smoke keeps admission closed. Do not run old code
against a database that has accepted new reservations. PostgreSQL transactional DDL rolls back a
failed `0016` migration; verify `alembic_version`, columns and original rows before deciding to
retry or resume. Existing Compose migration/readiness failure gates remain mandatory.

After **any** new reservation or paid bucket exists, `alembic downgrade` is refused. Even if a
manual schema rollback appears possible, it cannot restore the old charging contract. Rollback
to debit-on-start code requires the verified pre-cutover backup, restored into a separate empty
database while all application services are stopped. Keep the current database and a fresh safety
backup for investigation; acknowledge that post-backup executions are absent from the restored
state. Never silently merge/replay those executions, refund them, delete history or restore in place
with `--clean`.

Use current recovery tooling: `prod-down`, `prod-recovery-postgres-up`, create the empty recovery
database, stream `pg_restore --exit-on-error` into it, and compare the recorded history/head.
Select that restored database through the unchanged secret/environment configuration convention,
then use the matching old compatible revision's `prod-up` and `prod-ready`. For Atom Lab, follow
the existing [incompatible-schema rollback](README.md#backup-recovery-and-rollback).
Retain both histories until recovery is accepted. A failed restore/comparison defers reopening.

See the [mechanism handoff](../../docs/handoffs/ANY-507-execution-metering.md) for internal
interfaces, readback fixtures and actual local verification limits.
