# Platform Migrations

MVP-A runtime tables:

- scenario_sessions
- jobs
- action_runs
- provider_calls
- artifacts
- event_log
- guest_identities
- guest_quota_usage
- email_captures
- paywall_intents
- product_handoffs

Migration `0003` currently implements the A13 guest identity and guest quota usage tables.
Migration `0004` creates the final A17 handoff table for fresh databases. Migration `0008` is an
idempotent compatibility revision for databases that were stamped through the former placeholder
`0004` before A17 landed; it creates `product_handoffs` only when missing and has a no-op downgrade.
Email capture and paywall intent remain separate access-lite slices.

Migration `0009` adds `scenario_sessions.idempotency_key` / `idempotency_request_hash` plus the
`uq_scenario_sessions_idempotency_key` unique constraint (ANY-150). It is a genuine forward-only,
reversible migration (real `downgrade()`, idempotent guards in both directions) -- `0001` itself is
never edited retroactively. On PostgreSQL the constraint is added with a plain `ALTER TABLE`. SQLite
has no `ALTER TABLE ... ADD CONSTRAINT`, so the constraint is applied via
`op.batch_alter_table(recreate="always")`, validated against this repo's `ATTACH DATABASE ... AS
platform` test schema. `NULL` is distinct from itself in both dialects' unique-constraint semantics,
so a start with `guest_id IS NULL` (pure `user_id` path) is not deduplicated by this constraint.
This is a known, accepted gap, not a defect to fix in ANY-150.

Migration `0010` repairs legacy handoff indexes for already-upgraded databases.

`alembic.ini` in this directory is the checked-in CLI config for explicit Alembic invocations such
as offline SQL generation:

```powershell
uv run alembic -c migrations/platform/alembic.ini upgrade head --sql
```

The offline config URL is a placeholder used only to select the PostgreSQL dialect for SQL output.
