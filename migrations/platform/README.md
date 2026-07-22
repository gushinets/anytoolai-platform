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
